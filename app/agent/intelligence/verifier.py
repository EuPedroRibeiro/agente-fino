from __future__ import annotations


BAD_PATTERNS = [
    "nao sou especializado",
    "não sou especializado",
    "como ia nao tenho opiniao",
    "como ia não tenho opinião",
    "isso foge da minha função",
    "o que você acha?",
]


def verify_answer(answer: str, *, intent: str = "general_question", tools: list[str] | None = None) -> dict:
    text = (answer or "").lower()
    issues = [pattern for pattern in BAD_PATTERNS if pattern in text]
    if intent in {"disk_usage", "folder_usage_top"} and "disk_usage" not in (tools or []):
        issues.append("missing_disk_usage_tool")
    if intent == "folder_size" and "folder_size" not in (tools or []):
        issues.append("missing_folder_size_tool")
    return {"approved": not issues, "issues": issues}
