#!/usr/bin/env bash
# Roll the app back to a previous image tag.
#   scripts/rollback.sh          -> previous release recorded in .releases
#   scripts/rollback.sh v1.0.0   -> a specific tag (image must exist locally or in a registry)
source "$(dirname "$0")/_env.sh"
TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  [ -s .releases ] || { echo "No release history in .releases; pass a tag explicitly." >&2; exit 1; }
  TARGET="$(tail -n 1 .releases | awk '{print $2}')"
fi
docker image inspect "school-api:$TARGET" > /dev/null 2>&1 \
  || { echo "Image school-api:$TARGET not found locally." >&2; exit 1; }
echo "Rolling back app: ${APP_TAG:-dev} -> $TARGET"
set_env_var APP_TAG "$TARGET"
docker compose up -d --no-build --force-recreate app
wait_ready 90
echo "Rollback complete:"; curl -ks "$BASE_URL/health"; echo
