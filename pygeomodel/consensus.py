"""Consensus API client for knowledge-enhanced model Q&A."""

from __future__ import annotations

from typing import Any, Callable

import requests


class ConsensusClient:
    """Small wrapper around the official Consensus quick search API."""

    def __init__(
        self,
        api_key: str | None,
        base_url: str = "https://api.consensus.app/v1",
        request_get: Callable[..., Any] | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._get = request_get or requests.get

    def quick_search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        if not self.api_key:
            raise RuntimeError("CONSENSUS_API_KEY is required for knowledge-enhanced Q&A")
        response = self._get(
            f"{self.base_url}/quick_search",
            headers={"x-api-key": self.api_key},
            params={"query": query},
            timeout=30,
        )
        if response.status_code in {401, 403}:
            raise RuntimeError("Consensus authentication failed. Please check the Consensus API key.")
        response.raise_for_status()
        return self._parse_papers(response.json())[:limit]

    def _parse_papers(self, payload: Any) -> list[dict[str, Any]]:
        raw_papers = []
        if isinstance(payload, list):
            raw_papers = payload
        elif isinstance(payload, dict):
            for key in ("papers", "results", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    raw_papers = value
                    break
            if not raw_papers and isinstance(payload.get("results"), dict):
                raw_papers = payload["results"].get("papers", [])

        papers: list[dict[str, Any]] = []
        for paper in raw_papers:
            if not isinstance(paper, dict):
                continue
            title = paper.get("title") or paper.get("paper_title") or paper.get("name")
            if not title:
                continue
            papers.append(
                {
                    "title": title,
                    "abstract": paper.get("abstract") or paper.get("display_text") or paper.get("text") or "",
                    "journal": paper.get("journal") or paper.get("source") or "",
                    "year": paper.get("year") or paper.get("publication_year") or "",
                    "doi": paper.get("doi") or "",
                    "url": paper.get("url") or paper.get("paper_url") or "",
                }
            )
        return papers
