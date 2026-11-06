"""School Management API: classes, students and attendance."""

import logging
import os
import time
import uuid

from flask import Flask, g, jsonify, request

from .db import Database
from .logging_conf import configure_logging
from .metrics import Metrics
from .routes import bp

log = logging.getLogger("school")


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        DATABASE_URL=os.environ.get("DATABASE_URL", "sqlite:///school.db"),
        JWT_SECRET=os.environ.get("JWT_SECRET", ""),
        JWT_TTL_MINUTES=int(os.environ.get("JWT_TTL_MINUTES", "60")),
        LOG_LEVEL=os.environ.get("LOG_LEVEL", "INFO"),
        APP_VERSION=os.environ.get("APP_VERSION", "dev"),
    )
    if config:
        app.config.update(config)
    if len(app.config["JWT_SECRET"]) < 16:
        raise RuntimeError("JWT_SECRET must be set and at least 16 characters long")

    configure_logging(app.config["LOG_LEVEL"])
    app.db = Database(app.config["DATABASE_URL"])
    app.metrics = Metrics()

    @app.before_request
    def _start_timer():
        g.start = time.perf_counter()
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]

    @app.after_request
    def _log_request(resp):
        started = getattr(g, "start", time.perf_counter())
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        rule = request.url_rule.rule if request.url_rule else "unmatched"
        request_id = getattr(g, "request_id", "-")
        resp.headers["X-Request-ID"] = request_id
        app.metrics.observe(request.method, rule, resp.status_code)
        quiet = rule in ("/health", "/ready", "/metrics")
        log.log(
            logging.DEBUG if quiet else logging.INFO,
            "request",
            extra={
                "fields": {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.path,
                    "status": resp.status_code,
                    "duration_ms": duration_ms,
                    "user": (getattr(g, "user", None) or {}).get("username"),
                }
            },
        )
        return resp

    @app.errorhandler(404)
    def _not_found(_e):
        return jsonify(error="not_found"), 404

    @app.errorhandler(405)
    def _method_not_allowed(_e):
        return jsonify(error="method_not_allowed"), 405

    @app.errorhandler(Exception)
    def _unhandled(_e):
        request_id = getattr(g, "request_id", "-")
        log.exception("unhandled_error", extra={"fields": {"request_id": request_id}})
        return jsonify(error="internal_error", request_id=request_id), 500

    app.register_blueprint(bp)
    return app
