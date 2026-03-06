"""
Web search adapter for real-time information during interviews.
Uses a simple search API to fetch current info on technologies, companies, etc.
"""

import logging
from typing import Optional, List, Dict, Any

import httpx

logger = logging.getLogger(__name__)


class WebSearchAdapter:
    """Lightweight web search for interview context enrichment."""

    async def search(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """
        Search the web and return summarised results.
        For MVP this uses DuckDuckGo instant answer API (no key required).
        """
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_html": 1},
                    timeout=10,
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()

            results: List[Dict[str, Any]] = []
            if data.get("AbstractText"):
                results.append({"title": data.get("Heading", ""), "snippet": data["AbstractText"], "url": data.get("AbstractURL", "")})
            for topic in (data.get("RelatedTopics") or [])[:max_results]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({"title": topic.get("Text", "")[:80], "snippet": topic["Text"], "url": topic.get("FirstURL", "")})
            return results[:max_results]
        except Exception:
            logger.exception("Web search failed for query: %s", query)
            return []
