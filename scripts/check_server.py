#!/usr/bin/env python
"""Quick script to check server status and view recent activity."""

import requests
import json
from datetime import datetime

def main():
    try:
        # Check server status
        resp = requests.get("http://localhost:8000/api/status", timeout=2)
        status = resp.json()
        
        print("=" * 60)
        print("AERS Server Status")
        print("=" * 60)
        print(f"Running: {status.get('running', False)}")
        print(f"Config: {status.get('config_path', 'unknown')}")
        print(f"Nodes: {', '.join(status.get('nodes', []))}")
        print(f"Connected WebSocket clients: {status.get('connected_clients', 0)}")
        print("=" * 60)
        
        if status.get('running'):
            print("✅ Simulation is running - metrics should be updating!")
        else:
            print("⚠️  Simulation is NOT running - check server logs for errors")
            
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running on http://localhost:8000")
        print("   Start it with: PYTHONPATH=src python scripts/run_server.py")
    except Exception as e:
        print(f"❌ Error checking server: {e}")

if __name__ == "__main__":
    main()

