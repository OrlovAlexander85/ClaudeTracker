#!/bin/bash
# Start Claude Tracker

cd "$(dirname "$0")"

# Check if already running
if pgrep -f "claude_tracker.py" > /dev/null; then
    echo "Claude Tracker is already running"
    exit 0
fi

echo "Starting Claude Tracker..."
echo "Check your menu bar for the 🧠 icon."
echo ""
echo "Press Ctrl+C to stop the app"
echo ""

# Run in foreground
python3 claude_tracker.py
