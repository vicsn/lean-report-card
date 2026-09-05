from __future__ import annotations

import os
from pathlib import Path

TEST_DATABASE = Path("/tmp/lean-report-card-tests.db")
TEST_DATABASE.unlink(missing_ok=True)
os.environ.setdefault("LRC_DATABASE_URL", f"sqlite+pysqlite:///{TEST_DATABASE}")
os.environ.setdefault("LRC_REDIS_URL", "redis://127.0.0.1:6399/15")
os.environ.setdefault("LRC_RUNNER_MODE", "mock")
