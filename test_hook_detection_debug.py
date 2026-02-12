"""
Tests for hook status directory structure

Verifies that hook status files are correctly organized per session.

Run with: pytest test_hook_detection_debug.py -v
"""

import pytest
from pathlib import Path
from unittest.mock import patch
from tracker import ClaudeInstanceTracker


@pytest.fixture
def tracker():
    return ClaudeInstanceTracker()


def test_each_session_has_own_subdirectory(tracker, tmp_path):
    """Each session writes to its own subdirectory, preventing conflicts"""
    sessions = {
        "session-aaa": "working",
        "session-bbb": "ready",
        "session-ccc": "waiting_for_human",
    }
    for session_id, status in sessions.items():
        d = tmp_path / session_id
        d.mkdir()
        (d / "status").write_text(status)

    with patch("tracker.HOOK_STATUS_DIR", tmp_path):
        for session_id, expected in sessions.items():
            assert tracker._read_hook_status(session_id) == expected


def test_sessions_do_not_interfere(tracker, tmp_path):
    """Writing status for one session does not affect another"""
    for session_id, status in [("session-1", "working"), ("session-2", "ready")]:
        d = tmp_path / session_id
        d.mkdir()
        (d / "status").write_text(status)

    with patch("tracker.HOOK_STATUS_DIR", tmp_path):
        assert tracker._read_hook_status("session-1") == "working"
        assert tracker._read_hook_status("session-2") == "ready"


def test_status_file_overwrite(tracker, tmp_path):
    """Status file can be overwritten; latest value wins"""
    d = tmp_path / "session-x"
    d.mkdir()
    status_file = d / "status"

    status_file.write_text("working")
    with patch("tracker.HOOK_STATUS_DIR", tmp_path):
        assert tracker._read_hook_status("session-x") == "working"

    status_file.write_text("ready")
    with patch("tracker.HOOK_STATUS_DIR", tmp_path):
        assert tracker._read_hook_status("session-x") == "ready"


def test_missing_directory_returns_none(tracker, tmp_path):
    """Session directory that was never created returns None"""
    with patch("tracker.HOOK_STATUS_DIR", tmp_path):
        assert tracker._read_hook_status("ghost-session") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
