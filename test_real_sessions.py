"""
Tests for detect_instances integration

Verifies that detect_instances() returns well-formed instance data
using isolated temporary session and hook directories.

Run with: pytest test_real_sessions.py -v
"""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch
from tracker import ClaudeInstanceTracker, HOOK_STATUS_MAP


def make_session_dir(base: Path, project_name: str, session_id: str, cwd: str, lines=None):
    """Create a minimal project directory with a recent session file"""
    project_dir = base / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    session_file = project_dir / f"{session_id}.jsonl"
    content = [{"cwd": cwd, "type": "user"}] + (lines or [])
    session_file.write_text("\n".join(json.dumps(l) for l in content) + "\n")
    # Touch to ensure modification time is recent (within the 1-hour cutoff)
    session_file.touch()
    return project_dir


def write_hook_status(hook_dir: Path, session_id: str, status: str):
    d = hook_dir / session_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "status").write_text(status)


@pytest.fixture
def tracker():
    return ClaudeInstanceTracker()


class TestDetectInstances:
    """Verify detect_instances returns correctly structured data"""

    def test_single_session_detected(self, tracker, tmp_path):
        """A single session file is detected and returns one instance"""
        sessions_dir = tmp_path / "sessions"
        hook_dir = tmp_path / "hooks"
        hook_dir.mkdir()

        make_session_dir(sessions_dir, "project-a", "session-001", "/home/user/project-a")
        write_hook_status(hook_dir, "session-001", "ready")

        tracker.claude_dir = sessions_dir
        with patch("tracker.HOOK_STATUS_DIR", hook_dir):
            instances = tracker.detect_instances()

        assert len(instances) == 1
        assert instances[0]["working_dir"] == "/home/user/project-a"

    def test_instance_has_required_fields(self, tracker, tmp_path):
        """Each detected instance has all required fields"""
        sessions_dir = tmp_path / "sessions"
        hook_dir = tmp_path / "hooks"
        hook_dir.mkdir()

        make_session_dir(sessions_dir, "project-b", "session-002", "/home/user/project-b")
        write_hook_status(hook_dir, "session-002", "working")

        tracker.claude_dir = sessions_dir
        with patch("tracker.HOOK_STATUS_DIR", hook_dir):
            instances = tracker.detect_instances()

        assert len(instances) == 1
        inst = instances[0]
        assert "session_id" in inst
        assert "working_dir" in inst
        assert "status" in inst
        assert "message_count" in inst

    def test_status_reflects_hook_file(self, tracker, tmp_path):
        """Instance status comes from hook file, not log parsing"""
        sessions_dir = tmp_path / "sessions"
        hook_dir = tmp_path / "hooks"
        hook_dir.mkdir()

        make_session_dir(sessions_dir, "project-c", "session-003", "/home/user/project-c")
        write_hook_status(hook_dir, "session-003", "working")

        tracker.claude_dir = sessions_dir
        with patch("tracker.HOOK_STATUS_DIR", hook_dir):
            instances = tracker.detect_instances()

        assert instances[0]["status"] == "thinking"

    def test_waiting_status_reflected(self, tracker, tmp_path):
        """Instance with waiting_for_human hook shows waiting status"""
        sessions_dir = tmp_path / "sessions"
        hook_dir = tmp_path / "hooks"
        hook_dir.mkdir()

        make_session_dir(sessions_dir, "project-d", "session-004", "/home/user/project-d")
        write_hook_status(hook_dir, "session-004", "waiting_for_human")

        tracker.claude_dir = sessions_dir
        with patch("tracker.HOOK_STATUS_DIR", hook_dir):
            instances = tracker.detect_instances()

        assert instances[0]["status"] == "waiting"

    def test_no_hook_file_defaults_to_ready(self, tracker, tmp_path):
        """Session without hook file defaults to ready status"""
        sessions_dir = tmp_path / "sessions"
        hook_dir = tmp_path / "hooks"
        hook_dir.mkdir()

        make_session_dir(sessions_dir, "project-e", "session-005", "/home/user/project-e")
        # No hook file written

        tracker.claude_dir = sessions_dir
        with patch("tracker.HOOK_STATUS_DIR", hook_dir):
            instances = tracker.detect_instances()

        assert instances[0]["status"] == "ready"

    def test_multiple_projects_each_detected(self, tracker, tmp_path):
        """Multiple projects each contribute one instance"""
        sessions_dir = tmp_path / "sessions"
        hook_dir = tmp_path / "hooks"
        hook_dir.mkdir()

        make_session_dir(sessions_dir, "proj-1", "session-101", "/projects/one")
        make_session_dir(sessions_dir, "proj-2", "session-102", "/projects/two")
        write_hook_status(hook_dir, "session-101", "ready")
        write_hook_status(hook_dir, "session-102", "working")

        tracker.claude_dir = sessions_dir
        with patch("tracker.HOOK_STATUS_DIR", hook_dir):
            instances = tracker.detect_instances()

        assert len(instances) == 2
        dirs = {i["working_dir"] for i in instances}
        assert "/projects/one" in dirs
        assert "/projects/two" in dirs

    def test_current_task_extracted(self, tracker, tmp_path):
        """Current task subject is extracted from TaskCreate tool use"""
        sessions_dir = tmp_path / "sessions"
        hook_dir = tmp_path / "hooks"
        hook_dir.mkdir()

        lines = [{"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "TaskCreate", "input": {"subject": "Build the API"}}
        ]}}]
        make_session_dir(sessions_dir, "proj-task", "session-200", "/projects/api", lines)
        write_hook_status(hook_dir, "session-200", "working")

        tracker.claude_dir = sessions_dir
        with patch("tracker.HOOK_STATUS_DIR", hook_dir):
            instances = tracker.detect_instances()

        assert instances[0].get("current_task") == "Build the API"

    def test_empty_sessions_dir_returns_empty_list(self, tracker, tmp_path):
        """Empty sessions directory returns no instances"""
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        hook_dir = tmp_path / "hooks"
        hook_dir.mkdir()

        tracker.claude_dir = sessions_dir
        with patch("tracker.HOOK_STATUS_DIR", hook_dir):
            instances = tracker.detect_instances()

        assert instances == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
