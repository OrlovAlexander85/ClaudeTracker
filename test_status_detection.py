"""
Tests for hook-based status detection

Run with: pytest test_status_detection.py -v
"""

import pytest
from pathlib import Path
from unittest.mock import patch
from tracker import ClaudeInstanceTracker, HOOK_STATUS_DIR, HOOK_STATUS_MAP


def write_status(hook_dir: Path, session_id: str, status: str):
    d = hook_dir / session_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "status").write_text(status)


@pytest.fixture
def tracker():
    return ClaudeInstanceTracker()


class TestReadHookStatus:
    def test_reads_working(self, tracker, tmp_path):
        write_status(tmp_path, "s1", "working")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            assert tracker._read_hook_status("s1") == "working"

    def test_reads_ready(self, tracker, tmp_path):
        write_status(tmp_path, "s2", "ready")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            assert tracker._read_hook_status("s2") == "ready"

    def test_reads_waiting_for_human(self, tracker, tmp_path):
        write_status(tmp_path, "s3", "waiting_for_human")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            assert tracker._read_hook_status("s3") == "waiting_for_human"

    def test_missing_session_returns_none(self, tracker, tmp_path):
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            assert tracker._read_hook_status("no-such-session") is None

    def test_strips_trailing_newline(self, tracker, tmp_path):
        write_status(tmp_path, "s4", "working\n")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            assert tracker._read_hook_status("s4") == "working"

    def test_multiple_sessions_independent(self, tracker, tmp_path):
        write_status(tmp_path, "s-a", "working")
        write_status(tmp_path, "s-b", "ready")
        write_status(tmp_path, "s-c", "waiting_for_human")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            assert tracker._read_hook_status("s-a") == "working"
            assert tracker._read_hook_status("s-b") == "ready"
            assert tracker._read_hook_status("s-c") == "waiting_for_human"


class TestHookStatusMap:
    def test_working_maps_to_thinking(self):
        assert HOOK_STATUS_MAP["working"] == "thinking"

    def test_waiting_for_human_maps_to_waiting(self):
        assert HOOK_STATUS_MAP["waiting_for_human"] == "waiting"

    def test_ready_maps_to_ready(self):
        assert HOOK_STATUS_MAP["ready"] == "ready"

    def test_all_hook_states_covered(self):
        assert set(HOOK_STATUS_MAP.keys()) == {"working", "waiting_for_human", "ready"}

    def test_unknown_status_falls_back_to_ready(self):
        assert HOOK_STATUS_MAP.get("bogus_value", "ready") == "ready"

    def test_none_falls_back_to_ready(self):
        assert HOOK_STATUS_MAP.get(None, "ready") == "ready"


class TestStatusTransitions:
    def test_overwriting_status(self, tracker, tmp_path):
        """Later hook writes override earlier ones"""
        write_status(tmp_path, "session", "working")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            assert tracker._read_hook_status("session") == "working"

        write_status(tmp_path, "session", "ready")
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            assert tracker._read_hook_status("session") == "ready"

    def test_working_to_waiting_to_ready(self, tracker, tmp_path):
        for status in ["working", "waiting_for_human", "ready"]:
            write_status(tmp_path, "session", status)
            with patch("tracker.HOOK_STATUS_DIR", tmp_path):
                assert tracker._read_hook_status("session") == status

    def test_no_hook_file_defaults_to_ready_via_map(self, tracker, tmp_path):
        """Session with no hook file (new/pre-hook) maps to ready"""
        with patch("tracker.HOOK_STATUS_DIR", tmp_path):
            raw = tracker._read_hook_status("new-session")
        assert HOOK_STATUS_MAP.get(raw, "ready") == "ready"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
