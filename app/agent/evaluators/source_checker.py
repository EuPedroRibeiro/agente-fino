from __future__ import annotations


class SourceChecker:
    def check(self, citations: list) -> dict:
        unread = [source for source in citations if getattr(source, "source_status", "") != "lida"]
        return {
            "ok": len(unread) == 0,
            "unread_count": len(unread),
            "source_count": len(citations),
        }
