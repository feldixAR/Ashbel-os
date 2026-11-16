"""Real multi-process claims, restart replay, and crash safety with SQLite.

SQLite and PostgreSQL both enforce the composite primary key in the database;
no thread-local lock or mocked repository is used for the concurrency proof.
"""
import datetime
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import create_engine
from services.storage.models.scheduler_run import SchedulerRunModel

ROOT = str(Path(__file__).resolve().parents[1])
AT = '2026-11-16T08:00:00+00:00'
WORKER = '''
import datetime, os
from scheduler.job_claim import run_scheduled_once

def callback():
    with open(os.environ['CLAIM_OUTPUT'], 'a') as output:
        output.write('invoked\\n')
    if os.environ.get('CRASH_JOB'):
        os._exit(17)
    if os.environ.get('FAIL_JOB'):
        raise RuntimeError('synthetic job failure')
    return {'sent': False, 'mode': 'draft_only'}

result = run_scheduled_once(os.environ.get('CLAIM_JOB', 'daily_plan'), callback,
                           datetime.datetime.fromisoformat(os.environ['CLAIM_AT']))
print(result)
'''


def environment(tmp_path, create_schema=True):
    db_url = 'sqlite:///' + str(tmp_path / 'claims.sqlite')
    if create_schema:
        engine = create_engine(db_url)
        SchedulerRunModel.__table__.create(engine)
        engine.dispose()
    return {**os.environ, 'DATABASE_URL': db_url, 'ENVIRONMENT': 'test',
            'PYTHONPATH': ROOT, 'CLAIM_AT': AT,
            'CLAIM_OUTPUT': str(tmp_path / 'invocations.txt')}


def spawn(env):
    return subprocess.Popen([sys.executable, '-c', WORKER], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def finish(process, expected=0):
    out, err = process.communicate(timeout=30)
    assert process.returncode == expected, err
    return out


def invocations(tmp_path):
    path = tmp_path / 'invocations.txt'
    return path.read_text().splitlines() if path.exists() else []


def test_workers_and_fresh_process_replay_invoke_exactly_once(tmp_path):
    env = environment(tmp_path)
    workers = [spawn(env) for _ in range(6)]
    results = [finish(worker) for worker in workers]
    assert invocations(tmp_path) == ['invoked']
    assert sum('already_claimed' in result for result in results) == 5
    assert 'draft_only' in ''.join(results)  # winning callback's result is preserved
    assert 'already_claimed' in finish(spawn(env))  # all original processes exited
    assert invocations(tmp_path) == ['invoked']
    env['CLAIM_AT'] = '2026-11-17T08:00:00+00:00'
    finish(spawn(env))
    assert invocations(tmp_path) == ['invoked', 'invoked']


def test_crashed_worker_is_not_automatically_replayed(tmp_path):
    env = environment(tmp_path)
    finish(spawn({**env, 'CRASH_JOB': '1'}), expected=17)
    assert 'already_claimed' in finish(spawn(env))
    assert invocations(tmp_path) == ['invoked']
    from sqlalchemy.orm import Session
    with Session(create_engine(env['DATABASE_URL'])) as session:
        assert session.get(SchedulerRunModel, ('daily_plan', '2026-11-16')).status == 'claimed'


def test_failed_job_is_recorded_and_not_replayed(tmp_path):
    env = environment(tmp_path)
    finish(spawn({**env, 'FAIL_JOB': '1'}), expected=1)
    assert 'already_claimed' in finish(spawn(env))
    from sqlalchemy.orm import Session
    with Session(create_engine(env['DATABASE_URL'])) as session:
        row = session.get(SchedulerRunModel, ('daily_plan', '2026-11-16'))
        assert row.status == 'failed'
        assert row.error == 'synthetic job failure'
        assert row.finished_at


def test_missing_coordination_table_blocks_side_effect(tmp_path):
    env = environment(tmp_path, create_schema=False)
    assert 'claim_unavailable' in finish(spawn(env))
    assert invocations(tmp_path) == []


def test_slots_are_stable_across_timezone_and_interval_restart():
    from scheduler.job_claim import occurrence_slot
    start = datetime.datetime.fromisoformat(AT)
    same = start.astimezone(datetime.timezone(datetime.timedelta(hours=2)))
    for job in ('daily_plan', 'followup', 'gmail_scan'):
        assert occurrence_slot(job, start) == occurrence_slot(job, same)
    assert occurrence_slot('followup', start) == occurrence_slot('followup', start + datetime.timedelta(minutes=30))
    assert occurrence_slot('gmail_scan', start) != occurrence_slot('gmail_scan', start + datetime.timedelta(minutes=30))
    with pytest.raises(ValueError):
        occurrence_slot('daily_plan', datetime.datetime(2026, 11, 16))


def test_all_registered_jobs_use_the_durable_wrapper():
    from api.app import create_app
    from scheduler import revenue_scheduler
    from scheduler.job_claim import run_scheduled_once
    create_app()
    for job in revenue_scheduler._scheduler.get_jobs():
        assert job.func is run_scheduled_once
        assert job.args[0] == job.id
        assert callable(job.args[1])
    assert {job.id for job in revenue_scheduler._scheduler.get_jobs()} == set(revenue_scheduler._JOB_IDS)


def test_claim_outcome_is_visible_without_claiming_business_success():
    from scheduler.job_claim import run_scheduled_once
    from scheduler.revenue_scheduler import status
    import uuid
    job_id = 'status-proof-' + uuid.uuid4().hex
    value = {'dry_run': True, 'sent_outreach': False}
    assert run_scheduled_once(job_id, lambda: value) is value
    claim = next(row for row in status()['recent_claims'] if row['job_id'] == job_id)
    assert claim['status'] == 'returned'
    assert claim['finished_at']
