from __future__ import annotations

from app.agent.schemas.evidence import SourceCitation
from app.agent.web.ranker import domain_from_url, rank_reliability


def make_citation(*, title: str, url: str, excerpt: str, fetched_at: str, used_for: str, source_status: str = "lida") -> SourceCitation:
    return SourceCitation(
        title=title or url,
        url=url,
        domain=domain_from_url(url),
        reliability=rank_reliability(url),
        used_for=used_for,
        excerpt=" ".join(excerpt.split())[:420],
        fetched_at=fetched_at,
        source_status=source_status,
    )
