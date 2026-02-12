#!/usr/bin/env python3
"""
Claude Tracker - A macOS menu bar app to track running Claude Code instances
"""

import rumps
import time
from tracker import ClaudeInstanceTracker


class ClaudeTrackerApp(rumps.App):
    def __init__(self):
        super(ClaudeTrackerApp, self).__init__(
            name="Claude Tracker",
            title="🧠",
            quit_button=None
        )

        self.tracker = ClaudeInstanceTracker()
        self.instances = []

        # Track status changes for delayed notifications
        # Format: {session_id: {'status': 'red/green', 'timestamp': time, 'project_name': name, 'notified': bool}}
        self.pending_notifications = {}

        # Track last known status for each instance
        self.last_status = {}

        # Use rumps.Timer to refresh on the main thread (1 second for faster updates)
        self.timer = rumps.Timer(self.refresh_instances, 1)
        self.timer.start()

        # Initial refresh
        self.refresh_instances(None)

    def refresh_instances(self, sender):
        """Refresh the list of Claude instances"""
        self.instances = self.tracker.detect_instances()

        # Track status changes and manage notifications
        self.check_status_changes()
        self.check_pending_notifications()

        self.update_menu()
        self.update_title()

    def check_status_changes(self):
        """Detect status changes and add to pending notifications"""
        current_time = time.time()

        for instance in self.instances:
            session_id = instance['session_id']
            current_status = instance.get('status', 'ready')
            project_name = instance.get('project_name', 'Unknown')

            # Get previous status
            previous_status = self.last_status.get(session_id)

            # Update last status
            self.last_status[session_id] = current_status

            # Check if status changed to RED or GREEN (from something else)
            if previous_status and previous_status != current_status:
                if current_status == 'waiting':  # RED
                    # Status changed to waiting - add to pending notifications
                    print(f"[Notify] {project_name}: {previous_status}→WAITING, will notify in 3s")
                    self.pending_notifications[session_id] = {
                        'status': 'waiting',
                        'timestamp': current_time,
                        'project_name': project_name,
                        'notified': False
                    }
                elif current_status == 'ready':  # GREEN
                    # Status changed to ready - add to pending notifications
                    print(f"[Notify] {project_name}: {previous_status}→READY, will notify in 3s")
                    self.pending_notifications[session_id] = {
                        'status': 'ready',
                        'timestamp': current_time,
                        'project_name': project_name,
                        'notified': False
                    }
                else:
                    # Status changed to THINKING - cancel any pending notification
                    if session_id in self.pending_notifications:
                        print(f"[Notify] {project_name}: →THINKING, cancelled pending {self.pending_notifications[session_id]['status'].upper()} notification")
                        del self.pending_notifications[session_id]

            # If status reverted back before notification was shown, cancel it
            if session_id in self.pending_notifications:
                pending = self.pending_notifications[session_id]
                if pending['status'] != current_status:
                    # Status changed before notification was shown - cancel
                    print(f"[Notify] {project_name}: {pending['status'].upper()}→{current_status.upper()}, cancelled notification")
                    del self.pending_notifications[session_id]

    def check_pending_notifications(self):
        """Check pending notifications and show them after 3 second delay"""
        current_time = time.time()
        delay = 3.0  # 3 seconds

        # Check each pending notification
        to_remove = []
        for session_id, pending in self.pending_notifications.items():
            if pending['notified']:
                # Already notified, remove from pending
                to_remove.append(session_id)
                continue

            # Check if 3 seconds have passed
            elapsed = current_time - pending['timestamp']
            if elapsed >= delay:
                # Show notification
                status = pending['status']
                project_name = pending['project_name']

                print(f"[Notify] {project_name}: Sending {status.upper()} notification (elapsed: {elapsed:.1f}s)")

                if status == 'waiting':  # RED
                    rumps.notification(
                        title=f"Claude - {project_name}",
                        subtitle="Waiting for your reply",
                        message="Claude is waiting for your input",
                        sound=True
                    )
                elif status == 'ready':  # GREEN
                    rumps.notification(
                        title=f"Claude - {project_name}",
                        subtitle="Task completed",
                        message="Claude finished the task",
                        sound=True
                    )

                # Mark as notified
                pending['notified'] = True
                to_remove.append(session_id)

        # Remove notified items
        for session_id in to_remove:
            if session_id in self.pending_notifications:
                del self.pending_notifications[session_id]

    def update_menu(self):
        """Update the menu with current instances"""
        # Clear all menu items
        self.menu.clear()

        # Add instance count/status
        if not self.instances:
            self.menu.add(rumps.MenuItem("No active Claude instances", callback=None))
        else:
            count_text = f"{len(self.instances)} instance{'s' if len(self.instances) != 1 else ''} running"
            self.menu.add(rumps.MenuItem(count_text, callback=None))
            self.menu.add(rumps.separator)

            # Add each instance
            for instance in self.instances:
                instance_menu = self.create_instance_menu(instance)
                self.menu.add(instance_menu)

        # Add fixed menu items at the bottom
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Refresh Now", callback=self.refresh_now))
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit", callback=self.quit_app))

    def create_instance_menu(self, instance):
        """Create a menu item with submenu for an instance"""
        # Determine status icon based on Claude's state
        status = instance.get('status', 'ready')
        if status == 'thinking':
            status_icon = "🟡"  # Yellow - Claude is thinking/working
        elif status == 'waiting':
            status_icon = "🔴"  # Red - Needs user input
        elif status == 'ready':
            status_icon = "🟢"  # Green - Ready for next task
        else:
            status_icon = "🟢"  # Green - Unknown

        # Add status text
        status_text_map = {
            'thinking': 'Thinking/Working',
            'waiting': 'Waiting for input',
            'ready': 'Ready for next task'
        }
        status_text = status_text_map.get(status, 'Unknown')
        title = f"{status_icon} {instance['project_name']}"

        # Create submenu with details
        submenu_items = [
            rumps.MenuItem(f"Status: {status_text}", callback=None),
            rumps.separator,
            rumps.MenuItem(f"📂 {instance['working_dir']}", callback=None),
            rumps.separator,
            rumps.MenuItem(f"🕐 {instance['last_activity']}", callback=None),
            rumps.MenuItem(f"💬 {instance['message_count']} messages", callback=None),
        ]

        if instance['current_task']:
            submenu_items.extend([
                rumps.separator,
                rumps.MenuItem(f"⚡ {instance['current_task']}", callback=None)
            ])

        if instance['process_id']:
            submenu_items.extend([
                rumps.separator,
                rumps.MenuItem(f"PID: {instance['process_id']}", callback=None)
            ])

        menu_item = rumps.MenuItem(title)
        for item in submenu_items:
            menu_item.add(item)

        return menu_item

    def refresh_now(self, _):
        """Manual refresh callback"""
        self.refresh_instances(None)
        rumps.notification(
            title="Claude Tracker",
            subtitle="Refreshed",
            message=f"Found {len(self.instances)} instance(s)"
        )

    def update_title(self):
        """Update the main menu bar icon - one icon per Claude instance"""
        if not self.instances:
            self.title = "🟢"
            return

        # Sort instances by project name for consistent ordering
        sorted_instances = sorted(self.instances, key=lambda x: x.get('project_name', ''))

        # Create one icon per instance (max 8 to avoid menu bar overflow)
        icons = []
        for instance in sorted_instances[:8]:
            status = instance.get('status', 'ready')
            if status == 'waiting':
                icons.append("🔴")  # Red - needs attention
            elif status == 'thinking':
                icons.append("🟡")  # Yellow - working
            else:
                icons.append("🟢")  # Green - ready

        # If more than 8 instances, add a +count indicator
        if len(self.instances) > 8:
            remaining = len(self.instances) - 8
            icons.append(f"+{remaining}")

        self.title = "".join(icons)

    def quit_app(self, _):
        """Quit the application"""
        self.timer.stop()
        rumps.quit_application()


def main():
    ClaudeTrackerApp().run()


if __name__ == "__main__":
    main()
