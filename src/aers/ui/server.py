from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Dict, Set, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse

from aers.core.graph_engine import GraphEngine
from aers.ui.metrics import MetricsSnapshot, frame_to_metrics
from aers.utils.config_loader import load_routing_config

# Set up logging
logger = logging.getLogger("aers.ui.server")

# Configure logging to both console and file
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "aers_server.log"

# Create file handler
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(file_formatter)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(console_formatter)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

logger.info(f"Logging to console and file: {log_file}")


DEFAULT_SAMPLE_RATE = 48_000
DEFAULT_BLOCK_SIZE = 1_024
DEFAULT_CONFIG_PATH = "configs/simple_routing.yaml"

# Directory for uploaded audio files
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


app = FastAPI(title="AERS Metrics Server", version="0.1.0")

# Allow local dev UI (file://, localhost) to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connected clients
_metrics_clients: Set[WebSocket] = set()
# Control flag for the simulation loop
_simulation_task: Optional[asyncio.Task] = None
# Frame index tracking
_frame_index: int = 0
# Current engine and config (for dynamic updates)
_current_engine: Optional[GraphEngine] = None
_current_config_path: str = DEFAULT_CONFIG_PATH


async def _broadcast_snapshot(snapshot: MetricsSnapshot) -> None:
    """Send a metrics snapshot to all connected WebSocket clients."""
    if not _metrics_clients:
        return

    data = snapshot.to_dict()
    disconnected: Set[WebSocket] = set()

    for ws in list(_metrics_clients):
        try:
            await ws.send_json(data)
        except WebSocketDisconnect:
            disconnected.add(ws)
        except Exception:
            # Any unexpected error: drop the client quietly
            disconnected.add(ws)

    for ws in disconnected:
        _metrics_clients.discard(ws)


async def _simulation_loop(
    config_path: str,
    block_size: int = DEFAULT_BLOCK_SIZE,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> None:
    """
    Background simulation loop.

    - Loads routing config
    - Instantiates GraphEngine
    - Continuously processes blocks
    - Broadcasts node metrics over WebSocket to all subscribers
    """
    global _frame_index, _current_engine, _current_config_path

    try:
        logger.info(f"🔄 Loading config: {config_path}")
        routing_config = load_routing_config(config_path)
        logger.info(f"✅ Config loaded: {len(routing_config.node_specs)} nodes, {len(routing_config.connections)} connections")
        
        engine = GraphEngine(
            sample_rate=routing_config.sample_rate,
            frame_size=routing_config.frame_size,
            node_specs=routing_config.node_specs,
            connections=routing_config.connections,
            default_channels=2,
        )
        
        logger.info(f"✅ Engine created: {list(engine.nodes.keys())}")
        
        _current_engine = engine
        _current_config_path = config_path

        # Use actual frame_size from config
        actual_block_size = routing_config.frame_size
        block_duration = actual_block_size / float(routing_config.sample_rate)

        _frame_index = 0
        logger.info(f"🔄 Starting simulation loop (block_size={actual_block_size}, duration={block_duration:.4f}s)")

        while True:
            try:
                # Process one block of audio through the routing graph
                outputs = engine.process_frame(_frame_index)

                now = time.time()
                node_metrics = []
                for node_name, frame in outputs.items():
                    metric = frame_to_metrics(name=node_name, frame=frame)
                    # Add file info if this is an AudioFileSourceNode
                    node = engine.nodes.get(node_name)
                    if node and hasattr(node, 'get_file_info'):
                        try:
                            file_info = node.get_file_info()
                            # Create new metric with file_info
                            from aers.ui.metrics import NodeMetric
                            metric = NodeMetric(
                                name=metric.name,
                                peak=metric.peak,
                                rms=metric.rms,
                                num_frames=metric.num_frames,
                                num_channels=metric.num_channels,
                                file_info=file_info,
                            )
                        except Exception as e:
                            logger.debug(f"Could not get file info for {node_name}: {e}")
                    node_metrics.append(metric)
                snapshot = MetricsSnapshot(timestamp=now, nodes=node_metrics)

                await _broadcast_snapshot(snapshot)
                
                _frame_index += 1
                # Sleep to approximate real-time behavior
                await asyncio.sleep(block_duration)
            except Exception as e:
                logger.error(f"❌ Error in simulation loop iteration: {e}", exc_info=True)
                # Continue running despite errors
                await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"❌ Fatal error in simulation loop: {e}", exc_info=True)
        # Re-raise so the task is marked as done and can be restarted
        raise


@app.on_event("startup")
async def _on_startup() -> None:
    """Start the background simulation loop."""
    global _simulation_task
    if _simulation_task is None:
        _simulation_task = asyncio.create_task(
            _simulation_loop(config_path=DEFAULT_CONFIG_PATH)
        )


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    """Shutdown background task gracefully."""
    global _simulation_task
    if _simulation_task is not None:
        _simulation_task.cancel()
        try:
            await _simulation_task
        except asyncio.CancelledError:
            pass
        _simulation_task = None


@app.websocket("/ws/metrics")
async def metrics_websocket(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time metrics.

    Clients connect and receive JSON snapshots in the shape:
    {
      "timestamp": 1712345678.123,
      "nodes": [
        {"name": "source1", "peak": 0.2, "rms": 0.14, "num_frames": 1024, "num_channels": 2},
        ...
      ]
    }
    """
    await websocket.accept()
    _metrics_clients.add(websocket)

    try:
        # Keep the connection open. We don't require incoming messages,
        # but we must read to honor WebSocket semantics.
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                # Ignore malformed client messages; we are push-only.
                await asyncio.sleep(0.1)
    finally:
        _metrics_clients.discard(websocket)


@app.post("/api/upload-audio")
async def upload_audio(file: UploadFile = File(...)) -> JSONResponse:
    """
    Upload an audio file and update routing to use it.
    
    The uploaded file will be saved and a new routing config will be created
    that uses the uploaded file as an audio_file source node.
    """
    global _simulation_task, _current_config_path
    
    # Validate file type
    allowed_extensions = {'.wav', '.flac', '.mp3', '.ogg', '.m4a', '.aac'}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Generate unique filename
    file_id = str(uuid.uuid4())
    saved_filename = f"{file_id}{file_ext}"
    saved_path = UPLOAD_DIR / saved_filename
    
    try:
        # Save uploaded file
        with open(saved_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # Create a dynamic config that uses the uploaded file
        # Find the first source node and replace it, or add a new one
        try:
            current_config = load_routing_config(_current_config_path)
            
            # Create new node specs with uploaded file
            new_node_specs = []
            file_source_added = False
            source_id = None
            first_source_id = None
            
            for node_spec in current_config.node_specs:
                node_kind = node_spec.get("kind", "")
                node_id = node_spec.get("id", "")
                
                # Track first source node
                if node_kind in ("sine", "audio_file") and first_source_id is None:
                    first_source_id = node_id
                
                # Replace first sine source with audio_file
                if node_kind == "sine" and not file_source_added:
                    new_node_specs.append({
                        "id": node_id,
                        "kind": "audio_file",
                        "params": {
                            "file_path": str(saved_path.absolute()),
                            "loop": True,
                            "channels": node_spec.get("params", {}).get("channels", 2),
                        }
                    })
                    file_source_added = True
                    source_id = node_id
                else:
                    new_node_specs.append(node_spec)
            
            # If no sine source found, add audio_file as first node
            if not file_source_added:
                source_id = "uploaded_audio"
                new_node_specs.insert(0, {
                    "id": source_id,
                    "kind": "audio_file",
                    "params": {
                        "file_path": str(saved_path.absolute()),
                        "loop": True,
                        "channels": 2,
                    }
                })
                # Update connections: if first source was connected, connect new source to same destination
                if first_source_id:
                    from aers.core.graph_engine import Connection
                    new_connections = []
                    for conn in current_config.connections:
                        if conn.src == first_source_id:
                            new_connections.append(Connection(src=source_id, dst=conn.dst))
                        else:
                            new_connections.append(conn)
                else:
                    # No existing connections, use existing ones
                    new_connections = current_config.connections
            else:
                # Use existing connections
                new_connections = current_config.connections
            
            # Create temporary config file
            import yaml
            temp_config_path = UPLOAD_DIR / f"config_{file_id}.yaml"
            
            # Convert Connection objects to dicts for YAML serialization
            connections_dict = [
                {"from": conn.src, "to": conn.dst}
                for conn in new_connections
            ]
            
            with open(temp_config_path, "w") as f:
                yaml.dump({
                    "sample_rate": current_config.sample_rate,
                    "frame_size": current_config.frame_size,
                    "nodes": new_node_specs,
                    "connections": connections_dict,
                }, f)
            
            # Restart simulation with new config
            if _simulation_task:
                _simulation_task.cancel()
                try:
                    await _simulation_task
                except asyncio.CancelledError:
                    pass
                # Give it a moment to fully cancel
                await asyncio.sleep(0.1)
            
            _simulation_task = asyncio.create_task(
                _simulation_loop(config_path=str(temp_config_path))
            )
            
            logger.info(f"✅ Audio uploaded: {file.filename}")
            logger.info(f"   Config: {temp_config_path}")
            logger.info(f"   Source node: {source_id}")
            logger.info(f"   Nodes: {[n.get('id') for n in new_node_specs]}")
            
            return JSONResponse({
                "success": True,
                "message": f"Audio file uploaded and routing updated",
                "filename": file.filename,
                "file_id": file_id,
                "file_url": f"/api/audio/{file_id}",
                "source_node": source_id,
            })
            
        except Exception as e:
            # Clean up on error
            if saved_path.exists():
                saved_path.unlink()
            raise HTTPException(status_code=500, detail=f"Failed to update routing: {e}")
            
    except Exception as e:
        if saved_path.exists():
            saved_path.unlink()
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@app.get("/api/audio/{file_id}")
async def get_audio_file(file_id: str):
    """Serve an uploaded audio file."""
    # Find the file by ID (files are named with UUID)
    for file_path in UPLOAD_DIR.glob(f"{file_id}.*"):
        if file_path.is_file():
            return FileResponse(
                path=str(file_path),
                media_type="audio/mpeg" if file_path.suffix == ".mp3" else "audio/wav",
            )
    raise HTTPException(status_code=404, detail="Audio file not found")


@app.get("/api/status")
async def get_status() -> JSONResponse:
    """Get current server status and routing info."""
    global _current_engine, _current_config_path
    
    status = {
        "running": _simulation_task is not None and not _simulation_task.done(),
        "config_path": _current_config_path,
        "nodes": list(_current_engine.nodes.keys()) if _current_engine else [],
        "connected_clients": len(_metrics_clients),
    }
    
    return JSONResponse(status)

