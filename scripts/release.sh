#!/usr/bin/env bash
# Build and deploy a tagged release:  scripts/release.sh v1.0.0
source "$(dirname "$0")/_env.sh"
TAG="${1:?usage: scripts/release.sh <tag>  (e.g. v1.0.0)}"
echo "$(date -u +%FT%TZ) ${APP_TAG:-dev}" >> .releases   # remember what we are replacing
set_env_var APP_TAG "$TAG"
docker compose up -d --build
wait_ready 120
echo "Deployed $TAG:"; curl -ks "$BASE_URL/health"; echo
