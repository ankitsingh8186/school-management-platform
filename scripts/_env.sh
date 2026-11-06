# Shared helpers. Sourced by the other scripts.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "Missing .env - run: cp .env.example .env and edit it" >&2; exit 1; }
set -a
# shellcheck disable=SC1091
. ./.env
set +a
BASE_URL="${BASE_URL:-https://localhost:${HTTPS_PORT:-8443}}"

set_env_var() { # set_env_var KEY VALUE  (portable in-place edit of .env)
  grep -v "^$1=" .env > .env.tmp || true
  echo "$1=$2" >> .env.tmp
  mv .env.tmp .env
}

wait_ready() { # wait_ready [seconds]
  local deadline=$((SECONDS + ${1:-90}))
  until curl -ksf "$BASE_URL/ready" > /dev/null; do
    [ $SECONDS -lt $deadline ] || { echo "TIMEOUT waiting for $BASE_URL/ready" >&2; return 1; }
    sleep 2
  done
}
