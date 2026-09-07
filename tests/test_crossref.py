"""Tests for Crossref academic journal scraper and balanced digest quota."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models import (
    AIConfig,
    CategoryGroupConfig,
    ClassificationResult,
    Config,
    ContentAnalysis,
    ContentItem,
    CrossrefJournalConfig,
    DigestConfig,
    ProcessingResult,
    ProcessingConfig,
    SourceType,
    SourcesConfig,
)
from src.orchestrator import HorizonOrchestrator
from src.scrapers.crossref import CrossrefScraper


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _mock_crossref_response(items: list[dict]) -> dict:
    return {
        "status": "ok",
        "message-type": "work-list",
        "message": {
            "total-results": len(items),
            "items": items,
        },
    }


def _sample_crossref_item(
    doi: str = "10.3390/vehicles8090210",
    title: str = "Quantifying Autonomous Trajectory Tracking: A Real-Vehicle Comparison",
    abstract: str = "<jats:p>This study investigates <jats:bold>vehicle motion control</jats:bold> strategies.</jats:p>",
    authors: list[dict] | None = None,
    pub_date: list[int] | None = None,
    link: list[dict] | None = None,
) -> dict:
    if authors is None:
        authors = [
            {"given": "Mei", "family": "Cao"},
            {"given": "Xinjian", "family": "Yuan"},
        ]
    if pub_date is None:
        now = _now()
        pub_date = [now.year, now.month, now.day]
    if link is None:
        link = [
            {
                "URL": f"https://www.mdpi.com/2624-8921/8/9/210/pdf",
                "content-type": "application/pdf",
            }
        ]

    return {
        "DOI": doi,
        "URL": f"https://doi.org/{doi}",
        "title": [title],
        "abstract": abstract,
        "author": authors,
        "published": {
            "date-parts": [pub_date]
        },
        "published-online": {
            "date-parts": [pub_date]
        },
        "link": link,
    }


def _mock_client(response_data: dict) -> AsyncMock:
    response = MagicMock()
    response.json.return_value = response_data
    response.status_code = 200
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.get.return_value = response
    return client


def test_crossref_scraper_disabled() -> None:
    client = _mock_client({})
    config = CrossrefJournalConfig(enabled=False)
    scraper = CrossrefScraper(config, client)

    items = asyncio.run(scraper.fetch(_now() - timedelta(days=1)))
    assert items == []
    client.get.assert_not_called()


def test_crossref_scraper_clean_abstract() -> None:
    raw = "<jats:p>First paragraph.</jats:p><jats:p>Second with <jats:italic>italic</jats:italic> text.</jats:p>"
    cleaned = CrossrefScraper._clean_abstract(raw)
    assert cleaned == "First paragraph. Second with italic text."


def test_crossref_scraper_fetch_valid() -> None:
    now = _now()
    item_data = _sample_crossref_item(
        doi="10.3390/vehicles8090210",
        title="  Trajectory Tracking with Steer-by-Wire  \n System ",
        abstract="<jats:p>Real-vehicle experiments on <jats:bold>chassis</jats:bold> control.</jats:p>",
        pub_date=[now.year, now.month, now.day],
    )
    client = _mock_client(_mock_crossref_response([item_data]))
    config = CrossrefJournalConfig(
        enabled=True,
        issn="2624-8921",
        journal_name="MDPI Vehicles",
        category="mdpi-paper",
        profile="icar-papers",
    )
    scraper = CrossrefScraper(config, client)

    since = now - timedelta(days=2)
    items = asyncio.run(scraper.fetch(since))

    assert len(items) == 1
    item = items[0]
    assert item.source_type == SourceType.CROSSREF
    assert item.title == "[Paper] Trajectory Tracking with Steer-by-Wire System"
    assert item.author == "Mei Cao, Xinjian Yuan"
    assert str(item.url) == "https://doi.org/10.3390/vehicles8090210"
    assert item.metadata["doi"] == "10.3390/vehicles8090210"
    assert item.metadata["issn"] == "2624-8921"
    assert item.metadata["journal"] == "MDPI Vehicles"
    assert item.metadata["category"] == "mdpi-paper"
    assert item.metadata["summary"] == "Real-vehicle experiments on chassis control."
    assert item.metadata["is_oa"] is True
    assert item.metadata["pdf_url"] == "https://www.mdpi.com/2624-8921/8/9/210/pdf"
    assert item.profile == "icar-papers"


def test_crossref_scraper_date_filtering() -> None:
    old_date = [2024, 1, 1]
    item_data = _sample_crossref_item(pub_date=old_date)
    client = _mock_client(_mock_crossref_response([item_data]))
    config = CrossrefJournalConfig(enabled=True)
    scraper = CrossrefScraper(config, client)

    since = _now() - timedelta(days=2)
    items = asyncio.run(scraper.fetch(since))
    assert len(items) == 0


def test_papers_quota_limit_enforced_across_arxiv_and_mdpi() -> None:
    """Test that category_groups.papers with limit 3 strictly truncates ArXiv + MDPI papers to 3."""
    config = Config(
        ai=AIConfig(
            provider="openai",
            model="gpt-4",
            api_key_env="OPENAI_API_KEY",
        ),
        sources=SourcesConfig(),
        processing=ProcessingConfig(default_profile="icar-info"),
        digest=DigestConfig(
            category_groups={
                "papers": CategoryGroupConfig(
                    name="前沿论文",
                    limit=3,
                    categories=["arxiv-paper", "mdpi-paper"],
                )
            }
        ),
    )
    orchestrator = HorizonOrchestrator(config, storage=MagicMock())

    now = _now()
    # Create 3 ArXiv papers and 3 MDPI papers with different scores
    items = [
        ContentItem(
            id=f"arxiv:paper:{i}",
            source_type=SourceType.ARXIV,
            title=f"ArXiv Paper {i}",
            url=f"https://arxiv.org/abs/2601.0000{i}",
            content=f"ArXiv content {i}",
            published_at=now,
            metadata={"category": "arxiv-paper"},
            profile="icar-papers",
            processing=ProcessingResult(
                classification=ClassificationResult(
                    profile="icar-papers",
                    method="source_override",
                ),
                analysis=ContentAnalysis(
                    score=score,
                    reason="test reason",
                    summary="test summary",
                ),
            ),
        )
        for i, score in enumerate([9.0, 7.0, 5.0], start=1)
    ] + [
        ContentItem(
            id=f"crossref:26248921:10_3390_vehicles809020{i}",
            source_type=SourceType.CROSSREF,
            title=f"MDPI Paper {i}",
            url=f"https://doi.org/10.3390/vehicles809020{i}",
            content=f"MDPI content {i}",
            published_at=now,
            metadata={"category": "mdpi-paper"},
            profile="icar-papers",
            processing=ProcessingResult(
                classification=ClassificationResult(
                    profile="icar-papers",
                    method="source_override",
                ),
                analysis=ContentAnalysis(
                    score=score,
                    reason="test reason",
                    summary="test summary",
                ),
            ),
        )
        for i, score in enumerate([8.5, 6.5, 4.5], start=1)
    ]

    # Total items input = 6
    assert len(items) == 6

    # Apply balanced digest
    result = orchestrator.apply_balanced_digest(items, log=False)

    # Exactly 3 papers must be selected
    assert len(result.items) == 3

    # Scores should be the top 3: 9.0 (ArXiv 1), 8.5 (MDPI 1), 7.0 (ArXiv 2)
    selected_scores = [item.processing.analysis.score for item in result.items]
    assert selected_scores == [9.0, 8.5, 7.0]

    selected_categories = [item.metadata["category"] for item in result.items]
    assert selected_categories == ["arxiv-paper", "mdpi-paper", "arxiv-paper"]


def test_summarizer_renders_open_access_badge() -> None:
    from src.ai.summarizer import DailySummarizer

    summarizer = DailySummarizer(profile_order=["icar-papers"])
    item = ContentItem(
        id="crossref:26248921:10_3390_vehicles8090210",
        source_type=SourceType.CROSSREF,
        title="[Paper] Trajectory Tracking Control",
        url="https://doi.org/10.3390/vehicles8090210",
        content="Paper content",
        published_at=_now(),
        metadata={
            "doi": "10.3390/vehicles8090210",
            "is_oa": True,
            "pdf_url": "https://www.mdpi.com/2624-8921/8/9/210/pdf",
            "category": "mdpi-paper",
        },
        profile="icar-papers",
        processing=ProcessingResult(
            classification=ClassificationResult(
                profile="icar-papers",
                method="source_override",
            ),
            analysis=ContentAnalysis(
                score=8.5,
                reason="test reason",
                summary="test summary",
            ),
        ),
    )
    md = asyncio.run(summarizer.generate_summary([item], "2026-09-07", 1, language="zh"))
    assert "🔓" in md
    assert "Open Access" in md
    assert "免费全文直达 (PDF)" in md
    assert "https://www.mdpi.com/2624-8921/8/9/210/pdf" in md

