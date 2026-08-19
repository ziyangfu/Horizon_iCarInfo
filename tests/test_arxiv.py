from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
from src.models import ArXivConfig, SourceType
from src.scrapers.arxiv import ArXivScraper


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _arxiv_atom_feed(entries_xml: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>ArXiv Query Results</title>
      {entries_xml}
    </feed>
    """


def _arxiv_entry(
    arxiv_id: str = "2401.12345v1",
    title: str = "Steer-by-Wire Control for Intelligent Vehicles",
    summary: str = "This paper presents an active steer-by-wire controller.",
    author: str = "Jane Doe",
    published: str = "2026-08-19T10:00:00Z",
) -> str:
    return f"""
    <entry xmlns="http://www.w3.org/2005/Atom">
      <id>http://arxiv.org/abs/{arxiv_id}</id>
      <published>{published}</published>
      <title>{title}</title>
      <summary>{summary}</summary>
      <author><name>{author}</name></author>
      <link href="http://arxiv.org/abs/{arxiv_id}" rel="alternate" type="text/html"/>
      <link href="http://arxiv.org/pdf/{arxiv_id}" rel="related" type="application/pdf" title="pdf"/>
    </entry>
    """


def _mock_client(text: str) -> AsyncMock:
    response = MagicMock()
    response.text = text
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.get.return_value = response
    return client


def test_arxiv_scraper_disabled() -> None:
    client = _mock_client("")
    config = ArXivConfig(enabled=False)
    scraper = ArXivScraper(config, client)

    items = asyncio.run(scraper.fetch(_now() - timedelta(days=1)))
    assert items == []
    client.get.assert_not_called()


def test_arxiv_scraper_fetch_valid() -> None:
    feed_xml = _arxiv_atom_feed(_arxiv_entry())
    client = _mock_client(feed_xml)
    config = ArXivConfig(
        enabled=True,
        categories=["cs.RO", "eess.SY"],
        keywords=["steer-by-wire"],
        category="academic-paper",
        profile="icar-info",
    )
    scraper = ArXivScraper(config, client)

    since = _now() - timedelta(days=2)
    items = asyncio.run(scraper.fetch(since))

    assert len(items) == 1
    item = items[0]
    assert item.source_type == SourceType.ARXIV
    assert "[Paper] Steer-by-Wire Control for Intelligent Vehicles" in item.title
    assert item.author == "Jane Doe"
    assert str(item.url) == "http://arxiv.org/pdf/2401.12345v1"
    assert item.metadata["arxiv_id"] == "2401.12345v1"
    assert item.profile == "icar-info"
