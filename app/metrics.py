"""Tiny in-process request counters exposed in Prometheus text format.

Counters are per worker process. With several gunicorn workers each scrape sees
one worker's numbers; use prometheus_client multiprocess mode for exact totals.
"""

import threading
from collections import defaultdict


class Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self._counts = defaultdict(int)

    def observe(self, method, route, status):
        with self._lock:
            self._counts[(method, route, str(status))] += 1

    def render(self):
        lines = ["# TYPE school_http_requests_total counter"]
        with self._lock:
            items = sorted(self._counts.items())
        for (method, route, status), n in items:
            labels = f'method="{method}",route="{route}",status="{status}"'
            lines.append(f"school_http_requests_total{{{labels}}} {n}")
        return "\n".join(lines) + "\n"
