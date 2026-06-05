from __future__ import annotations

from urllib.parse import urlparse


HIGH_RELIABILITY_DOMAINS = [
    "learn.microsoft.com",
    "support.microsoft.com",
    "microsoft.com",
    "brother.com",
    "support.brother.com",
    "epson.com",
    "epson.com.br",
    "epson.eu",
    "epson.co.in",
    "download-center.epson.com",
    "support.epson.net",
    "hp.com",
    "support.hp.com",
    "dell.com",
    "lenovo.com",
    "acer.com",
    "intel.com",
    "amd.com",
    "nvidia.com",
    "docs.python.org",
    "fastapi.tiangolo.com",
    "github.com",
    "langchain-ai.github.io",
    "microsoft.github.io",
    "docs.crewai.com",
    "ai.pydantic.dev",
    "pydantic.dev",
    "docs.haystack.deepset.ai",
    "nvd.nist.gov",
    "cve.org",
]

MEDIUM_RELIABILITY_DOMAINS = [
    "stackoverflow.com",
    "serverfault.com",
    "superuser.com",
    "reddit.com",
    "community.spiceworks.com",
]


def domain_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower().removeprefix("www.")


def rank_reliability(url: str) -> str:
    domain = domain_from_url(url)
    if any(domain == official or domain.endswith(f".{official}") for official in HIGH_RELIABILITY_DOMAINS):
        return "high"
    if any(domain == known or domain.endswith(f".{known}") for known in MEDIUM_RELIABILITY_DOMAINS):
        return "medium"
    return "low"


def reliability_score(reliability: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(reliability, 0)
