"""A busy optional WAL change must not make durable coordination unavailable."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys


def test_sqlite_connection_survives_locked_journal_mode_and_keeps_foreign_keys(tmp_path):
    path = tmp_path / "locked-journal.sqlite"
    lock = sqlite3.connect(path)
    lock.execute("CREATE TABLE synthetic_lock (id INTEGER PRIMARY KEY)")
    lock.commit()
    lock.execute("BEGIN IMMEDIATE")
    lock.execute("INSERT INTO synthetic_lock VALUES (1)")
    try:
        # Independent process must be able to connect and read the committed
        # database even while changing the journal mode is blocked by a writer.
        result = subprocess.run(
            [sys.executable, "-c", """import json
from services.storage.db import engine
with engine.connect() as connection:
    foreign_keys = connection.exec_driver_sql('PRAGMA foreign_keys').scalar_one()
    mode = connection.exec_driver_sql('PRAGMA journal_mode').scalar_one()
    count = connection.exec_driver_sql('SELECT count(*) FROM synthetic_lock').scalar_one()
print(json.dumps({'foreign_keys': foreign_keys, 'mode': mode, 'count': count}))
"""],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "DATABASE_URL": "sqlite:///" + str(path), "ENVIRONMENT": "test"},
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout.strip()) == {"foreign_keys": 1, "mode": "delete", "count": 0}
    finally:
        lock.rollback()
        lock.close()
