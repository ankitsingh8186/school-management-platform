# Operations Runbook

All commands run from the repository root on the Docker host. `$BASE=https://localhost:8443`.

## Deploy
1. `cp .env.example .env` and fill in secrets (never commit `.env`).
2. First deploy: `docker compose up -d --build`. Later releases: `scripts/release.sh vX.Y.Z`.
3. Verify: `scripts/smoke_test.sh`, `curl -k $BASE/health`, `curl -k $BASE/ready`,
   `docker compose ps` (all services `healthy`).

## Restart
- One service: `docker compose restart app` (or `db`, `proxy`).
- Everything: `docker compose down && docker compose up -d` (volumes are kept; **never** add `-v`).
- Containers use `restart: unless-stopped`, so they return after a host reboot or crash.

## Logs
- Live: `docker compose logs -f --tail 100 app` (JSON lines: `ts, level, msg, request_id, method, path, status, duration_ms, user`).
- One request: grep the `X-Request-ID` response header value in the app logs.
- Failed readiness: `docker compose logs app | grep readiness_failed`.
- Proxy access logs: `docker compose logs proxy`.
- Who did what: `GET /audit-log` as `admin` (`denied`/`rejected`/`success` outcomes).

## Backup and restore
- Backup: `scripts/backup.sh`. Run before every release and on a schedule, e.g. cron
  `0 2 * * * cd /path/to/repo && scripts/backup.sh`. Copy `backups/` off-host.
- Restore: `scripts/restore.sh backups/<file>.dump` (stops app, `pg_restore --clean`, restarts app).
- Verify: the script prints row counts; also `scripts/smoke_test.sh`.
- Proof of restore (for evidence): record attendance -> backup -> delete rows -> restore ->
  show rows are back (sequence in EVIDENCE.md).

## Rollback
1. `scripts/rollback.sh` (previous tag) or `scripts/rollback.sh vX.Y.Z`.
2. Confirm `curl -k $BASE/health` shows the older version.
3. If data was damaged by the bad release: `scripts/restore.sh` the pre-release backup.

## Incident response

| Symptom | Likely cause | Action |
|---|---|---|
| `/ready` returns 503, `/health` 200 | Database down or unreachable | `docker compose ps db`; `docker compose logs db`; `docker compose start db`; app recovers by itself |
| Proxy returns 502 | App crashed or restarting | `docker compose ps app`; `docker compose logs --tail 100 app`; `docker compose up -d app` |
| App restart-loops, log says `JWT_SECRET must be set` / `SEED_PASSWORD` | Bad `.env` | Fix `.env`, `docker compose up -d app` |
| App log says `database not reachable` | Wrong DB creds or DB still starting | Check `POSTGRES_*` match the initialised volume; wait for DB `healthy` |
| 5xx after release | Bad build | `scripts/rollback.sh` |
| Disk filling | Logs/backups | Prune old `backups/`; `docker system df` |
| Suspected credential leak | - | Rotate `JWT_SECRET` (invalidates tokens), change DB/seed passwords, redeploy |

Escalation steps: 1) contain (rollback / stop proxy), 2) diagnose with logs and audit log,
3) recover (restart / restore), 4) write down timeline and fix.

## Failure drill
`scripts/drill_failure.sh` stops the DB (readiness goes 503 while liveness stays 200), shows logs,
restarts the DB and waits for recovery, then kills the app and verifies it comes back.
