from __future__ import annotations

from app.redlab.models import RANK_THRESHOLDS, RankName


def xp_to_rank(xp: int) -> RankName:
    rank = RankName.RECRUTA
    for candidate, threshold in RANK_THRESHOLDS.items():
        if xp >= threshold:
            rank = candidate
    return rank


def next_rank_progress(xp: int) -> dict:
    ordered = list(RANK_THRESHOLDS.items())
    rank = xp_to_rank(xp)
    index = [item[0] for item in ordered].index(rank)
    if index == len(ordered) - 1:
        return {"rank": rank.value, "next_rank": None, "percent": 100}
    current_floor = ordered[index][1]
    next_rank, next_floor = ordered[index + 1]
    percent = round((xp - current_floor) / max(1, next_floor - current_floor) * 100)
    return {"rank": rank.value, "next_rank": next_rank.value, "percent": max(0, min(100, percent))}
