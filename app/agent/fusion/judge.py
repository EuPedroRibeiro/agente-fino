from __future__ import annotations


def judge_answer(answer: str) -> dict:
    text = (answer or "").strip()
    return {"approved": bool(text), "issues": [] if text else ["resposta_vazia"]}
