"""
Tests for end-to-end status detection flow

Verifies that session metadata and hook status files combine correctly.

Run with: pytest test_debug_flow.py -v
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch
from tracker import ClaudeInstanceTracker, HOOK_STATUS_MAP


def make_session_file(tmp_path, session_id, cwd, lines=None):
    """Create a minimal JSONL session file"""
    session_dir = tmp_path / "project-dir"
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / f"{session_id}.jsonl"
    content = [{"cwd": cwd, "type": "user"}] + (lines or [])
    session_file.write_text("\n".join(json.dumps(l) for l in content) + "\n")
    return session_file


def write_hook_status(hook_dir: Path, session_id: str, status: str):
    d = hook_dir / session_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "status").write_text(status)


@pytest.fixture
def tracker():
    return ClaudeInstanceTracker()


def test_working_status_detected(tracker, tmp_path):
    """When hook writes 'working', mapped status is 'thinking'"""
    write_hook_status(tmp_path, "abc-123", "working")
    with patch("tracker.HOOK_STATUS_DIR", tmp_path):
        raw = tracker._read_hook_status("abc-123")
    assert HOOK_STATUS_MAP.get(raw, "ready") == "thinking"


def test_ready_status_after_stop(tracker, tmp_path):
    """When hook writes 'ready' (Stop event), mapped status is 'ready'"""
    write_hook_status(tmp_path, "abc-456", "ready")
    with patch("tracker.HOOK_STATUS_DIR", tmp_path):
        raw = tracker._read_hook_status("abc-456")
    assert HOOK_STATUS_MAP.get(raw, "ready") == "ready"


def test_waiting_status_on_permission_request(tracker, tmp_path):
    """When hook writes 'waiting_for_human' (PermissionRequest), mapped status is 'waiting'"""
    write_hook_status(tmp_path, "abc-789", "waiting_for_human")
    with patch("tracker.HOOK_STATUS_DIR", tmp_path):
        raw = tracker._read_hook_status("abc-789")
    assert HOOK_STATUS_MAP.get(raw, "ready") == "waiting"


def test_session_metadata_extracted_correctly(tracker, tmp_path):
    """Session file is parsed for working directory, message count, and current task"""
    lines = [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "TaskCreate", "input": {"subject": "Implement auth"}}
        ]}}
    ]
    session_file = make_session_file(tmp_path, "test-session", "/home/user/my-project", lines)

    wd, count, task = tracker._parse_session_file(session_file)
    assert wd == "/home/user/my-project"
    assert count == 2
    assert task == "Implement auth"


def test_status_and_metadata_are_independent(tracker, tmp_path):
    """Status comes from hook file; metadata comes from session file independently"""
    session_file = make_session_file(tmp_path, "session-xyz", "/projects/my-app")
    write_hook_status(tmp_path, "session-xyz", "working")

    wd, _, _ = tracker._parse_session_file(session_file)
    with patch("tracker.HOOK_STATUS_DIR", tmp_path):
        raw = tracker._read_hook_status("session-xyz")

    assert wd == "/projects/my-app"
    assert HOOK_STATUS_MAP.get(raw, "ready") == "thinking"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
