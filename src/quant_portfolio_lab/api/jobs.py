"""Background data-load jobs.

The loaders already exist as CLI scripts (``scripts/load_prices.py`` and
``scripts/load_fundamentals.py``); a job simply runs them as subprocesses so
the GUI can trigger real pykrx/FinanceDataReader loads without blocking the
API. Job state is in-memory: this is a single-user local tool.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import uuid
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

from .schemas import DataJob, DataLoadRequest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
MAX_LOG_LINES = 40


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class _JobState:
    def __init__(self, kind: str) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.status = "queued"
        self.created_at = _now_iso()
        self.finished_at: str | None = None
        self.log: deque[str] = deque(maxlen=MAX_LOG_LINES)
        self.error: str | None = None

    def snapshot(self) -> DataJob:
        return DataJob(
            id=self.id, kind=self.kind, status=self.status,
            createdAt=self.created_at, finishedAt=self.finished_at,
            logTail=list(self.log), error=self.error,
        )


class DataJobManager:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self._jobs: dict[str, _JobState] = {}
        self._lock = threading.Lock()
        self._db_path = str(db_path) if db_path else None

    def list(self) -> list[DataJob]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
            return [j.snapshot() for j in jobs]

    def get(self, job_id: str) -> DataJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.snapshot() if job else None

    def has_active(self) -> bool:
        with self._lock:
            return any(j.status in ("queued", "running") for j in self._jobs.values())

    def submit(self, request: DataLoadRequest) -> DataJob:
        job = _JobState(request.kind)
        with self._lock:
            self._jobs[job.id] = job
        thread = threading.Thread(
            target=self._run, args=(job, request), daemon=True, name=f"data-load-{job.id}"
        )
        thread.start()
        return job.snapshot()

    def _commands(self, request: DataLoadRequest) -> list[list[str]]:
        common: list[str] = []
        if request.synthetic:
            common.append("--synthetic")
        if self._db_path:
            common += ["--db", self._db_path]

        prices = [sys.executable, str(SCRIPTS_DIR / "load_prices.py"),
                  "--start", request.start, *common]
        if request.end:
            prices += ["--end", request.end]
        if not request.synthetic:
            prices += ["--universe-size", str(request.universeSize)]

        fundamentals = [sys.executable, str(SCRIPTS_DIR / "load_fundamentals.py"),
                        "--start", request.start, *common]
        if request.end:
            fundamentals += ["--end", request.end]

        if request.kind == "prices":
            return [prices]
        if request.kind == "fundamentals":
            return [fundamentals]
        return [prices, fundamentals]  # "all": prices first, then fundamentals

    def _run(self, job: _JobState, request: DataLoadRequest) -> None:
        job.status = "running"
        try:
            for cmd in self._commands(request):
                job.log.append(f"$ {' '.join(cmd[1:])}")
                proc = subprocess.Popen(
                    cmd, cwd=str(REPO_ROOT),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                )
                assert proc.stdout is not None
                for line in proc.stdout:
                    line = line.rstrip()
                    if line:
                        job.log.append(line)
                code = proc.wait()
                if code != 0:
                    raise RuntimeError(f"loader exited with code {code}")
            job.status = "completed"
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
        finally:
            job.finished_at = _now_iso()
