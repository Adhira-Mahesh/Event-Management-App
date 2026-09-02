import unittest
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import User, Resource, Event, ResourceRequest, ResourceRequestItem, Allocation


class TestCERASFullWorkflow(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_login_and_logout_flow(self):
        # 1. Login with bad password
        res = self.client.post("/auth/login", data={
            "email": "admin@college.edu",
            "password": "wrongpassword"
        }, follow_redirects=True)
        self.assertIn(b"Invalid email or password", res.data)

        # 2. Login with correct admin credentials
        res = self.client.post("/auth/login", data={
            "email": "admin@college.edu",
            "password": "admin123"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Administrator Workspace", res.data)
        self.assertIn(b"Dr. Eleanor Vance", res.data)

        # 3. Logout
        res = self.client.post("/auth/logout", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"You have been logged out successfully", res.data)

    def test_demo_login_shortcuts(self):
        # Test 1-click admin demo login
        res = self.client.get("/auth/demo-login/admin", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Dr. Eleanor Vance", res.data)

        # Test 1-click student demo login
        res = self.client.get("/auth/demo-login/student", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Alex Rivera", res.data)

    def test_admin_user_role_modification(self):
        # Login as Admin
        self.client.post("/auth/login", data={"email": "admin@college.edu", "password": "admin123"}, follow_redirects=True)

        db.session.expire_all()
        target_student = User.query.filter_by(email="sarah.arts@college.edu").first()

        # Promote Sarah to admin
        res = self.client.post(f"/admin/users/{target_student.id}/role", data={"role": "admin"}, follow_redirects=True)
        self.assertIn(b"Role for Sarah Chen updated to Admin", res.data)
        db.session.expire_all()
        updated = User.query.get(target_student.id)
        self.assertEqual(updated.role, "admin")

        # Demote Sarah back to student_organiser
        res = self.client.post(f"/admin/users/{target_student.id}/role", data={"role": "student_organiser"}, follow_redirects=True)
        self.assertIn(b"Role for Sarah Chen updated to Student Organiser", res.data)
        db.session.expire_all()
        updated = User.query.get(target_student.id)
        self.assertEqual(updated.role, "student_organiser")

    def test_admin_toggle_user_status(self):
        self.client.post("/auth/login", data={"email": "admin@college.edu", "password": "admin123"}, follow_redirects=True)

        db.session.expire_all()
        target_student = User.query.filter_by(email="sarah.arts@college.edu").first()
        self.assertTrue(target_student.is_active)

        # Deactivate
        self.client.post(f"/admin/users/{target_student.id}/toggle-status", follow_redirects=True)
        db.session.expire_all()
        updated = User.query.get(target_student.id)
        self.assertFalse(updated.is_active)

        # Reactivate
        self.client.post(f"/admin/users/{target_student.id}/toggle-status", follow_redirects=True)
        db.session.expire_all()
        updated = User.query.get(target_student.id)
        self.assertTrue(updated.is_active)

    def test_student_organiser_submits_multi_item_request_and_admin_approves(self):
        # 1. Login as student Alex
        self.client.post("/auth/login", data={"email": "alex.cs@college.edu", "password": "student123"}, follow_redirects=True)

        # Create an event
        now = datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(days=12)
        unique_name = f"Robotics Championship {int(datetime.utcnow().timestamp())}"
        res = self.client.post("/events/new", data={
            "name": unique_name,
            "organizer": "Computer Science Society",
            "expected_attendance": "100",
            "start_time": now.strftime("%Y-%m-%dT%H:%M"),
            "end_time": (now + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M"),
            "status": "Pending"
        }, follow_redirects=True)

        db.session.expire_all()
        event = Event.query.filter_by(name=unique_name).first()
        self.assertIsNotNone(event)

        # Submit multi-item resource request (1x Auditorium, 1x Projector)
        res = self.client.post("/requests/new", data={
            "event_id": str(event.id),
            "start_time": event.start_time.strftime("%Y-%m-%dT%H:%M"),
            "end_time": event.end_time.strftime("%Y-%m-%dT%H:%M"),
            "item_type[]": ["Auditorium", "Projector"],
            "item_quantity[]": ["1", "1"],
            "item_capacity[]": ["100", ""],
            "item_preferred[]": ["", ""]
        }, follow_redirects=True)
        self.assertIn(b"Resource request submitted successfully", res.data)

        db.session.expire_all()
        req = ResourceRequest.query.filter_by(event_id=event.id).first()
        self.assertIsNotNone(req)
        self.assertEqual(req.status, "Pending")
        self.assertEqual(len(req.items), 2)

        # 2. Student cannot approve own request
        res = self.client.post(f"/requests/{req.id}/approve", follow_redirects=True)
        self.assertIn(b"Access denied", res.data)

        # 3. Switch to Admin to approve request
        self.client.post("/auth/login", data={"email": "admin@college.edu", "password": "admin123"}, follow_redirects=True)

        res = self.client.post(f"/requests/{req.id}/approve", follow_redirects=True)
        self.assertIn(b"Request approved", res.data)

        db.session.expire_all()
        approved_req = ResourceRequest.query.get(req.id)
        self.assertEqual(approved_req.status, "Approved")
        self.assertEqual(len(approved_req.allocations), 2)


    def test_7_day_calendar_view(self):
        self.client.post("/auth/login", data={"email": "alex.cs@college.edu", "password": "student123"}, follow_redirects=True)

        res = self.client.get("/calendar/", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"7-Day Booking Schedule Calendar", res.data)
        self.assertIn(b"All Resources", res.data)

    def test_real_time_availability_checker(self):
        self.client.post("/auth/login", data={"email": "alex.cs@college.edu", "password": "student123"}, follow_redirects=True)

        now = datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(days=20)
        res = self.client.post("/requests/availability", data={
            "resource_type": "Auditorium",
            "min_capacity": "100",
            "start_time": now.strftime("%Y-%m-%dT%H:%M"),
            "end_time": (now + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M"),
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Available &amp; Suitable Resources", res.data)
        self.assertIn(b"Main Auditorium", res.data)


if __name__ == "__main__":
    unittest.main()
