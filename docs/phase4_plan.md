# Phase 4: Visualization UI - Implementation Plan

## Overview
Phase 4 adds a visualization dashboard to monitor the audio routing engine in real-time.

## Architecture

### Backend (API Server)
- **Location**: `src/aers/api/server.py`
- **Framework**: FastAPI
- **Endpoints**:
  - `GET /graph` - Returns nodes + connections
  - `GET /metrics` - Returns latest per-node metrics
  - `POST /control/start` - Start engine
  - `POST /control/stop` - Stop engine
  - `POST /control/step` - Step N frames
  - `WebSocket /ws/metrics` - Streaming metrics updates

### Metrics Collection
- **Location**: `src/aers/core/metrics.py`
- **Components**:
  - `NodeMetrics` dataclass (name, timestamp, peak, num_frames, latency_estimate)
  - `MetricsStore` - Thread-safe dict of latest metrics per node
  - Integration into `GraphEngine.process_frame()` to update metrics

### Frontend (Dashboard)
- **Options**:
  1. Simple React + Vite app (recommended for quick win)
  2. Next.js app (if more features needed)
  3. Plain HTML+JS (ultra-lightweight)
- **Features**:
  - Routing graph view (nodes as boxes, edges as lines)
  - Simple meters (per-node peak visualization)
  - Controls: start, stop, "run N frames"
  - Real-time updates via polling or WebSocket

## Implementation Steps

### Step 1: Metrics Collector
1. Create `src/aers/core/metrics.py`
2. Implement `NodeMetrics` dataclass
3. Implement `MetricsStore` with thread-safe operations
4. Integrate into `GraphEngine` to update metrics after each node processes

### Step 2: FastAPI Server
1. Create `src/aers/api/server.py`
2. Build GraphEngine instance from config
3. Hold MetricsStore instance
4. Implement REST endpoints
5. Optionally add WebSocket for streaming

### Step 3: Simple UI
1. Create frontend directory (e.g., `frontend/` or `src/aers/ui/`)
2. Set up React + Vite (or chosen framework)
3. Fetch `/graph` once to render node boxes
4. Poll `/metrics` every 250-500ms to update meters
5. Add control buttons for start/stop/step

## Dependencies to Add
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `websockets` (optional) - For WebSocket support
- Frontend: `react`, `vite`, `react-dom` (or chosen stack)

## File Structure
```
src/aers/
  api/
    __init__.py
    server.py
  core/
    metrics.py  # NEW
    ...
  ui/  # OR frontend/ (separate repo)
    ...
```

## Next Steps
1. Implement metrics collector
2. Build FastAPI server
3. Create minimal UI
4. Test end-to-end visualization

