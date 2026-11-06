"""Create schema and (optionally) seed data. Waits for the database to come up."""

import os
import sys
import time

from .db import Database
from .seed import seed


def main():
    db = Database(os.environ["DATABASE_URL"])
    deadline = time.time() + int(os.environ.get("DB_WAIT_SECONDS", "60"))
    while True:
        try:
            db.ping()
            break
        except Exception as exc:  # any connection error just means "not ready yet"
            if time.time() > deadline:
                print(f"database not reachable: {exc}", file=sys.stderr)
                sys.exit(1)
            time.sleep(2)
    db.init_schema()
    if os.environ.get("SEED_ON_START", "true").lower() == "true":
        password = os.environ.get("SEED_PASSWORD", "")
        if len(password) < 8:
            msg = "SEED_PASSWORD (min 8 chars) is required when SEED_ON_START=true"
            print(msg, file=sys.stderr)
            sys.exit(1)
        print("seeded" if seed(db, password) else "seed skipped (data exists)")


if __name__ == "__main__":
    main()
