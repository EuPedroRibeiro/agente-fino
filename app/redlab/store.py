from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.redlab.models import LabStatus, RedLabProgress, RedLabRun, TargetMode
from app.redlab.scoring import xp_to_rank


class RedLabStore:
    def __init__(self) -> None:
        self._runs: dict[str, RedLabRun] = {}
        self._progress: dict[str, RedLabProgress] = {}
        self._lock = Lock()

    def create_run(self, user_id: str, lab_id: str, mode: TargetMode, target_url: str | None = None) -> RedLabRun:
        run = RedLabRun(id=f"red-{uuid4().hex[:12]}", user_id=user_id, lab_id=lab_id, mode=mode, target_url=target_url)
        with self._lock:
            self._runs[run.id] = run
            progress = self._progress.setdefault(user_id, RedLabProgress(user_id=user_id))
            progress.total_runs += 1
            progress.last_active = datetime.now(timezone.utc)
        return run

    def get_run(self, run_id: str) -> RedLabRun | None:
        return self._runs.get(run_id)

    def save_run(self, run: RedLabRun) -> RedLabRun:
        with self._lock:
            self._runs[run.id] = run
        return run

    def progress(self, user_id: str) -> RedLabProgress:
        return self._progress.setdefault(user_id, RedLabProgress(user_id=user_id))

    def award(self, user_id: str, lab_id: str, xp: int, *, vulnerability: bool = False, patch: bool = False) -> RedLabProgress:
        with self._lock:
            progress = self._progress.setdefault(user_id, RedLabProgress(user_id=user_id))
            progress.total_xp += max(0, xp)
            progress.rank = xp_to_rank(progress.total_xp)
            progress.last_active = datetime.now(timezone.utc)
            if lab_id and lab_id not in progress.completed_labs:
                progress.completed_labs.append(lab_id)
            if vulnerability:
                progress.vulnerabilities_found += 1
            if patch:
                progress.patches_applied += 1
        return progress

    def history(self, user_id: str, limit: int = 30) -> list[RedLabRun]:
        runs = [run for run in self._runs.values() if run.user_id == user_id]
        return sorted(runs, key=lambda run: run.started_at, reverse=True)[:limit]

    def leaderboard(self, limit: int = 20) -> list[RedLabProgress]:
        return sorted(self._progress.values(), key=lambda item: item.total_xp, reverse=True)[:limit]


store = RedLabStore()
