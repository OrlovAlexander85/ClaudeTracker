"""
Tests verifying that hook statuses correctly map to tracker statuses

Run with: pytest test_hook_fix.py -v
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


class TestStatusMapping:
    """Verify hook status values correctly map to tracker display statuses"""

    def test_working_hook_maps_to_thinking(self, tracker, tmp_path):
        """PreToolUse/PostToolUse hooks write 'working' → tracker shows 'thinking'"""
        write_status(tmp_path, "s1", "working")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            raw = tracker._read_hook_status("s1")
        assert HOOK_STATUS_MAP.get(raw, "ready") == "thinking"

    def test_permission_request_maps_to_waiting(self, tracker, tmp_path):
        """PermissionRequest hook writes 'waiting_for_human' → tracker shows 'waiting'"""
        write_status(tmp_path, "s2", "waiting_for_human")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            raw = tracker._read_hook_status("s2")
        assert HOOK_STATUS_MAP.get(raw, "ready") == "waiting"

    def test_stop_hook_maps_to_ready(self, tracker, tmp_path):
        """Stop/SessionStart hooks write 'ready' → tracker shows 'ready'"""
        write_status(tmp_path, "s3", "ready")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            raw = tracker._read_hook_status("s3")
        assert HOOK_STATUS_MAP.get(raw, "ready") == "ready"

    def test_missing_file_maps_to_ready(self, tracker, tmp_path):
        """No hook file (session pre-dates hooks) defaults to 'ready'"""
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            raw = tracker._read_hook_status("no-file-session")
        assert HOOK_STATUS_MAP.get(raw, "ready") == "ready"

    def test_no_false_waiting_from_completed_task(self, tracker, tmp_path):
        """After task completes (Stop fires), status must not be 'waiting'"""
        write_status(tmp_path, "s4", "ready")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            raw = tracker._read_hook_status("s4")
        assert HOOK_STATUS_MAP.get(raw, "ready") != "waiting"

    def test_unknown_status_value_defaults_to_ready(self, tracker, tmp_path):
        """Unknown status values (e.g. misconfigured hook) should default to ready, not waiting"""
        write_status(tmp_path, "s5", "some_unexpected_value")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            raw = tracker._read_hook_status("s5")
        assert HOOK_STATUS_MAP.get(raw, "ready") == "ready"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
