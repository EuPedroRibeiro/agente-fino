from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass(frozen=True)
class SecretPattern:
    name: str
    regex: re.Pattern[str]
    risk: str
    recommendation: str
    secret_group: int | None = None


PATTERNS: tuple[SecretPattern, ...] = (
    SecretPattern(
        "OpenRouter API Key",
        re.compile(r"\bsk-or-v1-[A-Za-z0-9_-]{24,}\b"),
        "critical",
        "Revogar a chave no OpenRouter e substituir por segredo de ambiente.",
    ),
    SecretPattern(
        "DeepSeek API Key",
        re.compile(r"(?is)\b(?:DEEPSEEK_API_KEY|DEEPSEEK_KEY|deepseek|api\.deepseek\.com)[^\n\r]{0,120}?\b(sk-[A-Za-z0-9]{32,100})\b"),
        "critical",
        "Revogar a chave DeepSeek, gerar uma nova e remover qualquer valor hardcoded.",
        secret_group=1,
    ),
    SecretPattern(
        "OpenAI API Key",
        re.compile(r"(?is)\b(?:OPENAI_API_KEY|OPENAI_KEY|openai)[^\n\r]{0,120}?\b(sk-(?:proj-)?[A-Za-z0-9_-]{24,})\b|\bsk-proj-[A-Za-z0-9_-]{24,}\b"),
        "critical",
        "Revogar a chave imediatamente, gerar uma nova e mover para variavel de ambiente segura.",
    ),
    SecretPattern(
        "GitHub Token",
        re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
        "critical",
        "Revogar o token no GitHub e revisar permissoes concedidas.",
    ),
    SecretPattern(
        "Google/Firebase API Key",
        re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
        "high",
        "Restringir a chave por origem/API e rotacionar se houver exposicao publica.",
    ),
    SecretPattern(
        "AWS Access Key ID",
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        "critical",
        "Desativar a access key, rotacionar credenciais e revisar CloudTrail.",
    ),
    SecretPattern(
        "Bearer/JWT Token",
        re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        "high",
        "Invalidar o token e reduzir tempo de vida/escopo.",
    ),
    SecretPattern(
        "Generic Secret Assignment",
        re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password|passwd)\s*[:=]\s*['\"]?([A-Za-z0-9_./+=:-]{16,})['\"]?"),
        "medium",
        "Mover o segredo para cofre/variavel de ambiente e revisar exposicao.",
        secret_group=1,
    ),
    SecretPattern(
        "Possible AI API Key",
        re.compile(r"\bsk-[A-Za-z0-9]{32,100}\b"),
        "high",
        "Identificar o provedor, revogar se estiver exposta e mover para variavel de ambiente segura.",
    ),
)


def mask_secret(value: str) -> str:
    token = str(value or "")
    if len(token) <= 10:
        return "*" * len(token)
    if token.startswith("sk-proj-"):
        return f"sk-proj-{'*' * max(12, len(token) - 12)}{token[-4:]}"
    if token.startswith("sk-or-v1-"):
        return f"sk-or-v1-{'*' * max(12, len(token) - 13)}{token[-4:]}"
    prefix = token[: min(6, max(2, len(token) // 5))]
    suffix = token[-4:]
    return f"{prefix}{'*' * max(8, len(token) - len(prefix) - len(suffix))}{suffix}"


def risk_rank(risk: str) -> int:
    return {"low": 1, "medium": 2, "high": 3, "critical": 4}.get((risk or "").lower(), 1)


def highest_risk(risks: Iterable[str]) -> str:
    ordered = sorted(((risk_rank(risk), risk) for risk in risks), reverse=True)
    return ordered[0][1] if ordered else "low"


def find_secrets(text: str, *, source: str) -> list[dict]:
    findings: list[dict] = []
    for pattern in PATTERNS:
        for match in pattern.regex.finditer(text or ""):
            raw = _matched_secret(match, pattern)
            line = 1 + (text[: match.start()].count("\n") if text else 0)
            findings.append(
                {
                    "risk": pattern.risk,
                    "type": pattern.name,
                    "source": source,
                    "line": line,
                    "masked_value": mask_secret(raw),
                    "recommendation": pattern.recommendation,
                }
            )
    return dedupe_findings(findings)


def _matched_secret(match: re.Match[str], pattern: SecretPattern) -> str:
    if pattern.secret_group is not None:
        try:
            value = match.group(pattern.secret_group)
            if value:
                return value
        except IndexError:
            pass
    for value in match.groups():
        if value:
            return value
    return match.group(0)


def dedupe_findings(findings: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    unique: list[dict] = []
    for finding in findings:
        key = (finding.get("type"), finding.get("source"), finding.get("line"), finding.get("masked_value"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def public_pattern_catalog() -> list[dict]:
    return [
        {
            "name": pattern.name,
            "risk": pattern.risk,
            "recommendation": pattern.recommendation,
        }
        for pattern in PATTERNS
    ]
