from __future__ import annotations


def synthesize(primary_answer: str, verifier_notes: list[str] | None = None) -> str:
    notes = [note for note in verifier_notes or [] if note]
    if not notes:
        return primary_answer
    return f"{primary_answer}\n\nVerificacao: " + " ".join(notes)
