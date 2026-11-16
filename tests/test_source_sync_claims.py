"""Real separate-process workbook lease proof, with no network/provider calls."""
import os
from pathlib import Path
import subprocess
import sys


def test_source_sync_claim_is_shared_across_processes_and_survives_restart(tmp_path):
    root = Path(__file__).resolve().parents[1]
    environment = {**os.environ, "PYTHONPATH": str(root), "ENVIRONMENT": "test",
                   "DATABASE_URL": "sqlite:///" + str(tmp_path / "source-sync.sqlite"),
                   "BUSINESS_ID": "synthetic-sync-processes",
                   "ASHBEL_SOURCE_SPREADSHEET_ID": "synthetic-process-workbook-000000"}
    setup = """from services.storage.db import create_all_tables, get_session
from services.storage.models.source_sync import SourceSyncOperation
create_all_tables()
with get_session() as session:
    session.add(SourceSyncOperation(id='synthetic-operation',business_id='synthetic-sync-processes',
        spreadsheet_id='synthetic-process-workbook-000000',preview_hash='synthetic-hash',
        snapshot_hash='synthetic-snapshot',candidate={},expected_row=[],status='prepared',
        expires_at='2030-01-01T00:00:00+00:00'))
print('ready')
"""
    result = subprocess.run([sys.executable, "-c", setup], cwd=root, env=environment,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    worker = """from services.integrations.source_sync import _operation, _claim
print('won' if _claim(_operation('synthetic-operation')) else 'lost')
"""
    processes = [subprocess.Popen([sys.executable, "-c", worker], cwd=root, env=environment,
                                  text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(6)]
    results = []
    for process in processes:
        out, err = process.communicate(timeout=30)
        assert process.returncode == 0, err
        results.append(out.strip().splitlines()[-1])
    assert results.count("won") == 1 and results.count("lost") == 5
    replay = subprocess.run([sys.executable, "-c", worker], cwd=root, env=environment,
                            text=True, capture_output=True, timeout=30)
    assert replay.returncode == 0, replay.stderr
    assert replay.stdout.strip().splitlines()[-1] == "lost"
