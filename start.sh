#!/bin/bash
# Start Bloop Tracker locally

cd "$(dirname "$0")"
source venv/bin/activate

echo "Starting webhook server..."
python webhook_server.py
