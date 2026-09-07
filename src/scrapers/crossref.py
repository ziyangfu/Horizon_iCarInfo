"""Crossref academic journal scraper implementation for academic papers."""

import logging
import re
from datetime import datetime, timezone
from typing import List, Optional
import httpx

from .base import BaseScraper
from ..models import ContentItem, CrossrefJournalConfig, SourceType

logger = logging.getLogger(__name__)


class CrossrefScraper(BaseScraper):
    """Scraper for academic journals via Crossref API (e.g. MDPI Vehicles)."""

    CROSSREF_API_BASE = "https://api.crossref.org/journals"

    def __init__(self, config: CrossrefJournalConfig, http_client: httpx.AsyncClient):
        super().__init__(config.model_dump(), http_client)
        self.journal_config = config

    async def fetch(self, since: datetime) -> List[ContentItem]:
        """Fetch papers published in the journal since the given time."""
        if not self.config.get("enabled", True):
            return []

        issn = (self.config.get("issn") or "2624-8921").strip()
        journal_name = self.config.get("journal_name") or "MDPI Vehicles"
        keywords = self.config.get("keywords", [])
        max_results = self.config.get("max_results", 15)
        mailto = self.config.get("mailto") or "horizon-icarinfo@example.com"

        url = f"{self.CROSSREF_API_BASE}/{issn}/works"

        params = {
            "sort": "published",
            "order": "desc",
            "rows": max_results,
        }

        # Date filter on Crossref (filter by publication date)
        since_date_str = since.strftime("%Y-%m-%d")
        params["filter"] = f"from-pub-date:{since_date_str}"

        # Optional keyword query
        if keywords:
            params["query"] = " ".join([kw.strip() for kw in keywords if kw.strip()])

        headers = {
            "User-Agent": f"Horizon-iCarInfo/1.0 (mailto:{mailto})"
        }

        try:
            response = await self.client.get(
                url, params=params, headers=headers, timeout=20.0
            )
            response.raise_for_status()
            data = response.json()
            return self._parse_items(data, since, issn, journal_name)
        except Exception as e:
            logger.error("Error fetching Crossref papers for ISSN %s: %s", issn, e)
            return []

    def _parse_items(
        self,
        data: dict,
        since: datetime,
        issn: str,
        journal_name: str,
    ) -> List[ContentItem]:
        items = []
        if not isinstance(data, dict) or data.get("status") != "ok":
            return []

        raw_items = data.get("message", {}).get("items", [])
        category_tag = self.config.get("category", "mdpi-paper")
        profile_route = self.config.get("profile", "icar-papers")

        for entry in raw_items:
            # 1. Parse publication date
            published_dt = self._extract_published_date(entry)
            if not published_dt or published_dt < since:
                continue

            # 2. Extract DOI & URL
            doi = entry.get("DOI", "").strip()
            item_url = entry.get("URL", f"https://doi.org/{doi}" if doi else "").strip()
            if not doi and not item_url:
                continue

            # 3. Extract title
            titles = entry.get("title", [])
            raw_title = titles[0] if isinstance(titles, list) and titles else str(titles)
            clean_title = " ".join(raw_title.split()).strip()
            if not clean_title:
                clean_title = f"Untitled Paper ({doi})"

            # 4. Extract abstract (strip JATS XML / HTML tags)
            raw_abstract = entry.get("abstract", "") or ""
            clean_abstract = self._clean_abstract(raw_abstract)

            # 5. Extract authors
            authors = []
            for a in entry.get("author", []):
                given = a.get("given", "").strip()
                family = a.get("family", "").strip()
                name = f"{given} {family}".strip() if given or family else a.get("name", "").strip()
                if name:
                    authors.append(name)
            authors_str = ", ".join(authors)

            content_text = (
                f"Journal: {journal_name} (ISSN: {issn})\n"
                f"Authors: {authors_str or 'Unknown'}\n"
                f"DOI: {doi}\n\n"
                f"Abstract: {clean_abstract or 'No abstract provided.'}"
            )

            # Unique ID
            safe_doi = re.sub(r"[^a-zA-Z0-9_-]+", "_", doi).strip("_")
            item_id = self._generate_id("crossref", issn.replace("-", ""), safe_doi)

            # 6. Check Open Access & PDF URL
            is_oa, pdf_url = self._extract_oa_and_pdf(entry, doi, issn, journal_name)

            items.append(
                ContentItem(
                    id=item_id,
                    source_type=SourceType.CROSSREF,
                    title=f"[Paper] {clean_title}",
                    url=item_url,
                    content=content_text,
                    author=authors_str[:100] if authors_str else journal_name,
                    published_at=published_dt,
                    metadata={
                        "doi": doi,
                        "issn": issn,
                        "journal": journal_name,
                        "category": category_tag,
                        "authors": authors,
                        "summary": clean_abstract,
                        "is_oa": is_oa,
                        "pdf_url": pdf_url,
                    },
                    profile=profile_route,
                )
            )

        return items

    @staticmethod
    def _clean_abstract(raw_abstract: str) -> str:
        """Strip JATS XML / HTML tags and normalize whitespace."""
        if not raw_abstract:
            return ""
        # Remove tags like <jats:p>, </jats:title>, <b>, etc.
        text = re.sub(r"<[^>]+>", " ", raw_abstract)
        # Normalize whitespace
        return " ".join(text.split()).strip()

    @staticmethod
    def _extract_published_date(entry: dict) -> Optional[datetime]:
        """Extract publication datetime from Crossref item."""
        # Try published-online, then published, then created
        date_sources = [
            entry.get("published-online"),
            entry.get("published"),
            entry.get("published-print"),
        ]
        for src in date_sources:
            if isinstance(src, dict) and "date-parts" in src:
                parts = src["date-parts"]
                if parts and isinstance(parts[0], list) and len(parts[0]) >= 3:
                    try:
                        year, month, day = parts[0][:3]
                        return datetime(year, month, day, tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

        # Fallback to created date-time
        created = entry.get("created", {})
        if isinstance(created, dict) and "date-time" in created:
            try:
                return datetime.fromisoformat(
                    created["date-time"].replace("Z", "+00:00")
                )
            except ValueError:
                pass

        return None

    @staticmethod
    def _extract_oa_and_pdf(
        entry: dict,
        doi: str,
        issn: str,
        journal_name: str,
    ) -> tuple[bool, Optional[str]]:
        """Determine if work is Open Access and extract direct PDF link."""
        is_oa = False
        pdf_url = None

        # 1. MDPI is 100% Gold Open Access
        if "mdpi" in journal_name.lower() or issn == "2624-8921":
            is_oa = True

        # 2. Check licenses for Creative Commons or Open Access
        licenses = entry.get("license", [])
        for lic in licenses:
            u = lic.get("URL", "").lower()
            if "creativecommons" in u or "open-access" in u:
                is_oa = True
                break

        # 3. Check links for direct PDF
        for link_item in entry.get("link", []):
            url = link_item.get("URL", "")
            content_type = link_item.get("content-type", "").lower()
            if url.endswith(".pdf") or "pdf" in content_type:
                pdf_url = url
                is_oa = True
                break

        # 4. Fallback for MDPI standard PDF URL pattern if link was missing
        if is_oa and not pdf_url and ("mdpi" in journal_name.lower() or issn == "2624-8921"):
            # e.g. DOI 10.3390/vehicles8090210 -> https://www.mdpi.com/2624-8921/8/9/210/pdf
            m = re.match(r"10\.3390/[a-zA-Z]+(\d+)(\d{2})(\d{4})", doi)
            if m:
                vol, issue, page = int(m.group(1)), int(m.group(2)), int(m.group(3))
                pdf_url = f"https://www.mdpi.com/{issn}/{vol}/{issue}/{page}/pdf"
            elif doi.startswith("10.3390/"):
                suffix = doi.split("10.3390/")[-1]
                pdf_url = f"https://www.mdpi.com/{issn}/{suffix}/pdf"

        return is_oa, pdf_url
