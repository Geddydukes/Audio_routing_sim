# Testing Phase 5 - Quick Start Guide

## Server Status

✅ **AERS API Server**: Running on `http://localhost:8000`
✅ **Dashboard Server**: Running on `http://localhost:4173` (or open `ui/dashboard/index.html` directly)

## Quick Test Steps

### 1. Test the API Server

Open in your browser:
- **API Docs**: http://localhost:8000/docs
- **WebSocket Endpoint**: ws://localhost:8000/ws/metrics

### 2. Test the Dashboard

**Option A**: Open directly in browser
```
open ui/dashboard/index.html
```

**Option B**: Use the HTTP server
```
http://localhost:4173
```

### 3. What to Look For

1. **WebSocket Status**: Should show "Connected" (green)
2. **Node Cards**: Should display nodes from `configs/simple_routing.yaml`:
   - `source1` (sine generator)
   - `bus_main` (gain node)
3. **Real-time Updates**: Peak meters should update as audio is processed
4. **Metrics**: Each node shows:
   - Peak level (dBFS)
   - RMS level (dBFS)
   - Frame/channel info
   - Visual level bar

### 4. Test Security Features

To test plugin manifest loading:

1. Create a plugin directory:
```bash
mkdir -p plugins/example_gain_plugin
```

2. Generate a hash for the plugin (when you have plugin code):
```python
from aers.security.manifest import _hash_directory_sha256
from pathlib import Path
hash_value = _hash_directory_sha256(Path("plugins/example_gain_plugin"))
print(f"Hash: {hash_value}")
```

3. Update `configs/plugins/example_gain_plugin/manifest.yaml` with the real hash

### 5. Check Server Logs

The server logs will show:
- Simulation loop processing frames
- WebSocket connections/disconnections
- Any errors or warnings

## Troubleshooting

- **WebSocket disconnected**: Check server is running on port 8000
- **No metrics**: Verify `configs/simple_routing.yaml` exists and is valid
- **CORS errors**: Server allows all origins by default
- **Port conflicts**: Change ports in `scripts/run_server.py` or docker-compose

## Stop Servers

```bash
# Find and kill the server processes
lsof -ti:8000 | xargs kill
lsof -ti:4173 | xargs kill
```

Or use Ctrl+C if running in foreground.

