"""
AERS UI package.

Provides real-time monitoring and visualization endpoints for the
Audio Event Routing Simulator (AERS), including a WebSocket API
for node-level metrics.
"""

from .server import app  # FastAPI application entrypoint

__all__ = ["app"]

