#!/bin/sh
set -e
python -m app.init_db
exec gunicorn \
  --bind 0.0.0.0:8000 \
  --workers "${WEB_CONCURRENCY:-2}" \
  --worker-tmp-dir /dev/shm \
  --timeout 30 \
  --graceful-timeout 20 \
  --error-logfile - \
  wsgi:app
