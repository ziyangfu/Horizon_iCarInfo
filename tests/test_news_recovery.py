from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from rich.console import Console

from src.ai.enricher import EnrichmentBatchResult
from src.models import (
    AIConfig, ClassificationResult, Config, ContentAnalysis, ContentItem,
    EmailConfig, GoogleNewsConfig, NewsRecoveryConfig, ProcessingConfig,
    ProcessingResult, ProfileSettingsConfig, SourcesConfig, SourceType,
)
from src.orchestrator import FetchReport, HorizonOrchestrator, SourceFetchOutcome
from src.processing.news_recovery import NewsRecovery, news_sources
from src.storage.manager import StorageManager


NOW = datetime.now(timezone.utc)
SINCE = NOW - timedelta(hours=24)


def item(name, score=3, *, profile="icar-info", source=SourceType.GOOGLE_NEWS, hours=2):
    return ContentItem(
        id=name, title=name, url=f"https://example.com/{name}", content="Short excerpt",
        source_type=source, published_at=NOW - timedelta(hours=hours), profile=profile,
        processing=ProcessingResult(
            classification=ClassificationResult(profile=profile, method="source_override"),
            analysis=ContentAnalysis(score=score, reason=f"original {score}", summary=name),
        ),
    )


@pytest.fixture
def setup(tmp_path, monkeypatch):
    config = Config(
        ai=AIConfig(provider="ollama", model="test", api_key_env="OLLAMA_API_KEY", languages=["zh"]),
        sources=SourcesConfig(
            hackernews={"enabled": False}, reddit={"enabled": False},
            google_news=GoogleNewsConfig(enabled=True, profile="icar-info", lookback_hours=72),
        ),
        processing=ProcessingConfig(
            profiles_dir=str(Path("profiles").resolve()), default_profile="icar-info",
            profile_settings={name: ProfileSettingsConfig(threshold=4) for name in ["icar-info", "icar-papers", "icar-patents"]},
            news_recovery=NewsRecoveryConfig(enabled=True, queries=['"steer-by-wire"']),
        ),
    )
    orchestrator = HorizonOrchestrator(config, StorageManager(str(tmp_path)), Console(file=StringIO()))
    orchestrator.merge_topic_duplicates = AsyncMock(side_effect=lambda items, **kwargs: items)
    orchestrator._expand_twitter_discussion = AsyncMock()
    orchestrator.fetch_all_sources = AsyncMock(return_value=[])
    orchestrator.analyze_items = AsyncMock(side_effect=lambda items: items)
    extractor = SimpleNamespace(extract=AsyncMock(return_value=None))
    monkeypatch.setattr("src.processing.news_recovery.ExtractorRegistry", lambda config: SimpleNamespace(get=lambda name: extractor))
    return orchestrator, extractor


def recover(orchestrator, entries, *, since=SINCE):
    async def run():
        initial = await orchestrator.select_digest_items(entries, log=False)
        recovery = NewsRecovery(orchestrator, since)
        raw, analyzed, result = await recovery.run(entries, entries, initial)
        return recovery, raw, analyzed, result
    return asyncio.run(run())


def test_existing_news_skips_all_recovery_work(setup):
    orchestrator, extractor = setup
    recovery, raw, analyzed, result = recover(orchestrator, [item("kept", 4)])
    assert recovery.report["status"] == "not_needed"
    assert [entry.id for entry in result.items] == ["kept"]
    orchestrator.fetch_all_sources.assert_not_awaited()
    orchestrator.analyze_items.assert_not_awaited()
    extractor.extract.assert_not_awaited()


def test_quota_exclusion_does_not_trigger_fetch_or_rescoring(setup):
    orchestrator, _ = setup
    orchestrator.config.digest.max_items = 1
    recovery, _, _, _ = recover(orchestrator, [item("paper", 8, profile="icar-papers"), item("news", 4)])
    assert recovery.report["status"] == "skipped_quota"
    orchestrator.fetch_all_sources.assert_not_awaited()
    orchestrator.analyze_items.assert_not_awaited()


def test_near_threshold_item_is_not_rescored_without_new_content(setup):
    orchestrator, _ = setup
    recovery, _, analyzed, result = recover(orchestrator, [item("near", 3)])
    assert result.items == []
    assert analyzed[0].processing.analysis.score == 3
    assert recovery.report["reanalysis"][0]["status"] == "skipped_no_new_content"
    assert recovery.report["status"] == "still_empty"
    orchestrator.analyze_items.assert_not_awaited()
    orchestrator.fetch_all_sources.assert_awaited_once()
    assert orchestrator.config.processing.profile_settings["icar-info"].threshold == 4


def test_richer_content_recovery_preserves_first_pass_and_other_profiles(setup):
    orchestrator, extractor = setup
    extractor.extract.return_value = "Validated steering control architecture. " * 20
    near, paper = item("near", 3), item("paper", 7, profile="icar-papers")

    async def analyze(items):
        items[0].processing.analysis = ContentAnalysis(score=4.5, reason="new evidence", summary="technical details")
        return items

    orchestrator.analyze_items.side_effect = analyze
    recovery, _, analyzed, result = recover(orchestrator, [near, paper])
    assert {entry.id for entry in result.items} == {"near", "paper"}
    assert near.processing.analysis.score == 3
    assert next(entry for entry in analyzed if entry.id == "paper") is paper
    assert recovery.report["initial_selection"]["decisions"][0]["score"] == 3
    assert recovery.report["reanalysis"][0]["score"] == 4.5
    assert recovery.report["status"] == "recovered"
    orchestrator.fetch_all_sources.assert_not_awaited()
    assert [entry.id for entry in orchestrator.analyze_items.await_args.args[0]] == ["near"]


def test_new_body_does_not_guarantee_admission(setup):
    orchestrator, extractor = setup
    extractor.extract.return_value = "Still promotional rather than technical. " * 20
    _, _, _, result = recover(orchestrator, [item("near", 3)])
    assert result.items == []
    orchestrator.analyze_items.assert_awaited_once()


def test_failed_analysis_is_retried_even_when_body_extraction_raises(setup):
    orchestrator, extractor = setup
    extractor.extract.side_effect = RuntimeError("extractor unavailable")

    async def analyze(items):
        items[0].processing.analysis.score = 5
        return items

    orchestrator.analyze_items.side_effect = analyze
    recovery, _, _, result = recover(orchestrator, [item("failed", None)])
    assert [entry.id for entry in result.items] == ["failed"]
    assert "extractor unavailable" in recovery.report["reanalysis"][0]["extraction_error"]
    orchestrator.analyze_items.assert_awaited_once()


def test_reanalysis_failure_keeps_original_and_continues_supplemental_search(setup):
    orchestrator, extractor = setup
    extractor.extract.return_value = "More evidence " * 50
    orchestrator.analyze_items.side_effect = RuntimeError("model unavailable")
    recovery, _, analyzed, result = recover(orchestrator, [item("near", 3)])
    assert result.items == []
    assert analyzed[0].processing.analysis.score == 3
    assert recovery.report["reanalysis"][0]["status"] == "failed"
    orchestrator.fetch_all_sources.assert_awaited_once()


def test_reanalysis_has_a_shared_limit_and_prioritizes_failures(setup):
    orchestrator, extractor = setup
    orchestrator.config.processing.news_recovery.max_reanalysis_items = 2
    entries = [item("near", 3), item("fail1", None), item("fail2", None), item("noise", 1)]
    recovery, _, _, _ = recover(orchestrator, entries)
    assert [entry["id"] for entry in recovery.report["reanalysis"]] == ["fail1", "fail2"]
    assert extractor.extract.await_count == 2


def test_supplemental_search_rejects_duplicates_and_dates_and_enforces_budget(setup):
    orchestrator, _ = setup
    orchestrator.config.processing.news_recovery.max_new_items = 1
    existing = item("noise", 1)
    duplicate = item("duplicate", 6)
    duplicate.url = str(existing.url) + "?utm_source=other"
    orchestrator.fetch_all_sources.return_value = [
        duplicate, item("old", 6, hours=100), item("future", 6, hours=-1),
        item("new", 4), item("over-budget", 5),
    ]
    recovery, raw, _, result = recover(orchestrator, [existing])
    assert [entry.id for entry in result.items] == ["new"]
    assert [entry.id for entry in raw] == ["noise", "new"]
    assert recovery.report["duplicates"] == 1
    assert recovery.report["outside_window"] == 2
    assert recovery.report["new_items"] == 1
    call = orchestrator.fetch_all_sources.await_args
    assert call.args[0] == SINCE
    assert call.kwargs["source_names"] == {"Google News"}
    assert call.kwargs["sources"].google_news.lookback_hours == 72
    assert call.kwargs["sources"].google_news.queries == ['"steer-by-wire"']
    assert orchestrator.config.sources.google_news.queries == []


def test_weekly_window_is_kept_during_supplemental_search(setup):
    orchestrator, _ = setup
    orchestrator.fetch_all_sources.return_value = [item("six-days-old", 5, hours=144)]
    since = NOW - timedelta(hours=168)
    _, _, _, result = recover(orchestrator, [], since=since)
    assert [entry.id for entry in result.items] == ["six-days-old"]
    assert orchestrator.fetch_all_sources.await_args.args[0] == since


def test_no_external_search_when_google_news_is_disabled(setup):
    orchestrator, _ = setup
    orchestrator.config.sources.google_news.enabled = False
    recovery, _, _, result = recover(orchestrator, [item("noise", 1)])
    assert result.items == []
    assert recovery.report["rounds"] == 1
    orchestrator.fetch_all_sources.assert_not_awaited()


def test_failed_source_retry_keeps_first_report_and_never_retries_academic_sources(setup):
    orchestrator, _ = setup
    orchestrator.config.sources = SourcesConfig.model_validate({
        **orchestrator.config.sources.model_dump(), "arxiv": [{"enabled": True}],
    })
    original = FetchReport([
        SourceFetchOutcome("Google News", "failure", error="timeout"),
        SourceFetchOutcome("ArXiv (arxiv-paper)", "failure", error="timeout"),
    ])
    orchestrator.last_fetch_report = original

    async def fetch(since, **kwargs):
        assert kwargs["sources"].arxiv == []
        orchestrator.last_fetch_report = FetchReport([SourceFetchOutcome("Google News", "success", [item("recovered", 5)])])
        return [item("recovered", 5)]

    orchestrator.fetch_all_sources.side_effect = fetch
    recovery, _, _, result = recover(orchestrator, [])
    assert [entry.id for entry in result.items] == ["recovered"]
    assert orchestrator.last_fetch_report is original
    assert recovery.fetch_succeeded
    assert recovery.report["fetches"][0]["stage"] == "retry_failed_sources"
    orchestrator.fetch_all_sources.assert_awaited_once()


def test_fetch_failure_does_not_fail_existing_papers_or_start_another_round(setup):
    orchestrator, _ = setup
    orchestrator.fetch_all_sources.side_effect = RuntimeError("network down")
    recovery, _, _, result = recover(orchestrator, [item("paper", 7, profile="icar-papers")])
    assert [entry.id for entry in result.items] == ["paper"]
    assert recovery.report["status"] == "still_empty"
    assert "network down" in recovery.report["errors"][0]
    orchestrator.fetch_all_sources.assert_awaited_once()


def test_news_source_filter_handles_nested_routes_without_mutating_original():
    sources = SourcesConfig(
        arxiv=[{}], patents=[{}], crossref=[{}],
        rss=[{"name": "news", "url": "https://example.com/feed", "profile": "icar-info"},
             {"name": "papers", "url": "https://example.com/papers", "profile": "icar-papers"}],
        reddit={"subreddits": [{"subreddit": "news", "profile": ["icar-info", "icar-papers"]},
                                  {"subreddit": "papers", "profile": "icar-papers"}]},
    )
    narrowed = news_sources(sources, "icar-info")
    assert narrowed.arxiv == narrowed.patents == narrowed.crossref == []
    assert [entry.name for entry in narrowed.rss] == ["news"]
    assert [entry.subreddit for entry in narrowed.reddit.subreddits] == ["news"]
    assert len(sources.rss) == len(sources.reddit.subreddits) == 2


@pytest.mark.parametrize("config", [
    {"max_new_items": 0}, {"max_new_items": 101}, {"max_reanalysis_items": -1},
    {"max_reanalysis_items": 21}, {"queries": [" "]}, {"queries": ["x" * 501]},
    {"queries": [str(i) for i in range(9)]},
])
def test_invalid_recovery_budgets_are_rejected(config):
    with pytest.raises(ValidationError):
        NewsRecoveryConfig(**config)


def test_native_pipeline_publishes_once_after_recovery_and_saves_both_passes(setup, tmp_path, monkeypatch):
    orchestrator, _ = setup
    monkeypatch.chdir(tmp_path)
    orchestrator.config.email = EmailConfig(
        enabled=True, imap_enabled=False, imap_server="imap.example.com",
        smtp_server="smtp.example.com", email_address="digest@example.com",
    )
    orchestrator.email_manager = MagicMock()
    orchestrator.webhook_notifier = SimpleNamespace(send_daily_summary=AsyncMock(), send_failure=AsyncMock())
    orchestrator.enrich_items = AsyncMock(return_value=EnrichmentBatchResult())

    async def fetch(since, **kwargs):
        if kwargs:
            entries = [item("recovered", 5)]
        else:
            entries = [item("noise", 1), item("paper", 7, profile="icar-papers")]
        orchestrator.last_fetch_report = FetchReport([SourceFetchOutcome("Google News", "success", entries)])
        return entries

    orchestrator.fetch_all_sources.side_effect = fetch
    asyncio.run(orchestrator.run())
    orchestrator.email_manager.send_daily_summary.assert_called_once()
    orchestrator.webhook_notifier.send_daily_summary.assert_awaited_once()
    orchestrator.webhook_notifier.send_failure.assert_not_awaited()
    orchestrator.enrich_items.assert_awaited_once()
    report_path = next((tmp_path / "diagnostics").glob("*.json"))
    report = json.loads(report_path.read_text())
    assert report["news_recovery"]["status"] == "recovered"
    assert report["news_recovery"]["initial_selection"]["profiles"]["icar-info"].get("selected", 0) == 0
    assert report["profiles"]["icar-info"]["selected"] == 1
    assert "资讯空板块兜底" in report_path.with_suffix(".md").read_text()


def test_native_pipeline_recovers_when_first_collection_is_completely_empty(setup, tmp_path, monkeypatch):
    orchestrator, _ = setup
    monkeypatch.chdir(tmp_path)
    orchestrator.enrich_items = AsyncMock(return_value=EnrichmentBatchResult())

    async def fetch(since, **kwargs):
        entries = [item("new", 5)] if kwargs else []
        orchestrator.last_fetch_report = FetchReport([
            SourceFetchOutcome("Google News", "success" if entries else "empty", entries),
        ])
        return entries

    orchestrator.fetch_all_sources.side_effect = fetch
    asyncio.run(orchestrator.run())
    assert orchestrator.fetch_all_sources.await_count == 2
    orchestrator.analyze_items.assert_awaited_once()
    assert [entry.id for entry in orchestrator.enrich_items.await_args.args[0]] == ["new"]
    report = json.loads(next((tmp_path / "diagnostics").glob("*.json")).read_text())
    assert report["news_recovery"]["status"] == "recovered"


def test_native_pipeline_preserves_total_failure_after_bounded_recovery(setup, tmp_path):
    orchestrator, _ = setup
    orchestrator.enrich_items = AsyncMock()
    orchestrator.webhook_notifier = SimpleNamespace(send_daily_summary=AsyncMock(), send_failure=AsyncMock())
    original = FetchReport([SourceFetchOutcome("Google News", "failure", error="timeout")])

    async def fetch(since, **kwargs):
        orchestrator.last_fetch_report = original if not kwargs else FetchReport([
            SourceFetchOutcome("Google News", "failure", error="still down"),
        ])
        return []

    orchestrator.fetch_all_sources.side_effect = fetch
    with pytest.raises(RuntimeError, match="All 1 attempted sources failed.*timeout"):
        asyncio.run(orchestrator.run())
    assert orchestrator.fetch_all_sources.await_count == 3
    assert orchestrator.last_fetch_report is original
    orchestrator.enrich_items.assert_not_awaited()
    orchestrator.webhook_notifier.send_failure.assert_awaited_once()
    orchestrator.webhook_notifier.send_daily_summary.assert_not_awaited()
    report = json.loads(next((tmp_path / "diagnostics").glob("*.json")).read_text())
    assert report["news_recovery"]["status"] == "still_empty"
    assert report["news_recovery"]["rounds"] == 1


def test_disabled_recovery_leaves_native_pipeline_unchanged(setup, tmp_path, monkeypatch):
    orchestrator, _ = setup
    monkeypatch.chdir(tmp_path)
    orchestrator.config.processing.news_recovery.enabled = False
    orchestrator.enrich_items = AsyncMock(return_value=EnrichmentBatchResult())
    orchestrator.fetch_all_sources.return_value = [item("noise", 1)]
    asyncio.run(orchestrator.run())
    orchestrator.fetch_all_sources.assert_awaited_once()
    report = json.loads(next((tmp_path / "diagnostics").glob("*.json")).read_text())
    assert "news_recovery" not in report


def test_source_allowlist_fetches_only_requested_jobs(setup, monkeypatch):
    orchestrator, _ = setup
    google_fetch = AsyncMock(return_value=[item("fresh", 5)])
    github_fetch = AsyncMock(return_value=[])
    monkeypatch.setattr("src.orchestrator.GoogleNewsScraper", lambda config, client: SimpleNamespace(fetch=google_fetch))
    monkeypatch.setattr("src.orchestrator.GitHubScraper", lambda config, client: SimpleNamespace(fetch=github_fetch))
    sources = SourcesConfig(
        hackernews={"enabled": False}, reddit={"enabled": False},
        github=[{"type": "repo_releases", "owner": "example", "repo": "example", "profile": "icar-info"}],
        google_news={"enabled": True, "profile": "icar-info"},
    )
    entries = asyncio.run(HorizonOrchestrator.fetch_all_sources(
        orchestrator, SINCE, sources=sources, source_names={"Google News"},
    ))
    assert [entry.id for entry in entries] == ["fresh"]
    google_fetch.assert_awaited_once_with(SINCE)
    github_fetch.assert_not_awaited()
    assert [outcome.source_name for outcome in orchestrator.last_fetch_report.outcomes] == ["Google News"]
