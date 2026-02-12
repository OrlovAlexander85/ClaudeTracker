#!/usr/bin/env python3
"""
Claude Tracker - Cross-platform system tray app (macOS, Linux, Windows)

Requires: pystray, Pillow
Install:  pip install pystray Pillow

On Linux also install: libnotify-bin  (for desktop notifications)
  sudo apt install libnotify-bin      # Debian/Ubuntu
  sudo dnf install libnotify          # Fedora
"""

import sys
import time
import threading
import subprocess
import platform
from PIL import Image, ImageDraw
import pystray
from tracker import ClaudeInstanceTracker


# ── Notification helpers ──────────────────────────────────────────────────────

def send_notification(title: str, message: str) -> None:
    os_name = platform.system()
    try:
        if os_name == "Darwin":
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{message}" with title "{title}" sound name "default"'],
                check=False
            )
        elif os_name == "Linux":
            subprocess.run(["notify-send", title, message], check=False)
        elif os_name == "Windows":
            # pystray has built-in notification support on Windows via the icon object
            # handled separately in ClaudeTrackerTray
            pass
    except FileNotFoundError:
        pass  # notification tool not installed — silently skip


# ── Icon rendering ────────────────────────────────────────────────────────────

STATUS_COLORS = {
    "thinking": (255, 200, 0),    # yellow
    "waiting":  (220, 50,  50),   # red
    "ready":    (50,  180, 50),   # green
    "none":     (120, 120, 120),  # grey — no instances
}

ICON_SIZE = 64


def make_icon(instances: list) -> Image.Image:
    """Draw one dot per instance (up to 8), coloured by status."""
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if not instances:
        cx, cy, r = ICON_SIZE // 2, ICON_SIZE // 2, ICON_SIZE // 4
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=STATUS_COLORS["none"])
        return img

    visible = instances[:8]
    n = len(visible)
    cols = min(n, 4)
    rows = (n + cols - 1) // cols
    dot_r = max(6, ICON_SIZE // (cols * 3))
    cell_w = ICON_SIZE // cols
    cell_h = ICON_SIZE // rows

    for i, inst in enumerate(visible):
        col = i % cols
        row = i // cols
        cx = cell_w * col + cell_w // 2
        cy = cell_h * row + cell_h // 2
        color = STATUS_COLORS.get(inst.get("status", "ready"), STATUS_COLORS["ready"])
        draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=color)

    return img


# ── Main app ──────────────────────────────────────────────────────────────────

class ClaudeTrackerTray:
    REFRESH_INTERVAL = 1       # seconds between polls
    NOTIFY_DELAY     = 3.0     # seconds before sending notification

    def __init__(self):
        self.tracker   = ClaudeInstanceTracker()
        self.instances = []
        self.last_status: dict[str, str] = {}
        self.pending_notifications: dict[str, dict] = {}
        self._stop_event = threading.Event()

        self.icon = pystray.Icon(
            name="Claude Tracker",
            icon=make_icon([]),
            title="Claude Tracker",
            menu=self._build_menu(),
        )

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("Claude Tracker", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Refresh Now", self._on_refresh),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        )

    def _rebuild_menu(self) -> None:
        """Rebuild menu with current instance list."""
        items = []

        if not self.instances:
            items.append(pystray.MenuItem("No active Claude instances", None, enabled=False))
        else:
            label = f"{len(self.instances)} instance{'s' if len(self.instances) != 1 else ''} running"
            items.append(pystray.MenuItem(label, None, enabled=False))
            items.append(pystray.Menu.SEPARATOR)

            for inst in self.instances:
                status = inst.get("status", "ready")
                dot    = {"thinking": "🟡", "waiting": "🔴", "ready": "🟢"}.get(status, "🟢")
                name   = inst.get("project_name", "Unknown")
                status_text = {"thinking": "Thinking/Working", "waiting": "Waiting for input", "ready": "Ready for next task"}.get(status, "Ready")

                sub = [
                    pystray.MenuItem(f"Status: {status_text}", None, enabled=False),
                    pystray.MenuItem(f"📂 {inst.get('working_dir', 'Unknown')}", None, enabled=False),
                    pystray.MenuItem(f"🕐 {inst.get('last_activity', '?')}", None, enabled=False),
                    pystray.MenuItem(f"💬 {inst.get('message_count', 0)} messages", None, enabled=False),
                ]
                if inst.get("current_task"):
                    sub.append(pystray.MenuItem(f"⚡ {inst['current_task']}", None, enabled=False))
                if inst.get("process_id"):
                    sub.append(pystray.MenuItem(f"PID: {inst['process_id']}", None, enabled=False))

                items.append(pystray.MenuItem(f"{dot} {name}", pystray.Menu(*sub)))

        items += [
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Refresh Now", self._on_refresh),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        ]
        self.icon.menu = pystray.Menu(*items)

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_refresh(self, icon=None, item=None) -> None:
        self._refresh()

    def _on_quit(self, icon=None, item=None) -> None:
        self._stop_event.set()
        self.icon.stop()

    # ── Core refresh loop ─────────────────────────────────────────────────────

    def _refresh(self) -> None:
        self.instances = self.tracker.detect_instances()
        self._check_status_changes()
        self._check_pending_notifications()
        self.icon.icon = make_icon(self.instances)
        self._rebuild_menu()

    def _check_status_changes(self) -> None:
        current_time = time.time()
        for inst in self.instances:
            sid     = inst["session_id"]
            status  = inst.get("status", "ready")
            project = inst.get("project_name", "Unknown")
            prev    = self.last_status.get(sid)
            self.last_status[sid] = status

            if prev and prev != status:
                if status in ("waiting", "ready"):
                    self.pending_notifications[sid] = {
                        "status":       status,
                        "timestamp":    current_time,
                        "project_name": project,
                        "notified":     False,
                    }
                elif sid in self.pending_notifications:
                    del self.pending_notifications[sid]

            # Cancel if status reverted before delay elapsed
            if sid in self.pending_notifications:
                if self.pending_notifications[sid]["status"] != status:
                    del self.pending_notifications[sid]

    def _check_pending_notifications(self) -> None:
        current_time = time.time()
        to_remove = []
        for sid, pending in self.pending_notifications.items():
            if pending["notified"]:
                to_remove.append(sid)
                continue
            if current_time - pending["timestamp"] >= self.NOTIFY_DELAY:
                status  = pending["status"]
                project = pending["project_name"]
                if status == "waiting":
                    send_notification(f"Claude – {project}", "Waiting for your input")
                elif status == "ready":
                    send_notification(f"Claude – {project}", "Task completed")
                pending["notified"] = True
                to_remove.append(sid)
        for sid in to_remove:
            self.pending_notifications.pop(sid, None)

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            self._refresh()
            self._stop_event.wait(timeout=self.REFRESH_INTERVAL)

    # ── Entry point ───────────────────────────────────────────────────────────

    def run(self) -> None:
        # Poll on a background thread; pystray owns the main thread
        poller = threading.Thread(target=self._poll_loop, daemon=True)
        poller.start()
        self.icon.run()


def main() -> None:
    ClaudeTrackerTray().run()


if __name__ == "__main__":
    main()
