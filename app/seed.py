"""Synthetic seed data. No real people or credentials."""

from werkzeug.security import generate_password_hash

STUDENTS = [
    ("Aarav Mehta", "R001"),
    ("Diya Nair", "R002"),
    ("Kabir Singh", "R003"),
    ("Isha Patel", "R004"),
    ("Rohan Das", "R005"),
    ("Meera Iyer", "R006"),
    ("Vihaan Rao", "R007"),
    ("Anaya Gupta", "R008"),
    ("Arjun Kapoor", "R009"),
    ("Sara Khan", "R010"),
    ("Yash Verma", "R011"),
    ("Tara Joshi", "R012"),
]


def seed(db, password):
    """Insert seed data once; does nothing if users already exist."""
    if db.one("SELECT COUNT(*) AS n FROM users")["n"] > 0:
        return False
    pw = generate_password_hash(password)
    with db.transaction() as tx:
        users = [
            ("admin", "admin", "School Admin"),
            ("teacher1", "teacher", "Mrs. Sharma"),
            ("teacher2", "teacher", "Mr. Verma"),
            ("student1", "student", "Aarav Mehta (student login)"),
        ]
        for username, role, name in users:
            tx.execute(
                "INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
                (username, pw, role, name),
            )
        ids = {r["username"]: r["id"] for r in tx.query("SELECT id, username FROM users")}
        classes = [
            ("Grade 8A", ids["teacher1"]),
            ("Grade 8B", ids["teacher2"]),
            ("Grade 9A", ids["teacher1"]),
        ]
        for name, teacher_id in classes:
            tx.execute("INSERT INTO classes (name, teacher_id) VALUES (?, ?)", (name, teacher_id))
        for name, roll in STUDENTS:
            tx.execute("INSERT INTO students (full_name, roll_no) VALUES (?, ?)", (name, roll))
        class_ids = [r["id"] for r in tx.query("SELECT id FROM classes ORDER BY id")]
        student_ids = [r["id"] for r in tx.query("SELECT id FROM students ORDER BY id")]
        for i, sid in enumerate(student_ids):
            tx.execute(
                "INSERT INTO enrollments (class_id, student_id) VALUES (?, ?)",
                (class_ids[i // 4], sid),
            )
    return True
