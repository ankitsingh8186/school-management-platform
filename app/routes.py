"""HTTP API: health, auth, classes, students, attendance, audit log."""

import logging
from datetime import date, datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Blueprint, Response, current_app, g, jsonify, request
from werkzeug.security import check_password_hash

bp = Blueprint("api", __name__)
log = logging.getLogger("school")

SESSIONS = {"morning", "afternoon"}
STATUSES = {"present", "absent", "late"}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def audit(action, resource, outcome, detail="", actor=None):
    """Append an audit record. Never raises into the request path."""
    actor = actor or (getattr(g, "user", None) or {}).get("username", "anonymous")
    try:
        current_app.db.execute(
            "INSERT INTO audit_log (ts, actor, action, resource, outcome, detail) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_now(), actor, action, resource, outcome, detail),
        )
    except Exception:
        log.exception("audit_write_failed")


def authenticated(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify(error="authentication_required"), 401
        try:
            claims = jwt.decode(header[7:], current_app.config["JWT_SECRET"], algorithms=["HS256"])
            g.user = {
                "id": int(claims["sub"]),
                "username": claims["username"],
                "role": claims["role"],
            }
        except (jwt.PyJWTError, KeyError, ValueError):
            return jsonify(error="invalid_token"), 401
        return fn(*args, **kwargs)

    return wrapper


@bp.get("/health")
def health():
    return jsonify(status="ok", version=current_app.config["APP_VERSION"])


@bp.get("/ready")
def ready():
    try:
        current_app.db.ping()
    except Exception:
        log.exception("readiness_failed")
        return jsonify(status="unavailable", reason="database"), 503
    return jsonify(status="ready")


@bp.get("/metrics")
def metrics():
    return Response(current_app.metrics.render(), mimetype="text/plain")


@bp.post("/auth/login")
def login():
    body = request.get_json(silent=True) or {}
    username, password = body.get("username"), body.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify(error="username_and_password_required"), 400
    user = current_app.db.one("SELECT * FROM users WHERE username = ?", (username,))
    if not user or not check_password_hash(user["password_hash"], password):
        audit("login", "auth", "failure", actor=username[:64])
        return jsonify(error="invalid_credentials"), 401
    ttl = timedelta(minutes=current_app.config["JWT_TTL_MINUTES"])
    token = jwt.encode(
        {
            "sub": str(user["id"]),
            "username": user["username"],
            "role": user["role"],
            "exp": datetime.now(timezone.utc) + ttl,
        },
        current_app.config["JWT_SECRET"],
        algorithm="HS256",
    )
    audit("login", "auth", "success", actor=user["username"])
    return jsonify(access_token=token, role=user["role"])


@bp.get("/classes")
@authenticated
def list_classes():
    rows = current_app.db.query(
        "SELECT c.id, c.name, u.full_name AS teacher, "
        "(SELECT COUNT(*) FROM enrollments e WHERE e.class_id = c.id) AS student_count "
        "FROM classes c JOIN users u ON u.id = c.teacher_id ORDER BY c.id"
    )
    return jsonify(classes=rows)


@bp.get("/classes/<int:class_id>/students")
@authenticated
def class_students(class_id):
    db = current_app.db
    if not db.one("SELECT id FROM classes WHERE id = ?", (class_id,)):
        return jsonify(error="class_not_found"), 404
    rows = db.query(
        "SELECT s.id, s.full_name, s.roll_no FROM students s "
        "JOIN enrollments e ON e.student_id = s.id WHERE e.class_id = ? ORDER BY s.id",
        (class_id,),
    )
    return jsonify(class_id=class_id, students=rows)


@bp.get("/classes/<int:class_id>/attendance")
@authenticated
def list_attendance(class_id):
    db = current_app.db
    klass = db.one("SELECT id, teacher_id FROM classes WHERE id = ?", (class_id,))
    if not klass:
        return jsonify(error="class_not_found"), 404
    is_owner = g.user["role"] == "teacher" and klass["teacher_id"] == g.user["id"]
    if g.user["role"] != "admin" and not is_owner:
        return jsonify(error="forbidden"), 403
    sql = (
        "SELECT student_id, att_date, session, status, marked_by FROM attendance "
        "WHERE class_id = ?"
    )
    params = [class_id]
    if request.args.get("date"):
        sql += " AND att_date = ?"
        params.append(request.args["date"])
    rows = db.query(sql + " ORDER BY att_date, session, student_id", tuple(params))
    return jsonify(class_id=class_id, records=rows)


@bp.post("/classes/<int:class_id>/attendance")
@authenticated
def record_attendance(class_id):
    db = current_app.db
    resource = f"class:{class_id}"

    if g.user["role"] != "teacher":
        audit("record_attendance", resource, "denied", "role is not teacher")
        return jsonify(error="forbidden", reason="teacher role required"), 403

    klass = db.one("SELECT id, teacher_id FROM classes WHERE id = ?", (class_id,))
    if not klass:
        return jsonify(error="class_not_found"), 404
    if klass["teacher_id"] != g.user["id"]:
        audit("record_attendance", resource, "denied", "teacher not assigned to class")
        return jsonify(error="forbidden", reason="teacher not assigned to this class"), 403

    body = request.get_json(silent=True) or {}
    student_id = body.get("student_id")
    session = body.get("session", "morning")
    status = body.get("status", "present")
    raw_date = body.get("date") or date.today().isoformat()
    if isinstance(student_id, bool) or not isinstance(student_id, int):
        return jsonify(error="invalid_input", field="student_id"), 400
    if session not in SESSIONS:
        return jsonify(error="invalid_input", field="session", allowed=sorted(SESSIONS)), 400
    if status not in STATUSES:
        return jsonify(error="invalid_input", field="status", allowed=sorted(STATUSES)), 400
    try:
        att_date = date.fromisoformat(str(raw_date)).isoformat()
    except ValueError:
        return jsonify(error="invalid_input", field="date", expected="YYYY-MM-DD"), 400

    enrolled = db.one(
        "SELECT 1 AS ok FROM enrollments WHERE class_id = ? AND student_id = ?",
        (class_id, student_id),
    )
    if not enrolled:
        audit("record_attendance", resource, "rejected", f"student {student_id} not in class")
        return jsonify(error="student_not_in_class"), 422

    try:
        db.execute(
            "INSERT INTO attendance (class_id, student_id, att_date, session, status, "
            "marked_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (class_id, student_id, att_date, session, status, g.user["id"], _now()),
        )
    except db.IntegrityError:
        detail = f"duplicate {student_id} {att_date} {session}"
        audit("record_attendance", resource, "rejected", detail)
        return jsonify(error="duplicate_attendance"), 409

    audit("record_attendance", resource, "success", f"{student_id} {att_date} {session} {status}")
    record = {
        "class_id": class_id,
        "student_id": student_id,
        "date": att_date,
        "session": session,
        "status": status,
    }
    return jsonify(record), 201


@bp.get("/audit-log")
@authenticated
def audit_log():
    if g.user["role"] != "admin":
        return jsonify(error="forbidden"), 403
    try:
        limit = max(1, min(int(request.args.get("limit", 100)), 500))
    except ValueError:
        return jsonify(error="invalid_input", field="limit"), 400
    rows = current_app.db.query(
        "SELECT ts, actor, action, resource, outcome, detail FROM audit_log "
        "ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    return jsonify(entries=rows)
