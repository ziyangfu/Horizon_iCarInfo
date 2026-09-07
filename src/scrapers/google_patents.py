"""Google Patents scraper implementation with resilience fallback."""

import html
import logging
import re
import urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

import feedparser
import httpx

from .base import BaseScraper
from ..models import ContentItem, PatentQueryConfig, SourceType

logger = logging.getLogger(__name__)


class GooglePatentsScraper(BaseScraper):
    """Scraper for patent publications and disclosures.
    
    Primary: Google Patents XHR query API (https://patents.google.com/xhr/query).
    Fallback: Open Patent / IP Syndication search (https://news.google.com/rss/search)
    when Google Patents is rate-limited or CAPTCHA-challenged (503/timeout).
    """

    SOURCE_TYPE = SourceType.PATENTS
    GOOGLE_PATENTS_XHR_URL = "https://patents.google.com/xhr/query"
    FALLBACK_RSS_URL = "https://news.google.com/rss/search"

    def __init__(self, config: PatentQueryConfig, http_client: httpx.AsyncClient):
        super().__init__({"patents": config}, http_client)
        self.patent_config = config

    @staticmethod
    def _clean_text(raw_text: Optional[str]) -> str:
        """Strip HTML tags and unescape HTML entities."""
        if not raw_text:
            return ""
        text = re.sub(r"<[^>]+>", "", raw_text)
        return html.unescape(text).strip()

    def _build_google_patents_query(self) -> str:
        """Build query string for Google Patents."""
        parts = []
        keywords = self.patent_config.keywords
        assignees = self.patent_config.assignees

        if keywords:
            kw_or = " OR ".join([f'"{k.strip()}"' for k in keywords if k.strip()])
            parts.append(f"({kw_or})")

        if assignees:
            as_or = " OR ".join([f'assignee:"{a.strip()}"' for a in assignees if a.strip()])
            parts.append(f"({as_or})")

        query_str = " AND ".join(parts) if parts else "chassis"
        return f"q={urllib.parse.quote(query_str)}&sort=new&num={self.patent_config.max_results}"

    async def fetch(self, since: datetime) -> List[ContentItem]:
        """Fetch patent items published since the given time."""
        if not self.patent_config.enabled:
            return []

        # Attempt 1: Google Patents XHR query
        try:
            items = await self._fetch_from_google_patents(since)
            if items:
                logger.info("Google Patents XHR returned %d patent items", len(items))
                return items
        except Exception as e:
            logger.warning("Google Patents XHR query failed (%s); switching to patent syndication fallback", e)

        # Attempt 2: Fallback to Patent & IP Syndication search
        return await self._fetch_from_patent_syndication(since)

    async def _fetch_from_google_patents(self, since: datetime) -> List[ContentItem]:
        """Fetch patents directly from Google Patents XHR endpoint."""
        inner_query = self._build_google_patents_query()
        xhr_url = f"{self.GOOGLE_PATENTS_XHR_URL}?url={urllib.parse.quote(inner_query)}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://patents.google.com/",
        }

        response = await self.client.get(xhr_url, headers=headers, timeout=15.0)
        if response.status_code == 503:
            raise httpx.HTTPStatusError("Google Patents 503 rate-limited", request=response.request, response=response)
        response.raise_for_status()

        data = response.json()
        cluster = data.get("results", {}).get("cluster", [])
        if not cluster:
            return []

        raw_results = cluster[0].get("result", [])
        items: List[ContentItem] = []
        category_tag = self.patent_config.category or "chassis-patent"
        profile_route = self.patent_config.profile or "icar-patents"

        for entry in raw_results:
            patent = entry.get("patent", {})
            pub_num = patent.get("publication_number")
            if not pub_num:
                continue

            raw_title = patent.get("title", "Untitled Patent")
            title = self._clean_text(raw_title)
            if not title.startswith("[专利]") and not title.startswith("[Patent]"):
                title = f"[专利] {title}"

            assignee = self._clean_text(patent.get("assignee", "Unknown Assignee"))
            inventor = self._clean_text(patent.get("inventor", ""))
            snippet = self._clean_text(patent.get("snippet", ""))

            pub_date_str = patent.get("publication_date")
            filing_date_str = patent.get("filing_date")

            pub_dt = datetime.now(timezone.utc)
            if pub_date_str:
                try:
                    pub_dt = datetime.strptime(pub_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    pass

            # Filter by since date if applicable
            if pub_dt < since:
                continue

            patent_url = f"https://patents.google.com/patent/{pub_num}/zh"

            content_parts = [
                f"专利号: {pub_num}",
                f"申请人 / 专利权人: {assignee}",
            ]
            if inventor:
                content_parts.append(f"发明人: {inventor}")
            if filing_date_str:
                content_parts.append(f"申请日: {filing_date_str}")
            if pub_date_str:
                content_parts.append(f"公开日: {pub_date_str}")
            if snippet:
                content_parts.append(f"\n摘要与方案简述:\n{snippet}")

            content_text = "\n".join(content_parts)

            items.append(
                ContentItem(
                    id=self._generate_id("patents", "google", pub_num),
                    source_type=self.SOURCE_TYPE,
                    title=title,
                    url=patent_url,
                    content=content_text,
                    author=assignee[:100],
                    published_at=pub_dt,
                    metadata={
                        "patent_id": pub_num,
                        "publication_number": pub_num,
                        "assignee": assignee,
                        "inventor": inventor,
                        "filing_date": filing_date_str,
                        "publication_date": pub_date_str,
                        "category": category_tag,
                    },
                    profile=profile_route,
                )
            )

        return items[: self.patent_config.max_results]

    async def _fetch_from_patent_syndication(self, since: datetime) -> List[ContentItem]:
        """Fallback: Fetch recent patent disclosures via syndicated patent news/releases."""
        keywords = self.patent_config.keywords or ["线控底盘", "线控转向", "线控制动", "EMB", "智能底盘"]
        assignees = self.patent_config.assignees or ["伯特利", "同驭", "拿森", "博世", "采埃孚", "大陆", "比亚迪"]

        kw_query = " OR ".join(keywords[:5])
        as_query = " OR ".join(assignees[:6])
        query = f"专利 ({kw_query}) ({as_query})"

        url = f"{self.FALLBACK_RSS_URL}?q={urllib.parse.quote(query)}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"

        try:
            response = await self.client.get(url, timeout=15.0)
            response.raise_for_status()
            feed = feedparser.parse(response.text)
        except Exception as e:
            logger.error("Error fetching patent syndication feed: %s", e)
            return []

        items: List[ContentItem] = []
        category_tag = self.patent_config.category or "chassis-patent"
        profile_route = self.patent_config.profile or "icar-patents"

        for entry in feed.entries[: self.patent_config.max_results]:
            title = self._clean_text(entry.get("title", ""))
            if not title:
                continue
            if not title.startswith("[专利]") and not title.startswith("[Patent]"):
                title = f"[专利] {title}"

            link = entry.get("link", "")
            summary = self._clean_text(entry.get("summary", title))

            published_dt = datetime.now(timezone.utc)
            if entry.get("published"):
                try:
                    published_dt = parsedate_to_datetime(entry.published)
                    if published_dt.tzinfo is None:
                        published_dt = published_dt.replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            source_name = "专利前瞻资讯"
            if entry.get("source", {}).get("title"):
                source_name = entry.source.title

            native_id = entry.get("id") or link or title
            clean_id = re.sub(r"[^a-zA-Z0-9_-]+", "", native_id)[-32:]

            content_text = f"来源与主体: {source_name}\n发布时间: {published_dt:%Y-%m-%d %H:%M}\n\n专利公开与方案说明:\n{summary}"

            items.append(
                ContentItem(
                    id=self._generate_id("patents", "disclosure", clean_id or "item"),
                    source_type=self.SOURCE_TYPE,
                    title=title,
                    url=link,
                    content=content_text,
                    author=source_name[:100],
                    published_at=published_dt,
                    metadata={
                        "patent_id": clean_id,
                        "source_name": source_name,
                        "category": category_tag,
                    },
                    profile=profile_route,
                )
            )

        return items
