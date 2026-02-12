# Claude Tracker 🧠

Track all running Claude Code instances from your menu bar / system tray.

Two apps sharing the same core — pick whichever fits your platform:

| App | Platform | Framework |
|-----|----------|-----------|
| `claude_tracker.py` | macOS only | `rumps` (native menu bar) |
| `claude_tracker_tray.py` | macOS · Linux · Windows | `pystray` (system tray) |

## Features

- One coloured dot per Claude instance in the menu bar / tray icon
- Click an instance to see details in a submenu:
  - Status (Thinking, Waiting, Ready)
  - Working directory
  - Last activity time ("2m ago", "5h ago")
  - Message count
  - Current task (if available)
  - Process ID
- **Status indicators:**
  - 🟡 Yellow — Claude is executing a tool / working
  - 🔴 Red — Claude needs your input (permission request)
  - 🟢 Green — Ready for next task
- **Smart notifications** (3-second delay to avoid false alarms):
  - 🔴 Status → waiting: "Claude is waiting for your input"
  - 🟢 Status → ready: "Claude finished the task"
  - Notification cancelled if status reverts before the delay expires
- Auto-refreshes every 1 second
- Manual "Refresh Now" option
- Multiple concurrent instances tracked independently

> **Note:** Status changes to 🟡 only when Claude executes a tool (Bash, Read, Write, etc.).
> Pure text responses don't trigger a hook, so the icon stays 🟢 during those.

## Requirements

- Python 3.8 or later
- `jq`: `brew install jq` / `sudo apt install jq`
- **macOS app:** `pip3 install rumps`
- **Cross-platform tray app:** `pip3 install pystray Pillow`
- **Linux notifications:** `sudo apt install libnotify-bin`
- **Linux tray visibility:** `sudo apt install libappindicator3-1 gir1.2-appindicator3-0.1`

### Platform support — tray app

| Feature | macOS | Linux | Windows |
|---------|-------|-------|---------|
| Tray icon + menu | ✅ | ✅ | ✅ |
| Submenus with details | ✅ | ✅ | ✅ |
| Notifications | ✅ | ✅ (needs `libnotify-bin`) | ⚠️ silent (not yet wired up) |

> **Linux / GNOME**: The system tray is hidden by default on Ubuntu 22+. Install the
> [AppIndicator GNOME extension](https://extensions.gnome.org/extension/615/appindicator-support/)
> to make it visible. KDE, XFCE, and Cinnamon work out of the box.

## Setup

Claude Tracker relies on hooks in `~/.claude/settings.json` to track instance status in real time. Add the following `hooks` block to your settings (merge with any existing content):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "SESSION=$(cat | jq -r '.session_id'); mkdir -p /tmp/claude/$SESSION && echo 'ready' > /tmp/claude/$SESSION/status"}]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "SESSION=$(cat | jq -r '.session_id'); mkdir -p /tmp/claude/$SESSION && echo 'working' > /tmp/claude/$SESSION/status"}]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "SESSION=$(cat | jq -r '.session_id'); echo 'working' > /tmp/claude/$SESSION/status"}]
      }
    ],
    "PermissionRequest": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "SESSION=$(cat | jq -r '.session_id'); mkdir -p /tmp/claude/$SESSION && echo 'waiting_for_human' > /tmp/claude/$SESSION/status"}]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "SESSION=$(cat | jq -r '.session_id'); mkdir -p /tmp/claude/$SESSION && echo 'ready' > /tmp/claude/$SESSION/status"}]
      }
    ]
  }
}
```

Each hook writes a plain-text status to `/tmp/claude/<session_id>/status`. Claude Tracker reads these files — no log parsing, no heuristics.

| Hook | Status written | Meaning |
|------|---------------|---------|
| `SessionStart` | `ready` | New session started |
| `PreToolUse` / `PostToolUse` | `working` | Claude is executing a tool |
| `PermissionRequest` | `waiting_for_human` | Claude needs you to approve/deny something |
| `Stop` | `ready` | Claude finished responding |

> **Multiple instances**: Each session writes to its own subfolder keyed by `session_id`, so concurrent sessions never conflict.

### Quick Start

1. **Install dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Add hooks** to `~/.claude/settings.json` (see above).

3. **Start the app:**

   macOS native menu bar:
   ```bash
   ./start.sh
   # or: python3 claude_tracker.py &
   ```

   Cross-platform tray (macOS / Linux / Windows):
   ```bash
   python3 claude_tracker_tray.py &
   ```

4. Click the icon in your menu bar / system tray.

## Scripts

- `start.sh` — start the macOS app (checks if already running)
- `stop.sh` — stop the tracker
- `claude_tracker.py` — macOS menu bar app (`rumps`)
- `claude_tracker_tray.py` — cross-platform tray app (`pystray`)
- `tracker.py` — core tracking logic (shared by both apps)

## How it Works

1. Claude Code fires hooks (`PreToolUse`, `Stop`, etc.) during a session
2. Each hook writes a one-word status to `/tmp/claude/<session_id>/status`
3. Claude Tracker polls those files every second and updates the tray icon

## Status Detection

| File content | Icon | Meaning |
|---|---|---|
| `working` | 🟡 | Claude is executing a tool |
| `waiting_for_human` | 🔴 | Claude needs you to approve/deny something |
| `ready` or no file | 🟢 | Claude finished, waiting for next task |

## Notes

- Only shows sessions active within the last hour
- Status files live in `/tmp/claude/` and are cleared on reboot; stale files from old sessions are harmless
- The 3-second notification delay filters out rapid status transitions (e.g. tool → stop → tool)

## Troubleshooting

**Icon not appearing?**
- macOS app: `pip3 list | grep rumps`
- Tray app: `pip3 list | grep pystray`
- Check the process is running: `pgrep -f claude_tracker`
- Linux GNOME: install the AppIndicator extension (link above)
- Linux other: `sudo apt install libappindicator3-1 gir1.2-appindicator3-0.1`

**Instances not showing up?**
- Confirm hooks are configured in `~/.claude/settings.json`
- Check that `~/.claude/projects/` has `.jsonl` files
- Verify status files exist: `ls /tmp/claude/`
- Try "Refresh Now" from the menu
