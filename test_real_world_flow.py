"""
Tests for multi-instance hook status handling

Verifies that concurrent sessions with different statuses don't interfere,
and that status transitions are reflected correctly.

Run with: pytest test_real_world_flow.py -v
"""

import pytest
from pathlib import Path
from unittest.mock import patch
from tracker import ClaudeInstanceTracker, HOOK_STATUS_MAP


def write_status(hook_dir: Path, session_id: str, status: str):
    d = hook_dir / session_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "status").write_text(status)


@pytest.fixture
def tracker():
    return ClaudeInstanceTracker()


class TestMultiInstanceConcurrency:
    """Verify concurrent sessions maintain independent statuses"""

    def test_two_sessions_different_statuses(self, tracker, tmp_path):
        """Two concurrent sessions each return their own status"""
        write_status(tmp_path, "session-a", "working")
        write_status(tmp_path, "session-b", "ready")

        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            status_a = tracker._read_hook_status("session-a")
            status_b = tracker._read_hook_status("session-b")

        assert HOOK_STATUS_MAP.get(status_a, "ready") == "thinking"
        assert HOOK_STATUS_MAP.get(status_b, "ready") == "ready"

    def test_three_sessions_all_different(self, tracker, tmp_path):
        """Three concurrent sessions each maintain separate state"""
        write_status(tmp_path, "session-1", "working")
        write_status(tmp_path, "session-2", "waiting_for_human")
        write_status(tmp_path, "session-3", "ready")

        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            s1 = tracker._read_hook_status("session-1")
            s2 = tracker._read_hook_status("session-2")
            s3 = tracker._read_hook_status("session-3")

        assert HOOK_STATUS_MAP.get(s1, "ready") == "thinking"
        assert HOOK_STATUS_MAP.get(s2, "ready") == "waiting"
        assert HOOK_STATUS_MAP.get(s3, "ready") == "ready"

    def test_status_transition_working_to_ready(self, tracker, tmp_path):
        """Session transitions from working to ready when Stop hook fires"""
        write_status(tmp_path, "session-x", "working")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            assert HOOK_STATUS_MAP.get(tracker._read_hook_status("session-x"), "ready") == "thinking"

        # Stop hook fires → overwrites with 'ready'
        write_status(tmp_path, "session-x", "ready")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            assert HOOK_STATUS_MAP.get(tracker._read_hook_status("session-x"), "ready") == "ready"

    def test_status_transition_ready_to_working(self, tracker, tmp_path):
        """Session transitions from ready to working when PreToolUse fires"""
        write_status(tmp_path, "session-y", "ready")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            assert HOOK_STATUS_MAP.get(tracker._read_hook_status("session-y"), "ready") == "ready"

        write_status(tmp_path, "session-y", "working")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            assert HOOK_STATUS_MAP.get(tracker._read_hook_status("session-y"), "ready") == "thinking"

    def test_waiting_clears_when_stop_fires(self, tracker, tmp_path):
        """After PermissionRequest granted and Stop fires, status returns to ready"""
        write_status(tmp_path, "session-z", "waiting_for_human")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            assert HOOK_STATUS_MAP.get(tracker._read_hook_status("session-z"), "ready") == "waiting"

        # Stop hook fires after session completes
        write_status(tmp_path, "session-z", "ready")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            assert HOOK_STATUS_MAP.get(tracker._read_hook_status("session-z"), "ready") == "ready"

    def test_writing_to_one_session_does_not_affect_others(self, tracker, tmp_path):
        """Status update for one session leaves other sessions unchanged"""
        write_status(tmp_path, "stable-session", "ready")
        write_status(tmp_path, "active-session", "ready")

        # active-session starts working
        write_status(tmp_path, "active-session", "working")

        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            stable = tracker._read_hook_status("stable-session")
            active = tracker._read_hook_status("active-session")

        assert stable == "ready"
        assert active == "working"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
