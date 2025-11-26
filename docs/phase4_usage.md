# Phase 4: Visualization UI - Usage Guide

## Quick Start

### 1. Install Dependencies

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start the Metrics Server

```bash
PYTHONPATH=src python scripts/run_server.py --reload
```

The server will start on `http://localhost:8000` with:
- WebSocket endpoint: `ws://localhost:8000/ws/metrics`
- CORS enabled for local development

### 3. Open the Dashboard

**Option A: Direct file access (quick)**
- Open `ui/dashboard/index.html` directly in your browser
- Note: WebSocket will connect to `localhost:8000` by default

**Option B: Serve with HTTP server (recommended)**
```bash
cd ui/dashboard
python -m http.server 4173
# Then open http://localhost:4173 in your browser
```

## What You'll See

1. **WebSocket Status**: Shows "Connected" when the dashboard is receiving metrics
2. **Node Levels**: Real-time visualization of each node with:
   - Node name
   - Peak level (dBFS)
   - RMS level (dBFS)
   - Frame/channel info
   - Visual level bar (green → yellow → red)

## Server Configuration

The server uses `configs/simple_routing.yaml` by default. To use a different config:

Edit `src/aers/ui/server.py` and change:
```python
DEFAULT_CONFIG_PATH = "configs/your_config.yaml"
```

Or modify the `_simulation_loop` call in `_on_startup()`.

## Architecture

- **Backend**: FastAPI server with WebSocket support
- **Metrics**: Computed from `AudioFrame` objects (peak, RMS)
- **Real-time**: Updates broadcast to all connected clients
- **Frontend**: Vanilla JavaScript (no framework dependencies)

## API Endpoints

- `GET /` - FastAPI docs (if enabled)
- `WebSocket /ws/metrics` - Real-time metrics stream

## Troubleshooting

- **WebSocket disconnected**: Check that the server is running on port 8000
- **No metrics**: Verify the config file exists and is valid
- **CORS errors**: The server allows all origins by default for development

