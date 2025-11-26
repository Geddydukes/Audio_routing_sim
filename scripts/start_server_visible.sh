#!/bin/bash
# Start the AERS server in a visible terminal window
# This will show all logging output

cd "$(dirname "$0")/.." || exit 1

echo "Starting AERS server..."
echo "You should see logging output below:"
echo "======================================"
echo ""

source .venv/bin/activate
PYTHONPATH=src python scripts/run_server.py --reload

