import unittest
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import User, Resource, Event, ResourceRequest, ResourceRequestItem, Allocation
from app.services.booking_service import process_resource_request, is_resource_available


class TestRBACAndCERAS(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_seeded_users_exist_and_passwords_work(self):
        admin = User.query.filter_by(email="admin@college.edu").first()
        self.assertIsNotNone(admin)
        self.assertTrue(admin.is_admin)
        self.assertFalse(admin.is_student_organiser)
        self.assertTrue(admin.check_password("admin123"))

        student = User.query.filter_by(email="alex.cs@college.edu").first()
        self.assertIsNotNone(student)
        self.assertTrue(student.is_student_organiser)
        self.assertFalse(student.is_admin)
        self.assertTrue(student.check_password("student123"))

    def test_signup_strictly_assigns_student_organiser(self):
        response = self.client.post("/auth/signup", data={
            "name": "New Test Student",
            "email": "test.student@college.edu",
            "department": "Robotics Club",
            "password": "password123",
            "confirm_password": "password123"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        new_user = User.query.filter_by(email="test.student@college.edu").first()
        self.assertIsNotNone(new_user)
        self.assertEqual(new_user.role, "student_organiser")
        self.assertTrue(new_user.check_password("password123"))

    def test_unauthenticated_user_redirected_to_login(self):
        # Accessing dashboard unauthenticated should redirect to login
        res = self.client.get("/", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/auth/login", res.headers["Location"])

        # Accessing admin users unauthenticated should redirect to login
        res = self.client.get("/admin/users/", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/auth/login", res.headers["Location"])

    def test_student_organiser_blocked_from_admin_endpoints(self):
        # Login as student
        with self.client:
            self.client.post("/auth/login", data={
                "email": "alex.cs@college.edu",
                "password": "student123"
            }, follow_redirects=True)

            # Try to access Admin Users panel
            res = self.client.get("/admin/users/", follow_redirects=True)
            self.assertIn(b"Access denied", res.data)

            # Try to access Add Resource
            res = self.client.get("/resources/new", follow_redirects=True)
            self.assertIn(b"Access denied", res.data)

    def test_admin_can_access_admin_endpoints(self):
        # Login as admin
        with self.client:
            self.client.post("/auth/login", data={
                "email": "admin@college.edu",
                "password": "admin123"
            }, follow_redirects=True)

            res = self.client.get("/admin/users/", follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"User &amp; Role Management", res.data)

            res = self.client.get("/resources/new", follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Add New Campus Resource", res.data)

    def test_calendar_schedule_renders_for_logged_in_user(self):
        with self.client:
            self.client.post("/auth/login", data={
                "email": "alex.cs@college.edu",
                "password": "student123"
            }, follow_redirects=True)

            res = self.client.get("/calendar/", follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"7-Day Booking Schedule Calendar", res.data)
            self.assertIn(b"  Schedule Hub", res.data)


if __name__ == "__main__":
    unittest.main()
