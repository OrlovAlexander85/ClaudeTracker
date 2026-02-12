"""
Module to detect and track Claude Code instances
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta


HOOK_STATUS_DIR = Path('/tmp/claude')

HOOK_STATUS_MAP = {
    'working': 'thinking',
    'waiting_for_human': 'waiting',
    'ready': 'ready',
}


class ClaudeInstanceTracker:
    def __init__(self):
        self.claude_dir = Path.home() / ".claude" / "projects"

    def detect_instances(self):
        """Detect all running Claude Code instances"""
        instances = []

        if not self.claude_dir.exists():
            return instances

        processes = self._get_claude_processes()

        for project_dir in self.claude_dir.iterdir():
            if not project_dir.is_dir() or project_dir.name.startswith('.'):
                continue

            instance = self._parse_project_sessions(project_dir, processes)
            if instance:
                instances.append(instance)

        instances.sort(key=lambda x: x['last_activity_date'], reverse=True)
        return instances

    def _get_claude_processes(self):
        """Get list of running Claude Code processes"""
        processes = {}
        try:
            result = subprocess.run(
                ['ps', 'ax', '-o', 'pid,command'],
                capture_output=True,
                text=True
            )
            for line in result.stdout.split('\n'):
                if 'claude' in line.lower() and 'ClaudeTracker' not in line:
                    parts = line.strip().split(None, 1)
                    if len(parts) >= 2:
                        try:
                            pid = int(parts[0])
                            processes[pid] = parts[1]
                        except ValueError:
                            continue
        except Exception as e:
            print(f"Error getting processes: {e}")
        return processes

    def _read_hook_status(self, session_id):
        """Read status written by Claude Code hooks at /tmp/claude/<session_id>/status"""
        try:
            return (HOOK_STATUS_DIR / session_id / 'status').read_text().strip()
        except (FileNotFoundError, OSError):
            return None

    def _parse_project_sessions(self, project_dir, processes):
        """Parse session files for a project directory"""
        try:
            session_files = list(project_dir.glob("*.jsonl"))
            if not session_files:
                return None

            most_recent = max(session_files, key=lambda f: f.stat().st_mtime)
            last_modified = datetime.fromtimestamp(most_recent.stat().st_mtime)
            if datetime.now() - last_modified > timedelta(hours=1):
                return None

            session_id = most_recent.stem

            # Status from hook file — authoritative, no heuristics needed
            hook_status = self._read_hook_status(session_id)
            status = HOOK_STATUS_MAP.get(hook_status, 'ready')

            working_dir, message_count, current_task = self._parse_session_file(most_recent)

            matching_pid = None
            if working_dir != "Unknown":
                for pid, command in processes.items():
                    if working_dir in command:
                        matching_pid = pid
                        break

            return {
                'session_id': session_id,
                'process_id': matching_pid,
                'working_dir': working_dir,
                'project_name': Path(working_dir).name if working_dir != "Unknown" else project_dir.name,
                'last_activity': self._format_time_ago(last_modified),
                'last_activity_date': last_modified,
                'message_count': message_count,
                'current_task': current_task,
                'is_active': matching_pid is not None,
                'status': status
            }

        except Exception as e:
            print(f"Error parsing project {project_dir}: {e}")
            return None

    def _parse_session_file(self, session_file):
        """Extract working directory, message count, and current task from a session file"""
        working_dir = "Unknown"
        message_count = 0
        current_task = None

        try:
            with open(session_file, 'r') as f:
                lines = f.readlines()

            message_count = len([l for l in lines if l.strip()])

            for line in lines[:100]:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if 'cwd' in data and data['cwd'] and len(data['cwd']) > 1:
                        working_dir = data['cwd']
                        break
                except (json.JSONDecodeError, KeyError):
                    continue

            for line in reversed(lines[-100:]):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if current_task is None and data.get('type') == 'assistant':
                        for item in data.get('message', {}).get('content', []):
                            if isinstance(item, dict) and item.get('type') == 'tool_use':
                                if 'subject' in item.get('input', {}):
                                    current_task = item['input']['subject']
                                    break
                    if current_task:
                        break
                except json.JSONDecodeError:
                    continue

        except Exception as e:
            print(f"Error reading session file: {e}")

        return working_dir, message_count, current_task

    def _format_time_ago(self, dt):
        """Format a datetime as relative time ago"""
        seconds = (datetime.now() - dt).total_seconds()
        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m ago"
        elif seconds < 86400:
            return f"{int(seconds / 3600)}h ago"
        else:
            return f"{int(seconds / 86400)}d ago"
