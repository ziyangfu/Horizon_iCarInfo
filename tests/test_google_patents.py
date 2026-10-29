"""Tests for Google Patents scraper, patent validation, and profile guard isolation."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai.classifier import ContentClassifier
from src.ai.summarizer import DailySummarizer
from src.models import (
    ClassificationResult,
    ContentAnalysis,
    ContentItem,
    PatentQueryConfig,
    ProcessingResult,
    SourceType,
)
from src.processing import ProfileRegistry
from src.scrapers.google_patents import GooglePatentsScraper


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sample_cluster_response(patents: list[dict]) -> dict:
    results = []
    for i, p in enumerate(patents):
        results.append({
            "id": f"patent/{p.get('publication_number')}/zh",
            "rank": i,
            "patent": p,
        })
    return {
        "results": {
            "total_num_results": len(patents),
            "cluster": [{"result": results}],
        }
    }


def _mock_client(response_data: dict, status_code: int = 200) -> AsyncMock:
    response = MagicMock()
    response.json.return_value = response_data
    response.status_code = status_code
    if status_code >= 400:
        import httpx
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=response
        )
    else:
        response.raise_for_status.return_value = None
    client = AsyncMock()
    client.get.return_value = response
    return client


def test_google_patents_scraper_disabled() -> None:
    client = _mock_client({})
    config = PatentQueryConfig(enabled=False)
    scraper = GooglePatentsScraper(config, client)

    items = asyncio.run(scraper.fetch(_now() - timedelta(days=1)))
    assert items == []
    client.get.assert_not_called()


def test_google_patents_valid_publication_number_check() -> None:
    assert GooglePatentsScraper._is_valid_patent_num("CN120791811B") is True
    assert GooglePatentsScraper._is_valid_patent_num("US20260137286A1") is True
    assert GooglePatentsScraper._is_valid_patent_num("WO2026021196A1") is True
    assert GooglePatentsScraper._is_valid_patent_num("EP3456789A1") is True
    assert GooglePatentsScraper._is_valid_patent_num("invalid_news_id") is False
    assert GooglePatentsScraper._is_valid_patent_num("") is False
    assert GooglePatentsScraper._is_valid_patent_num(None) is False


def test_google_patents_fetch_from_xhr_valid() -> None:
    patent_data = {
        "publication_number": "CN121822331A",
        "title": "一种多域冗余线控转向协同控制方法与系统",
        "assignee": "比亚迪股份有限公司",
        "inventor": "张工",
        "filing_date": "2025-10-10",
        "publication_date": "2026-04-10",
        "snippet": "本发明公开了一种多域冗余线控转向协同控制方法...",
    }
    client = _mock_client(_sample_cluster_response([patent_data]))
    config = PatentQueryConfig(
        enabled=True,
        keywords=["线控转向"],
        assignees=["比亚迪"],
        max_results=5,
    )
    scraper = GooglePatentsScraper(config, client)

    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    items = asyncio.run(scraper.fetch(since))

    assert len(items) == 1
    item = items[0]
    assert item.source_type == SourceType.PATENTS
    assert item.title == "[专利] 一种多域冗余线控转向协同控制方法与系统"
    assert item.author == "比亚迪股份有限公司"
    assert str(item.url) == "https://patents.google.com/patent/CN121822331A/zh"
    assert item.metadata["patent_id"] == "CN121822331A"
    assert item.metadata["publication_number"] == "CN121822331A"
    assert item.metadata["assignee"] == "比亚迪股份有限公司"
    assert item.profile == "icar-patents"


def test_google_patents_empty_when_no_genuine_patents_found() -> None:
    """When both XHR fails (503) and index search returns nothing, return [] without news fallback."""
    client = _mock_client({}, status_code=503)
    config = PatentQueryConfig(enabled=True)
    scraper = GooglePatentsScraper(config, client)

    with patch.object(scraper, "_fetch_from_google_patents_index", return_value=[]):
        items = asyncio.run(scraper.fetch(_now() - timedelta(days=1)))
        assert items == []


def test_google_patents_index_fallback_only_accepts_patent_urls() -> None:
    """Index search must only accept Google Patents URL with valid patent numbers."""
    client = _mock_client({}, status_code=503)
    config = PatentQueryConfig(
        enabled=True,
        keywords=["线控制动", "EMB"],
        assignees=["伯特利"],
    )
    scraper = GooglePatentsScraper(config, client)

    mock_ddgs_results = [
        {
            "href": "https://patents.google.com/patent/CN115107722B/zh",
            "title": "CN115107722B - 一种电子机械制动EMB系统及控制方法 - Google Patents",
            "body": "本发明公开了一种电子机械制动EMB夹紧力控制系统...",
        },
        {
            # A news URL that somehow showed up in search
            "href": "https://auto.gasgoo.com/news/12345.html",
            "title": "伯特利公布全新线控制动专利技术",
            "body": "媒体新闻报道...",
        },
    ]

    with patch("ddgs.DDGS") as mock_ddgs_cls:
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = mock_ddgs_results
        mock_ddgs_cls.return_value = mock_ddgs

        with patch.object(scraper, "_fetch_patent_details", new=AsyncMock(return_value={
            "publication_date": _now().strftime("%Y-%m-%d"),
            "assignee": "伯特利",
            "filing_date": "2026-01-01",
            "abstract": "本发明公开了一种电子机械制动系统。",
        })):
            items = asyncio.run(scraper.fetch(_now() - timedelta(days=1)))

        # Only the 1 genuine Google Patents result must be extracted
        assert len(items) == 1
        assert items[0].metadata["publication_number"] == "CN115107722B"
        assert items[0].source_type == SourceType.PATENTS
        assert items[0].title == "[专利] 一种电子机械制动EMB系统及控制方法"
        assert str(items[0].url) == "https://patents.google.com/patent/CN115107722B/zh"
        assert items[0].metadata["publication_date"] == _now().strftime("%Y-%m-%d")
        assert items[0].author == "伯特利"


@pytest.mark.parametrize("date", [None, "not-a-date", "2026-02-30"])
def test_xhr_rejects_unverifiable_publication_dates(date) -> None:
    client = _mock_client(_sample_cluster_response([{
        "publication_number": "CN119734755A", "title": "线控转向", "publication_date": date,
    }]))
    scraper = GooglePatentsScraper(PatentQueryConfig(), client)
    with patch.object(scraper, "_fetch_patent_details", new=AsyncMock(return_value=None)):
        items = asyncio.run(scraper._fetch_from_google_patents(_now() - timedelta(days=1)))
    assert items == []


@pytest.mark.parametrize("date", ["2014-02-19", "2025-04-01", "2099-01-01"])
def test_index_rejects_old_and_future_publications(date) -> None:
    scraper = GooglePatentsScraper(PatentQueryConfig(), _mock_client({}))
    with patch("ddgs.DDGS") as search, patch.object(scraper, "_fetch_patent_details", new=AsyncMock(return_value={
        "publication_date": date, "assignee": "申请人", "filing_date": "", "abstract": "线控转向",
    })):
        search.return_value.text.return_value = [{"href": "https://patents.google.com/patent/CN119734755A/zh", "title": "线控转向"}]
        items = asyncio.run(scraper._fetch_from_google_patents_index(_now() - timedelta(days=7)))
    assert items == []


@pytest.mark.parametrize("url", [
    "https://evil.example/patents.google.com/patent/CN119734755A",
    "https://patents.google.com.evil.example/patent/CN119734755A",
    "https://patents.google.com/patent/CN119734755A/zh",
])
def test_index_does_not_accept_search_snippets_as_date_evidence(url) -> None:
    scraper = GooglePatentsScraper(PatentQueryConfig(), _mock_client({}))
    with patch("ddgs.DDGS") as search, patch.object(scraper, "_fetch_patent_details", new=AsyncMock(return_value=None)) as details:
        search.return_value.text.return_value = [{"href": url, "title": "线控转向", "body": "Published today"}]
        items = asyncio.run(scraper._fetch_from_google_patents_index(_now() - timedelta(days=1)))
    assert items == []
    if "evil.example" in url:
        details.assert_not_awaited()


def test_patent_page_extracts_official_date_and_applicant() -> None:
    import httpx
    response = httpx.Response(200, text='''
        <meta name="citation_patent_number" content="CN119734755A">
        <meta name="DC.date" content="2025-01-20" scheme="dateSubmitted">
        <time itemprop="publicationDate" datetime="2025-04-01">2025年4月1日</time>
        <dd itemprop="assigneeOriginal">吉利汽车研究院</dd>
        <div itemprop="abstract">本申请提供线控转向系统的摩擦补偿方法。</div>
    ''', request=httpx.Request("GET", "https://patents.google.com/patent/CN119734755A/zh"))
    scraper = GooglePatentsScraper(PatentQueryConfig(), AsyncMock(get=AsyncMock(return_value=response)))
    details = asyncio.run(scraper._fetch_patent_details("CN119734755A"))
    assert details["publication_date"] == "2025-04-01"
    assert details["assignee"] == "吉利汽车研究院"
    assert "摩擦补偿" in details["abstract"]


def test_xhr_accepts_compact_publication_date() -> None:
    client = _mock_client(_sample_cluster_response([{
        "publication_number": "CN119734755A", "title": "线控转向", "publication_date": _now().strftime("%Y%m%d"),
    }]))
    scraper = GooglePatentsScraper(PatentQueryConfig(), client)
    items = asyncio.run(scraper._fetch_from_google_patents(_now() - timedelta(hours=1)))
    assert len(items) == 1
    assert items[0].metadata["publication_date"] == _now().strftime("%Y-%m-%d")


def test_classifier_strictly_isolates_icar_patents() -> None:
    """Non-patent items can NEVER be assigned icar-patents profile."""
    from pathlib import Path
    profiles = ProfileRegistry.load(Path("profiles"), default_profile="icar-info")
    mock_ai = AsyncMock()
    classifier = ContentClassifier(mock_ai, profiles)

    # 1. An RSS item trying to request icar-patents
    rss_item = ContentItem(
        id="rss:gasgoo:123",
        source_type=SourceType.RSS,
        title="华为公布转向专利",
        url="https://auto.gasgoo.com/news/123.html",
        content="华为公布了关于智能底盘转向专利的新闻",
        published_at=_now(),
        profile="icar-patents",  # Attempted override
    )
    resolved_profile = asyncio.run(classifier.resolve(rss_item))
    # Must be forced to fallback/default profile, NEVER icar-patents
    assert resolved_profile.id != "icar-patents"
    assert rss_item.processing.classification.profile != "icar-patents"

    # 2. A genuine PATENTS item
    patent_item = ContentItem(
        id="patents:google:CN121822331A",
        source_type=SourceType.PATENTS,
        title="[专利] 线控转向控制系统",
        url="https://patents.google.com/patent/CN121822331A/zh",
        content="专利说明书",
        published_at=_now(),
    )
    patent_profile = asyncio.run(classifier.resolve(patent_item))
    assert patent_profile.id == "icar-patents"
    assert patent_item.processing.classification.profile == "icar-patents"


def test_summarizer_renders_patent_metadata() -> None:
    summarizer = DailySummarizer(profile_order=["icar-patents"])
    item = ContentItem(
        id="patents:google:CN121822331A",
        source_type=SourceType.PATENTS,
        title="[专利] 多域冗余线控转向协同控制方法与系统",
        url="https://patents.google.com/patent/CN121822331A/zh",
        content="专利正文",
        published_at=_now(),
        metadata={
            "patent_id": "CN121822331A",
            "publication_number": "CN121822331A",
            "assignee": "比亚迪股份有限公司",
            "publication_date": "2026-04-10",
            "category": "chassis-patent",
        },
        profile="icar-patents",
        processing=ProcessingResult(
            classification=ClassificationResult(
                profile="icar-patents",
                method="source_override",
            ),
            analysis=ContentAnalysis(
                score=8.0,
                reason="核心专利",
                summary="测试摘要",
            ),
        ),
    )
    md = asyncio.run(summarizer.generate_summary([item], "2026-09-08", 1, language="zh"))
    assert "Google Patents" in md
    assert "专利号: CN121822331A" in md
    assert "申请人: 比亚迪股份有限公司" in md
    assert "公开日: 2026-04-10" in md
