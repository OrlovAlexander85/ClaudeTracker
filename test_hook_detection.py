"""
Tests for hook status file detection

Run with: pytest test_hook_detection.py -v
"""

import pytest
from pathlib import Path
from unittest.mock import patch
from tracker import ClaudeInstanceTracker


def write_status(hook_dir: Path, session_id: str, status: str):
    d = hook_dir / session_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "status").write_text(status)


@pytest.fixture
def tracker():
    return ClaudeInstanceTracker()


def test_detects_working_status(tracker, tmp_path):
    write_status(tmp_path, "test-session", "working")
    with patch("tracker.HOOK_STATUS_DIR", tmp_path):
        result = tracker._read_hook_status("test-session")
    assert result == "working"


def test_detects_ready_status(tracker, tmp_path):
    write_status(tmp_path, "test-session", "ready")
    with patch("tracker.HOOK_STATUS_DIR", tmp_path):
        result = tracker._read_hook_status("test-session")
    assert result == "ready"


def test_detects_waiting_for_human_status(tracker, tmp_path):
    write_status(tmp_path, "test-session", "waiting_for_human")
    with patch("tracker.HOOK_STATUS_DIR", tmp_path):
        result = tracker._read_hook_status("test-session")
    assert result == "waiting_for_human"


def test_missing_hook_file_returns_none(tracker, tmp_path):
    """Session without a hook file (e.g. started before hooks were configured) returns None"""
    with patch("tracker.HOOK_STATUS_DIR", tmp_path):
        result = tracker._read_hook_status("no-such-session")
    assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
