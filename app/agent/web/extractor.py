from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup


@dataclass
class ExtractedPage:
    title: str
    text: str
    language: str


def extract_text(html_text: str, max_chars: int = 8000) -> ExtractedPage:
    soup = BeautifulSoup(html_text, "html.parser")
    for node in soup(["script", "style", "noscript", "svg", "canvas"]):
        node.decompose()
    title = " ".join((soup.title.get_text(" ", strip=True) if soup.title else "").split()) or "Sem titulo"
    lang = soup.html.get("lang", "indefinido") if soup.html else "indefinido"
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return ExtractedPage(title=title[:250], text=text[:max_chars], language=lang)
