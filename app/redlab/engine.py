from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.agent.security.sanitizer import mask_secrets
from app.redlab.labs import LABS, LABS_BY_ID, public_lab
from app.redlab.models import LabResult, LabStatus, PatchResult, RedLabReport, TargetMode
from app.redlab.scoring import next_rank_progress
from app.redlab.store import RedLabStore, store
from app.redlab.target_engine import RedLabTargetEngine


class RedLabEngine:
    def __init__(self, run_store: RedLabStore | None = None, target_engine: RedLabTargetEngine | None = None) -> None:
        self.store = run_store or store
        self.target_engine = target_engine or RedLabTargetEngine()

    def status(self) -> dict[str, Any]:
        return {
            "active": True,
            "version": "1.0.0",
            "labs": len(LABS),
            "sandbox_mode": "simulated_isolated",
            "target": self.target_engine.status(),
        }

    def list_labs(self) -> list[dict]:
        return [public_lab(lab) for lab in LABS]

    def start(self, user_id: str, lab_id: str, mode: str = "sandbox", target_url: str | None = None) -> dict:
        parsed_mode = TargetMode(mode)
        if parsed_mode is TargetMode.SANDBOX and lab_id not in LABS_BY_ID:
            raise ValueError("Laboratorio nao encontrado.")
        run = self.store.create_run(user_id, lab_id, parsed_mode, target_url)
        return {"run": run.model_dump(mode="json"), "progress": self.progress(user_id)}

    def validate_lab(self, user_id: str, run_id: str, lab_id: str, payload: str) -> dict:
        run = self._owned_run(user_id, run_id)
        lab = LABS_BY_ID.get(lab_id)
        if not lab or run.lab_id != lab_id or run.mode is not TargetMode.SANDBOX:
            raise ValueError("Run ou laboratorio invalido.")
        clean_payload = payload[:2000]
        matched, evidence, response = lab.matcher(clean_payload)
        result = LabResult(
            lab_id=lab_id,
            status=LabStatus.COMPLETED if matched else LabStatus.FAILED,
            technique_used=lab.briefing.category,
            payload_preview=mask_secrets(clean_payload[:240]),
            vulnerability_found=matched,
            evidence=evidence,
            response_summary=response,
            xp_earned=lab.briefing.xp_reward if matched else 0,
        )
        run.results.append(result)
        if matched:
            run.status = LabStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            run.xp_earned += result.xp_earned
            self.store.award(user_id, lab_id, result.xp_earned, vulnerability=True)
        self.store.save_run(run)
        return {"result": result.model_dump(mode="json"), "progress": self.progress(user_id)}

    def patch(self, user_id: str, run_id: str, lab_id: str) -> dict:
        run = self._owned_run(user_id, run_id)
        lab = LABS_BY_ID.get(lab_id)
        if not lab or run.lab_id != lab_id:
            raise ValueError("Run ou laboratorio invalido.")
        patch = PatchResult(
            lab_id=lab_id,
            patch_applied=True,
            patch_diff=lab.patch_diff,
            tests_passed=len(lab.regression_tests),
            tests_total=len(lab.regression_tests),
        )
        run.patch = patch
        self.store.save_run(run)
        self.store.award(user_id, lab_id, 25, patch=True)
        return {"patch": patch.model_dump(mode="json"), "progress": self.progress(user_id)}

    def target_scan(self, user_id: str, url: str, techniques: list[str], confirmed: bool) -> dict:
        run = self.store.create_run(user_id, "target_preflight", TargetMode.REAL_TARGET, url)
        results = self.target_engine.scan(url, techniques, confirmed)
        run.target_results = results
        run.status = LabStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc)
        self.store.save_run(run)
        return {"run_id": run.id, "results": [item.model_dump(mode="json") for item in results], "progress": self.progress(user_id)}

    def report(self, user_id: str, run_id: str) -> dict:
        run = self._owned_run(user_id, run_id)
        report = RedLabReport(run=mask_secrets(run.model_dump(mode="json")), progress=self.progress(user_id))
        return report.model_dump(mode="json")

    def history(self, user_id: str, limit: int = 30) -> list[dict]:
        return [mask_secrets(run.model_dump(mode="json")) for run in self.store.history(user_id, limit)]

    def progress(self, user_id: str) -> dict:
        progress = self.store.progress(user_id)
        return {**progress.model_dump(mode="json"), **next_rank_progress(progress.total_xp)}

    def leaderboard(self, limit: int = 20) -> list[dict]:
        return [item.model_dump(mode="json") for item in self.store.leaderboard(limit)]

    def _owned_run(self, user_id: str, run_id: str):
        run = self.store.get_run(run_id)
        if not run or run.user_id != user_id:
            raise ValueError("Run nao encontrada.")
        return run
