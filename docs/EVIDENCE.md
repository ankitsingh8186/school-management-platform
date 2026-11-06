# Evidence checklist (fill in before submitting)

Put screenshots in `docs/evidence/` and commit them. Replace the placeholders below.

| Item | How to capture | Link / file |
|---|---|---|
| CI run (green) | GitHub -> Actions -> latest run | `<pipeline run URL>` |
| Image tag + digest | Run summary "Published image" | `<tag>` / `<sha256:...>` |
| Clean build + start | `docker compose up -d --build` then `docker compose ps` | `docs/evidence/01-up.png` |
| Health / readiness / logs | `curl -k https://localhost:8443/ready`, `docker compose logs app` | `docs/evidence/02-health-logs.png` |
| Role rule tests | `make test` and `scripts/smoke_test.sh` output | `docs/evidence/03-tests.png` |
| Failure + recovery | `scripts/drill_failure.sh` output | `docs/evidence/04-drill.png` |
| Backup + restore | See sequence below | `docs/evidence/05-restore.png` |
| Rollback | `scripts/release.sh v1.0.1` then `scripts/rollback.sh` | `docs/evidence/06-rollback.png` |

## Backup/restore sequence to record
```bash
TOKEN=$(curl -ks -X POST https://localhost:8443/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"teacher1","password":"<SEED_PASSWORD>"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -ks -X POST https://localhost:8443/classes/1/attendance -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"student_id":2,"date":"2030-02-01"}'
scripts/backup.sh
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DELETE FROM attendance;"'
scripts/restore.sh backups/<the file just created>
curl -ks https://localhost:8443/classes/1/attendance -H "Authorization: Bearer $TOKEN"   # row is back
```
