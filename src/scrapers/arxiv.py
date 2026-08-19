"""ArXiv scraper implementation for academic papers."""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List
import httpx

from .base import BaseScraper
from ..models import ArXivConfig, ContentItem, SourceType

logger = logging.getLogger(__name__)


class ArXivScraper(BaseScraper):
    """Scraper for ArXiv academic papers."""

    ARXIV_API_URL = "https://export.arxiv.org/api/query"

    def __init__(self, config: ArXivConfig, http_client: httpx.AsyncClient):
        super().__init__(config.model_dump(), http_client)
        self.arxiv_config = config

    async def fetch(self, since: datetime) -> List[ContentItem]:
        """Fetch papers published or updated since the given time."""
        if not self.config.get("enabled", True):
            return []

        categories = self.config.get(
            "categories", ["cs.RO", "cs.CV", "eess.SY", "cs.SY"]
        )
        keywords = self.config.get("keywords", [])
        max_results = self.config.get("max_results", 30)

        # Build search query
        cat_query = " OR ".join([f"cat:{c.strip()}" for c in categories if c.strip()])
        if not cat_query:
            cat_query = "cat:cs.RO"

        if keywords:
            kw_query = " OR ".join([f'all:"{kw.strip()}"' for kw in keywords if kw.strip()])
            search_query = f"({cat_query}) AND ({kw_query})"
        else:
            search_query = f"({cat_query})"

        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        try:
            response = await self.client.get(
                self.ARXIV_API_URL, params=params, timeout=15.0
            )
            response.raise_for_status()
            return self._parse_feed(response.text, since)
        except Exception as e:
            logger.error("Error fetching ArXiv papers: %s", e)
            return []

    def _parse_feed(self, xml_data: str, since: datetime) -> List[ContentItem]:
        items = []
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError as e:
            logger.error("Error parsing ArXiv XML: %s", e)
            return []

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }

        category_tag = self.config.get("category", "academic-paper")
        profile_route = self.config.get("profile")

        for entry in root.findall("atom:entry", ns):
            published_str = entry.findtext("atom:published", default="", namespaces=ns)
            if not published_str:
                continue

            try:
                published_dt = datetime.fromisoformat(
                    published_str.replace("Z", "+00:00")
                )
            except ValueError:
                continue

            if published_dt < since:
                continue

            entry_id = entry.findtext("atom:id", default="", namespaces=ns).strip()
            arxiv_id = entry_id.split("/")[-1] if entry_id else "unknown"

            title = entry.findtext("atom:title", default="", namespaces=ns).strip()
            title = " ".join(title.split())  # Clean newlines and extra spaces

            summary = entry.findtext("atom:summary", default="", namespaces=ns).strip()
            summary = " ".join(summary.split())

            authors = [
                a.findtext("atom:name", default="", namespaces=ns).strip()
                for a in entry.findall("atom:author", ns)
            ]
            authors_str = ", ".join([a for a in authors if a])

            pdf_url = entry_id
            for link in entry.findall("atom:link", ns):
                if link.attrib.get("title") == "pdf":
                    pdf_url = link.attrib.get("href", entry_id)
                    break

            content_text = f"Authors: {authors_str}\n\nAbstract: {summary}"

            items.append(
                ContentItem(
                    id=self._generate_id("arxiv", "paper", arxiv_id),
                    source_type=SourceType.ARXIV,
                    title=f"[Paper] {title}",
                    url=pdf_url or entry_id,
                    content=content_text,
                    author=authors_str[:100] if authors_str else "ArXiv",
                    published_at=published_dt,
                    metadata={
                        "arxiv_id": arxiv_id,
                        "category": category_tag,
                        "authors": authors,
                        "summary": summary,
                    },
                    profile=profile_route,
                )
            )

        return items
