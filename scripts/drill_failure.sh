#!/usr/bin/env bash
# Failure/recovery drill for the demo: break the database, show detection, recover.
source "$(dirname "$0")/_env.sh"
code() { curl -ks -o /dev/null -w '%{http_code}' "$BASE_URL/$1"; }

echo "== 1. Baseline"; echo "health=$(code health) ready=$(code ready)"
echo "== 2. Stopping the database container"
docker compose stop db
sleep 3
echo "health=$(code health) (app alive)  ready=$(code ready) (expect 503)"
docker compose ps
echo "== 3. Recent app logs showing the failure"
docker compose logs --tail 5 app
echo "== 4. Recovering"
docker compose start db
wait_ready 120
echo "health=$(code health) ready=$(code ready)"
echo "== 5. Killing the app process; restart policy should bring it back"
docker compose kill app
sleep 2
docker compose up -d app   # explicit in case the engine treats 'kill' as a manual stop
wait_ready 120
echo "Recovered: health=$(code health) ready=$(code ready)"
