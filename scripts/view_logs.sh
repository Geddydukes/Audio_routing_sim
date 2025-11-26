#!/bin/bash
# View the server log file in real-time

LOG_FILE="logs/aers_server.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "Log file not found: $LOG_FILE"
    echo "Start the server first to create log file."
    exit 1
fi

echo "Viewing server logs (Ctrl+C to exit)..."
echo "Log file: $LOG_FILE"
echo "======================================"
echo ""

tail -f "$LOG_FILE"

