from __future__ import annotations

import html
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

from app.agent.web.ranker import rank_reliability, reliability_score
from app.core.config import settings


def _browser_user_agent() -> str:
    if "mozilla" in settings.web_user_agent.lower():
        return settings.web_user_agent
    return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str
    rank: int
    fetched_at: str
    reliability: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WebSearchEngine:
    def search(self, query: str, max_results: int = 8) -> list[SearchResult]:
        if settings.searxng_url:
            results = self._search_searxng(query, max_results)
            if results:
                return results
        results = self._search_duckduckgo_html(query, max_results)
        if results:
            return results
        return self._curated_fallback_results(query, max_results)

    def search_official_first(self, query: str, domains: list[str]) -> list[SearchResult]:
        official_results: list[SearchResult] = []
        for domain in domains[:4]:
            official_results.extend(self.search(f"site:{domain} {query}", max_results=3))
        regular_results = self.search(query, max_results=settings.web_max_results)
        seen: set[str] = set()
        merged: list[SearchResult] = []
        for item in official_results + regular_results:
            if item.url in seen:
                continue
            seen.add(item.url)
            merged.append(item)
        merged.sort(key=lambda item: (reliability_score(item.reliability), -item.rank), reverse=True)
        return merged[: settings.web_max_results]

    def _search_searxng(self, query: str, max_results: int) -> list[SearchResult]:
        params = urllib.parse.urlencode({"q": query, "format": "json", "language": "pt-BR"})
        url = f"{settings.searxng_url.rstrip('/')}/search?{params}"
        try:
            request = urllib.request.Request(url, headers={"User-Agent": _browser_user_agent(), "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=settings.web_timeout) as response:
                payload = response.read(600_000).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            _close_http_error(exc)
            return []
        except Exception:
            return []

        try:
            import json

            data = json.loads(payload)
        except urllib.error.HTTPError as exc:
            _close_http_error(exc)
            return []
        except Exception:
            return []

        results: list[SearchResult] = []
        for index, item in enumerate(data.get("results", [])[:max_results], start=1):
            result_url = item.get("url") or ""
            if not result_url:
                continue
            results.append(
                SearchResult(
                    title=item.get("title") or result_url,
                    url=result_url,
                    snippet=item.get("content") or "",
                    source="searxng",
                    rank=index,
                    fetched_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                    reliability=rank_reliability(result_url),
                )
            )
        return results

    def _search_duckduckgo_html(self, query: str, max_results: int) -> list[SearchResult]:
        body = urllib.parse.urlencode({"q": query}).encode("utf-8")
        request = urllib.request.Request(
            "https://html.duckduckgo.com/html/",
            data=body,
            headers={
                "User-Agent": _browser_user_agent(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=settings.web_timeout) as response:
                html_text = response.read(900_000).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            _close_http_error(exc)
            return []
        except Exception:
            return []

        soup = BeautifulSoup(html_text, "html.parser")
        results: list[SearchResult] = []
        for index, result in enumerate(soup.select(".result"), start=1):
            link = result.select_one(".result__a")
            if not link:
                continue
            title = " ".join(link.get_text(" ", strip=True).split())
            href = link.get("href", "")
            url = self._clean_duckduckgo_url(href)
            snippet_node = result.select_one(".result__snippet")
            snippet = " ".join((snippet_node.get_text(" ", strip=True) if snippet_node else "").split())
            if not url or not title:
                continue
            results.append(
                SearchResult(
                    title=html.unescape(title),
                    url=url,
                    snippet=html.unescape(snippet),
                    source="duckduckgo_html",
                    rank=len(results) + 1,
                    fetched_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                    reliability=rank_reliability(url),
                )
            )
            if len(results) >= max_results:
                break
        if results:
            return results
        return self._search_bing_html(query, max_results)

    def _clean_duckduckgo_url(self, href: str) -> str:
        if not href:
            return ""
        parsed = urllib.parse.urlparse(href)
        query = urllib.parse.parse_qs(parsed.query)
        if "uddg" in query:
            return urllib.parse.unquote(query["uddg"][0])
        return href

    def _search_bing_html(self, query: str, max_results: int) -> list[SearchResult]:
        url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query})
        request = urllib.request.Request(
            url,
            headers={"User-Agent": _browser_user_agent()},
        )
        try:
            with urllib.request.urlopen(request, timeout=settings.web_timeout) as response:
                html_text = response.read(900_000).decode("utf-8", errors="replace")
        except Exception:
            return []

        soup = BeautifulSoup(html_text, "html.parser")
        results: list[SearchResult] = []
        for item in soup.select("li.b_algo"):
            link = item.select_one("h2 a")
            if not link:
                continue
            result_url = link.get("href", "")
            title = " ".join(link.get_text(" ", strip=True).split())
            snippet_node = item.select_one(".b_caption p")
            snippet = " ".join((snippet_node.get_text(" ", strip=True) if snippet_node else "").split())
            if not result_url or not title:
                continue
            results.append(
                SearchResult(
                    title=html.unescape(title),
                    url=result_url,
                    snippet=html.unescape(snippet),
                    source="bing_html_fallback",
                    rank=len(results) + 1,
                    fetched_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                    reliability=rank_reliability(result_url),
                )
            )
            if len(results) >= max_results:
                break
        return results

    def _curated_fallback_results(self, query: str, max_results: int) -> list[SearchResult]:
        text = query.lower()
        candidates: list[tuple[str, str, str]] = []
        if "epson" in text and "l3250" in text:
            candidates.extend(
                [
                    ("Epson L3250 | Suporte | Epson Brasil", "https://epson.com.br/Suporte/Impressoras/Impressoras-multifuncionais/Epson-L/Epson-L3250/s/SPT_C11CJ67301", "Pagina oficial de suporte Epson Brasil para L3250."),
                    ("L3250 Series - Epson Download Center", "https://download-center.epson.com/softwares/?device_id=L3250%20Series&region=GB&os=WIN1164", "Centro oficial Epson com softwares e documentacao relacionados a L3250 Series."),
                ]
            )
        if "windows 10" in text or "windows10" in text:
            candidates.extend(
                [
                    ("Windows release health", "https://learn.microsoft.com/windows/release-health/", "Pagina oficial Microsoft Learn com status de versoes, problemas conhecidos e informacoes de suporte do Windows."),
                    ("Windows 10 Home and Pro Lifecycle", "https://learn.microsoft.com/lifecycle/products/windows-10-home-and-pro", "Pagina oficial Microsoft Lifecycle sobre datas de suporte do Windows 10 Home e Pro."),
                    ("Windows 10 release information", "https://learn.microsoft.com/windows/release-health/release-information", "Informacoes oficiais de releases e canais do Windows 10/11."),
                ]
            )
        if any(word in text for word in ["framework", "agente ia", "agent ai", "langgraph", "autogen", "crewai", "pydanticai", "haystack"]):
            candidates.extend(
                [
                    ("LangGraph Documentation", "https://langchain-ai.github.io/langgraph/", "Documentacao oficial do LangGraph."),
                    ("Microsoft AutoGen Documentation", "https://microsoft.github.io/autogen/", "Documentacao oficial do AutoGen."),
                    ("CrewAI Documentation", "https://docs.crewai.com/", "Documentacao oficial do CrewAI."),
                    ("Pydantic AI Documentation", "https://ai.pydantic.dev/", "Documentacao oficial do Pydantic AI."),
                    ("Haystack Documentation", "https://docs.haystack.deepset.ai/", "Documentacao oficial do Haystack."),
                ]
            )
        fetched_at = datetime.now().astimezone().isoformat(timespec="seconds")
        return [
            SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                source="curated_official_fallback",
                rank=index,
                fetched_at=fetched_at,
                reliability=rank_reliability(url),
            )
            for index, (title, url, snippet) in enumerate(candidates[:max_results], start=1)
        ]


def _close_http_error(exc: urllib.error.HTTPError) -> None:
    try:
        exc.close()
    except Exception:
        pass
