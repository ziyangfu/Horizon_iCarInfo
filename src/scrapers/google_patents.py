"""Google Patents scraper implementation for genuine patent documents only."""

import html
import logging
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import httpx

from .base import BaseScraper
from ..models import ContentItem, PatentQueryConfig, SourceType

logger = logging.getLogger(__name__)

# Valid patent publication number regex (e.g. CN114735076B, US20260137286A1, WO2026021196A1)
PATENT_PUB_NUM_REGEX = re.compile(r"^[A-Z]{2}[0-9A-Z]{5,}$")


class GooglePatentsScraper(BaseScraper):
    """Scraper strictly for genuine patent publications.

    Primary: Google Patents XHR query endpoint (https://patents.google.com/xhr/query).
    Fallback: Direct Google Patents index retrieval (site:patents.google.com/patent/)
    via search syndication when Google Patents blocks raw HTTP requests (503 / CAPTCHA).

    Guaranteed constraint: All returned items MUST be authentic patent documents with
    official publication numbers and Google Patents links. Never returns news articles.
    """

    SOURCE_TYPE = SourceType.PATENTS
    GOOGLE_PATENTS_XHR_URL = "https://patents.google.com/xhr/query"

    def __init__(self, config: PatentQueryConfig, http_client: httpx.AsyncClient):
        super().__init__({"patents": config}, http_client)
        self.patent_config = config

    @staticmethod
    def _clean_text(raw_text: Optional[str]) -> str:
        """Strip HTML tags, unescape HTML entities, and normalize whitespace."""
        if not raw_text:
            return ""
        text = re.sub(r"<[^>]+>", " ", raw_text)
        text = html.unescape(text)
        return " ".join(text.split()).strip()

    @staticmethod
    def _is_valid_patent_num(num: Optional[str]) -> bool:
        """Verify that a string looks like an authentic patent publication number."""
        if not num:
            return False
        clean = num.strip().replace("-", "").replace("/", "")
        return bool(PATENT_PUB_NUM_REGEX.match(clean))

    def _build_google_patents_query(self) -> str:
        """Build single-encoded query string for Google Patents XHR."""
        parts = []
        keywords = self.patent_config.keywords
        assignees = self.patent_config.assignees

        if keywords:
            kw_or = " OR ".join([f'"{k.strip()}"' for k in keywords[:8] if k.strip()])
            parts.append(f"({kw_or})")

        if assignees:
            as_or = " OR ".join([f'assignee:"{a.strip()}"' for a in assignees[:8] if a.strip()])
            parts.append(f"({as_or})")

        query_str = " ".join(parts) if parts else "chassis"
        return f"q={query_str}&sort=new&num={self.patent_config.max_results}"

    async def fetch(self, since: datetime) -> List[ContentItem]:
        """Fetch authentic patent items published since the given time."""
        if not self.patent_config.enabled:
            return []

        # Attempt 1: Google Patents XHR query
        try:
            items = await self._fetch_from_google_patents(since)
            if items:
                logger.info("Google Patents XHR returned %d genuine patent items", len(items))
                return items
        except Exception as e:
            logger.warning("Google Patents XHR query failed (%s); trying Google Patents index fallback", e)

        # Attempt 2: Fallback to Google Patents index search (site:patents.google.com/patent/)
        try:
            items = await self._fetch_from_google_patents_index(since)
            if items:
                logger.info("Google Patents index search returned %d genuine patent items", len(items))
                return items
        except Exception as e:
            logger.error("Google Patents index search failed: %s", e)

        # Invariant: If no genuine patents are found, return empty list.
        # NEVER fall back to news or blogs.
        return []

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
            if not self._is_valid_patent_num(pub_num):
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

            # Filter by since date if publication date is available
            if pub_date_str and pub_dt < since:
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

    async def _fetch_from_google_patents_index(self, since: datetime) -> List[ContentItem]:
        """Fallback: Retrieve genuine Google Patents documents via site-specific search."""
        try:
            from ddgs import DDGS
        except ImportError:
            logger.warning("ddgs package not installed; skipping Google Patents index search")
            return []

        keywords = self.patent_config.keywords or [
            "整车运动控制", "运动控制", "智能控制", "线控转向", "线控制动", "EMB", "主动悬架"
        ]
        assignees = self.patent_config.assignees or [
            "伯特利", "同驭", "拿森", "博世", "采埃孚", "比亚迪", "华为"
        ]

        # Construct focused thematic queries on Google Patents domain
        kw_chunk = " OR ".join(keywords[:6])
        as_chunk = " OR ".join(assignees[:6])
        search_queries = [
            f"site:patents.google.com/patent/ ({kw_chunk}) ({as_chunk})",
            f"site:patents.google.com/patent/ (整车运动控制 OR 运动控制 OR 智能控制) (比亚迪 OR 华为 OR 地平线 OR 蔚来)",
        ]

        category_tag = self.patent_config.category or "chassis-patent"
        profile_route = self.patent_config.profile or "icar-patents"
        items: List[ContentItem] = []
        seen_pub_nums: Set[str] = set()

        ddgs = DDGS()
        for query in search_queries:
            try:
                results = list(ddgs.text(query, max_results=self.patent_config.max_results))
            except Exception as e:
                logger.warning("Search query failed for '%s': %s", query, e)
                continue

            for r in results:
                url = r.get("href", "")
                m = re.search(r"patents\.google\.com/patent/([A-Z]{2}[0-9A-Z]+)", url)
                if not m:
                    continue

                pub_num = m.group(1).upper()
                if not self._is_valid_patent_num(pub_num) or pub_num in seen_pub_nums:
                    continue
                seen_pub_nums.add(pub_num)

                raw_title = r.get("title", "")
                # Clean Google Patents title format: "CN123456A - Title - Google Patents"
                clean_title = re.sub(r"^[A-Z]{2}[0-9A-Z]+\s*[-–—]\s*", "", raw_title)
                clean_title = re.sub(r"\s*[-–—]\s*Google\s+Patent.*$", "", clean_title, flags=re.IGNORECASE).strip()
                clean_title = clean_title.rstrip(". \t\n")
                if not clean_title or clean_title.startswith("patents.google.com"):
                    clean_title = f"专利 {pub_num}"
                if not clean_title.startswith("[专利]") and not clean_title.startswith("[Patent]"):
                    clean_title = f"[专利] {clean_title}"

                snippet = self._clean_text(r.get("body", ""))

                # Deduce assignee from matching keywords in snippet/title or assignees list
                matched_assignee = "未知申请人"
                assignee_match = re.search(r"(?:申请人|专利权人)[：:]\s*([^\s,，。；;]+)", snippet)
                if assignee_match:
                    matched_assignee = assignee_match.group(1).strip()
                else:
                    for a in assignees:
                        if a in snippet or a in clean_title:
                            matched_assignee = a
                            break

                pub_dt = datetime.now(timezone.utc)
                patent_url = f"https://patents.google.com/patent/{pub_num}/zh"

                content_parts = [
                    f"专利号: {pub_num}",
                    f"申请人 / 专利权人: {matched_assignee}",
                ]
                if snippet:
                    content_parts.append(f"\n摘要与方案简述:\n{snippet}")

                content_text = "\n".join(content_parts)

                items.append(
                    ContentItem(
                        id=self._generate_id("patents", "google", pub_num),
                        source_type=self.SOURCE_TYPE,
                        title=clean_title,
                        url=patent_url,
                        content=content_text,
                        author=matched_assignee[:100],
                        published_at=pub_dt,
                        metadata={
                            "patent_id": pub_num,
                            "publication_number": pub_num,
                            "assignee": matched_assignee,
                            "category": category_tag,
                            "summary": snippet,
                        },
                        profile=profile_route,
                    )
                )

                if len(items) >= self.patent_config.max_results:
                    break

            if len(items) >= self.patent_config.max_results:
                break

        return items[: self.patent_config.max_results]
