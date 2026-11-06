"""Minimal DB layer: PostgreSQL in deployment, SQLite for local tests.

SQL is written with ``?`` placeholders and translated to ``%s`` for PostgreSQL.
"""

import sqlite3
from contextlib import contextmanager

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        id {pk},
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        full_name TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS classes (
        id {pk},
        name TEXT NOT NULL UNIQUE,
        teacher_id INTEGER NOT NULL REFERENCES users(id)
    )""",
    """CREATE TABLE IF NOT EXISTS students (
        id {pk},
        full_name TEXT NOT NULL,
        roll_no TEXT NOT NULL UNIQUE
    )""",
    """CREATE TABLE IF NOT EXISTS enrollments (
        class_id INTEGER NOT NULL REFERENCES classes(id),
        student_id INTEGER NOT NULL REFERENCES students(id),
        PRIMARY KEY (class_id, student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS attendance (
        id {pk},
        class_id INTEGER NOT NULL REFERENCES classes(id),
        student_id INTEGER NOT NULL REFERENCES students(id),
        att_date TEXT NOT NULL,
        session TEXT NOT NULL,
        status TEXT NOT NULL,
        marked_by INTEGER NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL,
        UNIQUE (class_id, student_id, att_date, session)
    )""",
    """CREATE TABLE IF NOT EXISTS audit_log (
        id {pk},
        ts TEXT NOT NULL,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        resource TEXT NOT NULL,
        outcome TEXT NOT NULL,
        detail TEXT NOT NULL DEFAULT ''
    )""",
]


class Tx:
    def __init__(self, db, conn):
        self._db = db
        self._conn = conn

    def query(self, sql, params=()):
        sql = self._db.translate(sql)
        if self._db.is_sqlite:
            rows = self._conn.execute(sql, params).fetchall()
        else:
            with self._conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() if cur.description else []
        return [dict(r) for r in rows]

    def one(self, sql, params=()):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql, params=()):
        sql = self._db.translate(sql)
        if self._db.is_sqlite:
            self._conn.execute(sql, params)
        else:
            with self._conn.cursor() as cur:
                cur.execute(sql, params)


class Database:
    def __init__(self, url):
        self.url = url
        self.is_sqlite = url.startswith("sqlite")
        if self.is_sqlite:
            self.path = url[len("sqlite:///") :]
            self.IntegrityError = sqlite3.IntegrityError
        else:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            self._pg = psycopg2
            self._cursor_factory = RealDictCursor
            self.IntegrityError = psycopg2.IntegrityError

    def translate(self, sql):
        return sql if self.is_sqlite else sql.replace("?", "%s")

    def _connect(self):
        if self.is_sqlite:
            conn = sqlite3.connect(self.path, timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        return self._pg.connect(self.url, connect_timeout=5, cursor_factory=self._cursor_factory)

    @contextmanager
    def transaction(self):
        conn = self._connect()
        try:
            yield Tx(self, conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def query(self, sql, params=()):
        with self.transaction() as tx:
            return tx.query(sql, params)

    def one(self, sql, params=()):
        with self.transaction() as tx:
            return tx.one(sql, params)

    def execute(self, sql, params=()):
        with self.transaction() as tx:
            tx.execute(sql, params)

    def ping(self):
        self.query("SELECT 1 AS ok")

    def init_schema(self):
        pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if self.is_sqlite else "SERIAL PRIMARY KEY"
        with self.transaction() as tx:
            for stmt in SCHEMA:
                tx.execute(stmt.format(pk=pk))
