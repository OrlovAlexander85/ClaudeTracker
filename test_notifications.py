#!/usr/bin/env python3
"""
Test notification logic without running the full app
"""
import time


class MockApp:
    def __init__(self):
        self.pending_notifications = {}
        self.last_status = {}
        self.instances = []

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
                    self.pending_notifications[session_id] = {
                        'status': 'waiting',
                        'timestamp': current_time,
                        'project_name': project_name,
                        'notified': False
                    }
                elif current_status == 'ready':  # GREEN
                    # Status changed to ready - add to pending notifications
                    self.pending_notifications[session_id] = {
                        'status': 'ready',
                        'timestamp': current_time,
                        'project_name': project_name,
                        'notified': False
                    }
                else:
                    # Status changed to THINKING - cancel any pending notification
                    if session_id in self.pending_notifications:
                        del self.pending_notifications[session_id]

            # If status reverted back before notification was shown, cancel it
            if session_id in self.pending_notifications:
                pending = self.pending_notifications[session_id]
                if pending['status'] != current_status:
                    # Status changed before notification was shown - cancel
                    del self.pending_notifications[session_id]


def test_status_changes():
    """Test status change detection logic"""
    app = MockApp()

    # Test 1: Status change from thinking to waiting should create pending notification
    print("Test 1: thinking -> waiting")
    app.instances = [{'session_id': 's1', 'status': 'thinking', 'project_name': 'Project1'}]
    app.check_status_changes()
    assert 's1' not in app.pending_notifications, "First status should not trigger notification"

    app.instances = [{'session_id': 's1', 'status': 'waiting', 'project_name': 'Project1'}]
    app.check_status_changes()
    assert 's1' in app.pending_notifications, "Status change to waiting should create pending notification"
    assert app.pending_notifications['s1']['status'] == 'waiting'
    print("✓ Pending notification created for waiting status")

    # Test 2: Status change from waiting back to thinking should cancel notification
    print("\nTest 2: waiting -> thinking (cancel)")
    app.instances = [{'session_id': 's1', 'status': 'thinking', 'project_name': 'Project1'}]
    app.check_status_changes()
    assert 's1' not in app.pending_notifications, "Status change to thinking should cancel pending notification"
    print("✓ Pending notification cancelled")

    # Test 3: Status change to ready should create pending notification
    print("\nTest 3: thinking -> ready")
    app.instances = [{'session_id': 's1', 'status': 'ready', 'project_name': 'Project1'}]
    app.check_status_changes()
    assert 's1' in app.pending_notifications, "Status change to ready should create pending notification"
    assert app.pending_notifications['s1']['status'] == 'ready'
    print("✓ Pending notification created for ready status")

    # Test 4: Multiple instances
    print("\nTest 4: Multiple instances")
    app.pending_notifications = {}
    app.last_status = {}
    app.instances = [
        {'session_id': 's1', 'status': 'thinking', 'project_name': 'Project1'},
        {'session_id': 's2', 'status': 'thinking', 'project_name': 'Project2'}
    ]
    app.check_status_changes()

    app.instances = [
        {'session_id': 's1', 'status': 'waiting', 'project_name': 'Project1'},
        {'session_id': 's2', 'status': 'ready', 'project_name': 'Project2'}
    ]
    app.check_status_changes()
    assert 's1' in app.pending_notifications
    assert 's2' in app.pending_notifications
    assert app.pending_notifications['s1']['status'] == 'waiting'
    assert app.pending_notifications['s2']['status'] == 'ready'
    print("✓ Multiple pending notifications created")

    print("\nAll tests passed! ✓")


if __name__ == "__main__":
    test_status_changes()
