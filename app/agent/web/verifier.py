from __future__ import annotations

from app.agent.schemas.evidence import SourceCitation


class WebEvidenceVerifier:
    def verify(self, citations: list[SourceCitation], sensitive_or_current: bool = False) -> dict:
        warnings: list[str] = []
        high_sources = [source for source in citations if source.reliability == "high"]
        read_sources = [source for source in citations if source.source_status == "lida"]
        if sensitive_or_current and len(read_sources) < 2:
            warnings.append("Assunto atual/sensivel com menos de duas fontes lidas.")
        if citations and not high_sources:
            warnings.append("Nenhuma fonte oficial ou de alta confiabilidade foi lida.")
        return {
            "ok": not warnings,
            "warnings": warnings,
            "official_source_available": bool(high_sources),
            "sources_read": len(read_sources),
        }
