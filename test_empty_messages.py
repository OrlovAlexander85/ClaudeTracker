"""
Tests for session file metadata parsing

Run with: pytest test_empty_messages.py -v
"""

import json
import pytest
from tracker import ClaudeInstanceTracker


def make_jsonl(tmp_path, lines, name="session.jsonl"):
    f = tmp_path / name
    f.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    return f


@pytest.fixture
def tracker():
    return ClaudeInstanceTracker()


class TestParseSessionFile:
    def test_extracts_working_directory(self, tracker, tmp_path):
        f = make_jsonl(tmp_path, [{"cwd": "/home/user/project", "type": "user"}])
        wd, _, _ = tracker._parse_session_file(f)
        assert wd == "/home/user/project"

    def test_unknown_working_dir_when_no_cwd(self, tracker, tmp_path):
        f = make_jsonl(tmp_path, [{"type": "user", "message": {"content": []}}])
        wd, _, _ = tracker._parse_session_file(f)
        assert wd == "Unknown"

    def test_counts_non_empty_lines(self, tracker, tmp_path):
        lines = [
            {"cwd": "/project", "type": "user"},
            {"type": "assistant", "message": {"content": []}},
            {"type": "user", "message": {"content": []}},
        ]
        f = make_jsonl(tmp_path, lines)
        _, count, _ = tracker._parse_session_file(f)
        assert count == 3

    def test_extracts_current_task_subject(self, tracker, tmp_path):
        lines = [
            {"cwd": "/project", "type": "user"},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "TaskCreate", "input": {"subject": "Fix the login bug"}}
            ]}},
        ]
        f = make_jsonl(tmp_path, lines)
        _, _, task = tracker._parse_session_file(f)
        assert task == "Fix the login bug"

    def test_no_task_when_no_tool_use(self, tracker, tmp_path):
        lines = [
            {"cwd": "/project", "type": "user"},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "Done"}]}},
        ]
        f = make_jsonl(tmp_path, lines)
        _, _, task = tracker._parse_session_file(f)
        assert task is None

    def test_empty_file_returns_defaults(self, tracker, tmp_path):
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        wd, count, task = tracker._parse_session_file(f)
        assert wd == "Unknown"
        assert count == 0
        assert task is None

    def test_uses_most_recent_task(self, tracker, tmp_path):
        lines = [
            {"cwd": "/project", "type": "user"},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "TaskCreate", "input": {"subject": "Old task"}}
            ]}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "TaskCreate", "input": {"subject": "New task"}}
            ]}},
        ]
        f = make_jsonl(tmp_path, lines)
        _, _, task = tracker._parse_session_file(f)
        assert task == "New task"

    def test_ignores_invalid_json_lines(self, tracker, tmp_path):
        f = tmp_path / "session.jsonl"
        f.write_text('{"cwd": "/project", "type": "user"}\nnot valid json\n{"type": "user"}\n')
        wd, _, _ = tracker._parse_session_file(f)
        assert wd == "/project"

    def test_empty_lines_not_counted(self, tracker, tmp_path):
        f = tmp_path / "session.jsonl"
        f.write_text('{"type": "user"}\n\n\n{"type": "assistant"}\n\n')
        _, count, _ = tracker._parse_session_file(f)
        assert count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
