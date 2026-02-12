#!/bin/bash
# Stop Claude Tracker

if pgrep -f "claude_tracker.py" > /dev/null; then
    echo "Stopping Claude Tracker..."
    pkill -f "claude_tracker.py"
    echo "Claude Tracker stopped."
else
    echo "Claude Tracker is not running."
fi
