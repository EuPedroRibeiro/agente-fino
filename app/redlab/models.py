from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LabDifficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class LabStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TargetMode(str, Enum):
    SANDBOX = "sandbox"
    REAL_TARGET = "real_target"


class RankName(str, Enum):
    RECRUTA = "Recruta"
    ANALISTA = "Analista"
    OPERADOR = "Operador"
    RED_TEAM = "Red Team"
    ELITE = "Elite"
    FINO_SPECTER = "Fino Specter"


RANK_THRESHOLDS = {
    RankName.RECRUTA: 0,
    RankName.ANALISTA: 100,
    RankName.OPERADOR: 300,
    RankName.RED_TEAM: 700,
    RankName.ELITE: 1500,
    RankName.FINO_SPECTER: 3000,
}


class LabBriefing(BaseModel):
    title: str
    description: str
    difficulty: LabDifficulty
    category: str
    objectives: list[str]
    hints: list[str]
    xp_reward: int


class LabResult(BaseModel):
    lab_id: str
    status: LabStatus
    technique_used: str
    payload_preview: str
    vulnerability_found: bool
    evidence: str
    response_summary: str
    xp_earned: int = 0


class PatchResult(BaseModel):
    lab_id: str
    patch_applied: bool
    patch_diff: str
    tests_passed: int
    tests_total: int
    regressions: list[str] = Field(default_factory=list)


class TargetScanResult(BaseModel):
    technique: str
    status: str
    evidence: str
    recommendation: str


class RedLabRun(BaseModel):
    id: str
    user_id: str
    lab_id: str
    mode: TargetMode
    target_url: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    status: LabStatus = LabStatus.IN_PROGRESS
    xp_earned: int = 0
    results: list[LabResult] = Field(default_factory=list)
    patch: PatchResult | None = None
    target_results: list[TargetScanResult] = Field(default_factory=list)


class RedLabProgress(BaseModel):
    user_id: str
    total_xp: int = 0
    rank: RankName = RankName.RECRUTA
    completed_labs: list[str] = Field(default_factory=list)
    total_runs: int = 0
    vulnerabilities_found: int = 0
    patches_applied: int = 0
    last_active: datetime = Field(default_factory=utc_now)


class RedLabReport(BaseModel):
    run: dict[str, Any]
    progress: dict[str, Any]
    generated_at: datetime = Field(default_factory=utc_now)
