"""API tests. Run with: python -m unittest discover -s tests -v"""

import os
import tempfile
import unittest
from unittest import mock

from app import create_app
from app.seed import seed

PASSWORD = "test-pass-123"


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.app = create_app(
            {
                "DATABASE_URL": f"sqlite:///{self.path}",
                "JWT_SECRET": "x" * 32,
                "LOG_LEVEL": "CRITICAL",
            }
        )
        self.app.db.init_schema()
        seed(self.app.db, PASSWORD)
        self.client = self.app.test_client()

    def tearDown(self):
        os.unlink(self.path)

    def auth(self, username, password=PASSWORD):
        resp = self.client.post("/auth/login", json={"username": username, "password": password})
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        return {"Authorization": f"Bearer {resp.get_json()['access_token']}"}

    def mark(self, user, class_id, student_id, **extra):
        body = {"student_id": student_id, "date": "2026-01-12", **extra}
        return self.client.post(
            f"/classes/{class_id}/attendance", json=body, headers=self.auth(user)
        )


class HealthTests(ApiTestCase):
    def test_health_and_ready(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/ready").get_json()["status"], "ready")

    def test_ready_returns_503_when_database_down(self):
        with mock.patch.object(self.app.db, "ping", side_effect=RuntimeError("db down")):
            resp = self.client.get("/ready")
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(self.client.get("/health").status_code, 200)  # liveness unaffected

    def test_metrics_endpoint(self):
        self.client.get("/health")
        body = self.client.get("/metrics").get_data(as_text=True)
        self.assertIn("school_http_requests_total", body)


class AuthTests(ApiTestCase):
    def test_bad_password_rejected(self):
        resp = self.client.post("/auth/login", json={"username": "teacher1", "password": "nope"})
        self.assertEqual(resp.status_code, 401)

    def test_protected_endpoint_requires_token(self):
        self.assertEqual(self.client.get("/classes").status_code, 401)
        bad = {"Authorization": "Bearer not-a-token"}
        self.assertEqual(self.client.get("/classes", headers=bad).status_code, 401)


class ReadTests(ApiTestCase):
    def test_list_classes_and_students(self):
        headers = self.auth("student1")
        classes = self.client.get("/classes", headers=headers).get_json()["classes"]
        self.assertEqual(len(classes), 3)
        self.assertEqual(classes[0]["student_count"], 4)
        students = self.client.get("/classes/1/students", headers=headers).get_json()["students"]
        self.assertEqual([s["roll_no"] for s in students], ["R001", "R002", "R003", "R004"])
        self.assertEqual(self.client.get("/classes/99/students", headers=headers).status_code, 404)


class AttendanceRuleTests(ApiTestCase):
    def test_assigned_teacher_can_record(self):
        resp = self.mark("teacher1", 1, 1)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.get_json()["status"], "present")

    def test_unassigned_teacher_cannot_record(self):
        # teacher2 teaches class 2, not class 1
        resp = self.mark("teacher2", 1, 1)
        self.assertEqual(resp.status_code, 403)
        records = self.client.get("/classes/1/attendance", headers=self.auth("admin"))
        self.assertEqual(records.get_json()["records"], [])

    def test_non_teacher_roles_cannot_record(self):
        self.assertEqual(self.mark("student1", 1, 1).status_code, 403)
        self.assertEqual(self.mark("admin", 1, 1).status_code, 403)

    def test_unauthenticated_cannot_record(self):
        resp = self.client.post("/classes/1/attendance", json={"student_id": 1})
        self.assertEqual(resp.status_code, 401)

    def test_student_must_belong_to_class(self):
        self.assertEqual(self.mark("teacher1", 1, 5).status_code, 422)  # student 5 is in class 2

    def test_duplicate_for_same_date_and_session_rejected(self):
        self.assertEqual(self.mark("teacher1", 1, 1).status_code, 201)
        self.assertEqual(self.mark("teacher1", 1, 1).status_code, 409)

    def test_same_student_different_session_or_date_allowed(self):
        self.assertEqual(self.mark("teacher1", 1, 1).status_code, 201)
        self.assertEqual(self.mark("teacher1", 1, 1, session="afternoon").status_code, 201)
        self.assertEqual(self.mark("teacher1", 1, 1, date="2026-01-13").status_code, 201)

    def test_invalid_input_rejected(self):
        self.assertEqual(self.mark("teacher1", 1, "1").status_code, 400)
        self.assertEqual(self.mark("teacher1", 1, 1, status="sleeping").status_code, 400)
        self.assertEqual(self.mark("teacher1", 1, 1, session="night").status_code, 400)
        self.assertEqual(self.mark("teacher1", 1, 1, date="12-01-2026").status_code, 400)

    def test_unknown_class_returns_404(self):
        self.assertEqual(self.mark("teacher1", 99, 1).status_code, 404)


class AuditTests(ApiTestCase):
    def test_audit_log_records_success_and_denial(self):
        self.mark("teacher1", 1, 1)
        self.mark("teacher2", 1, 1)
        entries = self.client.get("/audit-log", headers=self.auth("admin")).get_json()["entries"]
        outcomes = {(e["actor"], e["action"], e["outcome"]) for e in entries}
        self.assertIn(("teacher1", "record_attendance", "success"), outcomes)
        self.assertIn(("teacher2", "record_attendance", "denied"), outcomes)

    def test_audit_log_is_admin_only(self):
        resp = self.client.get("/audit-log", headers=self.auth("teacher1"))
        self.assertEqual(resp.status_code, 403)


if __name__ == "__main__":
    unittest.main()
