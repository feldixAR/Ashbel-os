"""Configuration must keep using the database driver in requirements.txt."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("supplied, expected", [
    ("postgres://ci:synthetic%40pass@localhost/ci?sslmode=require",
     "postgresql+psycopg2://ci:synthetic%40pass@localhost/ci?sslmode=require"),
    ("postgresql://ci:synthetic@localhost/ci",
     "postgresql+psycopg2://ci:synthetic@localhost/ci"),
    ("postgresql+psycopg://ci:synthetic@localhost/ci",
     "postgresql+psycopg://ci:synthetic@localhost/ci"),
    ("sqlite:///:memory:", "sqlite:///:memory:"),
])
def test_database_url_selects_installed_driver_without_rewriting_explicit_choice(supplied, expected):
    # New process avoids dependence on which test imported cached settings first.
    result = subprocess.run(
        [sys.executable, "-c", "from config.settings import DATABASE_URL; print(DATABASE_URL)"],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "DATABASE_URL": supplied, "ENVIRONMENT": "test"},
        text=True, capture_output=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected
