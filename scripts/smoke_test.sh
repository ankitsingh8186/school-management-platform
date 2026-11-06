#!/usr/bin/env bash
# End-to-end check against a running stack. Uses SEED_PASSWORD from .env.
# Override target with BASE_URL, e.g. BASE_URL=http://127.0.0.1:5000
source "$(dirname "$0")/_env.sh"
fail() { echo "FAIL: $*" >&2; exit 1; }
req() { curl -ks -o /tmp/smoke_body -w '%{http_code}' "$@"; }

token() { # token <username>
  curl -ks -X POST "$BASE_URL/auth/login" -H 'Content-Type: application/json' \
    -d "{\"username\":\"$1\",\"password\":\"$SEED_PASSWORD\"}" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'
}
post_att() { # post_att <token> <class> <student> <date>
  req -X POST "$BASE_URL/classes/$2/attendance" -H "Authorization: Bearer $1" \
    -H 'Content-Type: application/json' -d "{\"student_id\":$3,\"date\":\"$4\"}"
}

[ "$(req "$BASE_URL/health")" = 200 ] || fail "/health"
[ "$(req "$BASE_URL/ready")" = 200 ] || fail "/ready"
echo "ok  health + readiness"

T1="$(token teacher1)"; T2="$(token teacher2)"; TS="$(token student1)"
DAY="$(date -u +%F)"
[ "$(req "$BASE_URL/classes" -H "Authorization: Bearer $T1")" = 200 ] || fail "list classes"
echo "ok  list classes"

[ "$(post_att "$TS" 1 1 "$DAY")" = 403 ] || fail "student must not write attendance"
echo "ok  non-teacher blocked (403)"
[ "$(post_att "$T2" 1 1 "$DAY")" = 403 ] || fail "unassigned teacher must not write attendance"
echo "ok  unassigned teacher blocked (403)"
[ "$(post_att "$T1" 1 5 "$DAY")" = 422 ] || fail "student outside class must be rejected"
echo "ok  student not in class rejected (422)"

D="2030-01-$(printf '%02d' $((RANDOM % 28 + 1)))"
[ "$(post_att "$T1" 1 1 "$D")" = 201 ] || fail "assigned teacher should record attendance"
echo "ok  assigned teacher recorded attendance (201)"
[ "$(post_att "$T1" 1 1 "$D")" = 409 ] || fail "duplicate must be rejected"
echo "ok  duplicate rejected (409)"
echo "ALL SMOKE TESTS PASSED"
