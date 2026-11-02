"""Bounded recovery before publishing an empty chassis-news section."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import httpx

from ..extractors import ExtractorRegistry
from ..models import ContentItem, SOURCE_REGISTRY, SourcesConfig, SourceType
from .content import COMMENTS_MARKER, select_content, split_content
from .diagnostics import selection_diagnostics

if TYPE_CHECKING:
    from ..orchestrator import FilteringPipelineResult, HorizonOrchestrator


NEWS_PROFILE = "icar-info"
ACADEMIC_SOURCES = {"arxiv", "patents", "crossref"}


def news_sources(sources: SourcesConfig, default_profile: str) -> SourcesConfig:
    """Copy only sources routed to chassis news; never retry academic sources."""
    result = sources.model_copy(deep=True)

    def matches(config) -> bool:
        if not getattr(config, "enabled", True):
            return False
        route = getattr(config, "profile", None)
        if isinstance(route, list):
            return NEWS_PROFILE in route
        return route == NEWS_PROFILE or (
            route in {None, "auto"} and default_profile == NEWS_PROFILE
        )

    for definition in SOURCE_REGISTRY.values():
        field = definition.config_field
        value = getattr(result, field)
        if value is None:
            continue
        if definition.config_is_list:
            setattr(result, field, [] if field in ACADEMIC_SOURCES else [entry for entry in value if matches(entry)])
        elif definition.item_fields:
            for child_field in definition.item_fields:
                setattr(value, child_field, [entry for entry in getattr(value, child_field) if matches(entry)])
            if not any(getattr(value, child_field) for child_field in definition.item_fields):
                value.enabled = False
        elif not matches(value):
            value.enabled = False
    return result


class NewsRecovery:
    """One recovery round scoped to one run, with no publishing side effects."""

    def __init__(self, orchestrator: HorizonOrchestrator, since: datetime):
        self.orchestrator = orchestrator
        self.config = orchestrator.config.processing.news_recovery
        self.since = since
        self.until = datetime.now(timezone.utc)
        self.sources = news_sources(
            orchestrator.config.sources,
            orchestrator.config.processing.default_profile,
        )
        self.fetch_succeeded = False
        self.report: dict = {
            "triggered": False,
            "profile": NEWS_PROFILE,
            "rounds": 0,
            "since": since.isoformat(),
            "until": self.until.isoformat(),
            "fetches": [],
            "reanalysis": [],
            "errors": [],
        }

    def _profile(self, item: ContentItem) -> str | None:
        if item.processing:
            return item.processing.classification.profile
        if item.profile in (None, "auto"):
            return self.orchestrator.config.processing.default_profile
        if isinstance(item.profile, list) and NEWS_PROFILE in item.profile:
            return NEWS_PROFILE
        return item.profile if isinstance(item.profile, str) else None

    def _in_window(self, item: ContentItem) -> bool:
        since = self.since
        if item.source_type == SourceType.GOOGLE_NEWS and self.sources.google_news:
            hours = self.sources.google_news.lookback_hours
            if hours is not None:
                since = min(since, self.until - timedelta(hours=hours))
        published = item.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        return since <= published <= self.until

    async def _fetch(self, names: set[str], sources: SourcesConfig, stage: str) -> list[ContentItem]:
        orchestrator = self.orchestrator
        original_report = orchestrator.last_fetch_report
        try:
            items = await orchestrator.fetch_all_sources(
                self.since, sources=sources, source_names=names,
            )
            report = orchestrator.last_fetch_report
            if report is not None and report is not original_report:
                self.report["fetches"].append({"stage": stage, **report.to_dict()})
                self.fetch_succeeded |= bool(report.outcomes) and not report.all_failed
            return items
        except Exception as exc:
            self.report["errors"].append(f"{stage}: {type(exc).__name__}: {exc}")
            return []
        finally:
            orchestrator.last_fetch_report = original_report

    async def _add_new_items(
        self, fetched: list[ContentItem], raw: list[ContentItem], analyzed: list[ContentItem],
    ) -> None:
        from ..orchestrator import _deduplication_url_key

        seen_ids = {item.id for item in raw}
        seen_urls = {_deduplication_url_key(str(item.url)) for item in raw}
        remaining = self.config.max_new_items - self.report["new_items"]
        candidates = []
        for item in fetched:
            key = _deduplication_url_key(str(item.url))
            if not self._in_window(item):
                self.report["outside_window"] += 1
                continue
            if item.id in seen_ids or key in seen_urls:
                self.report["duplicates"] += 1
                continue
            if len(candidates) >= remaining:
                break
            seen_ids.add(item.id)
            seen_urls.add(key)
            candidates.append(item)
        raw.extend(candidates)
        self.report["new_items"] += len(candidates)
        self.report["new_item_ids"].extend(item.id for item in candidates)
        if not candidates:
            return
        try:
            results = await self.orchestrator.analyze_items(
                [item.model_copy(deep=True) for item in candidates],
            )
            analyzed.extend(results)
        except Exception as exc:
            self.report["errors"].append(f"new_item_analysis: {type(exc).__name__}: {exc}")

    async def _reanalyze(self, analyzed: list[ContentItem], threshold: float) -> None:
        candidates = []
        for item in analyzed:
            if self._profile(item) != NEWS_PROFILE:
                continue
            score = item.processing.analysis.score if item.processing and item.processing.analysis else None
            if score is None or max(3.0, threshold - 1.0) <= score < threshold:
                candidates.append((item, score))
        candidates.sort(key=lambda entry: (entry[1] is not None, -(entry[1] or 0)))
        extractor = ExtractorRegistry(self.orchestrator.config.extractors).get("trafilatura")
        async with httpx.AsyncClient(timeout=20.0) as client:
            for item, original_score in candidates[:self.config.max_reanalysis_items]:
                entry = {
                    "id": item.id,
                    "original_score": original_score,
                    "original_reason": item.processing.analysis.reason if item.processing and item.processing.analysis else None,
                    "content_extended": False,
                    "status": "skipped_no_new_content",
                }
                self.report["reanalysis"].append(entry)
                revised = item.model_copy(deep=True)
                try:
                    try:
                        async with asyncio.timeout(30):
                            body = await extractor.extract(str(item.url), client) if extractor else None
                    except Exception as exc:
                        body = None
                        entry["extraction_error"] = f"{type(exc).__name__}: {exc}"
                    parts = split_content(item.content)
                    original = select_content(parts.main, 100000, "prefix")
                    if body and len(body.strip()) >= max(200, len(original.strip()) + 100):
                        revised.content = body.strip()
                        if parts.comments:
                            revised.content += f"\n\n{COMMENTS_MARKER}\n\n{parts.comments}"
                        entry["content_extended"] = True
                    if original_score is not None and not entry["content_extended"]:
                        continue
                    results = await self.orchestrator.analyze_items([revised])
                    if len(results) != 1 or results[0].id != item.id:
                        raise ValueError("Reanalysis must return the requested item")
                    revised = results[0]
                    analysis = revised.processing.analysis if revised.processing else None
                    entry["score"] = analysis.score if analysis else None
                    entry["reason"] = analysis.reason if analysis else None
                    entry["status"] = "scored" if analysis and analysis.score is not None else "analysis_failed"
                    analyzed[analyzed.index(item)] = revised
                except Exception as exc:
                    entry["status"] = "failed"
                    entry["error"] = f"{type(exc).__name__}: {exc}"

    async def run(
        self,
        raw_items: list[ContentItem],
        analyzed_items: list[ContentItem],
        initial: FilteringPipelineResult,
    ) -> tuple[list[ContentItem], list[ContentItem], FilteringPipelineResult]:
        from ..orchestrator import FilteringPipelineResult

        if any(self._profile(item) == NEWS_PROFILE for item in initial.items):
            self.report["status"] = "not_needed"
            return raw_items, analyzed_items, initial
        # A quota exclusion is not a shortage of qualifying news.
        if any(self._profile(item) == NEWS_PROFILE and item.id in initial.eligible_ids for item in analyzed_items):
            self.report["status"] = "skipped_quota"
            return raw_items, analyzed_items, initial
        settings = self.orchestrator.config.processing.profile_settings.get(NEWS_PROFILE)
        threshold = settings.threshold if settings else None
        if threshold is None:
            self.report["status"] = "skipped_no_threshold"
            return raw_items, analyzed_items, initial

        self.report.update({
            "triggered": True,
            "rounds": 1,
            "threshold": threshold,
            "new_items": 0,
            "new_item_ids": [],
            "duplicates": 0,
            "outside_window": 0,
            "initial_selection": selection_diagnostics(
                analyzed_items, self.orchestrator.config.processing,
                initial.threshold_ids, initial.topic_ids, initial.eligible_ids,
                [item.id for item in initial.items],
            ),
        })
        self.orchestrator.console.print("[yellow]No qualifying chassis news; attempting one recovery round.[/yellow]")
        raw = list(raw_items)
        analyzed = list(analyzed_items)
        fetch_report = self.orchestrator.last_fetch_report
        failed_names = {
            outcome.source_name for outcome in fetch_report.outcomes
            if outcome.status == "failure"
        } if fetch_report else set()
        if failed_names:
            fetched = await self._fetch(failed_names, self.sources, "retry_failed_sources")
            await self._add_new_items(fetched, raw, analyzed)

        await self._reanalyze(analyzed, threshold)
        has_news = any(
            self._profile(item) == NEWS_PROFILE and self.orchestrator.passes_profile_filter(item)
            for item in analyzed
        )
        gn = self.sources.google_news
        if not has_news and gn and gn.enabled and self.config.queries and self.report["new_items"] < self.config.max_new_items:
            supplemental = self.sources.model_copy(deep=True)
            supplemental.google_news = gn.model_copy(update={
                "queries": self.config.queries,
                "max_results": self.config.max_new_items,
                "profile": NEWS_PROFILE,
            })
            fetched = await self._fetch({"Google News"}, supplemental, "supplemental_search")
            await self._add_new_items(fetched, raw, analyzed)

        news = [item for item in analyzed if self._profile(item) == NEWS_PROFILE]
        selected_news = await self.orchestrator.select_digest_items(news)
        original_ids = {item.id for item in analyzed_items if self._profile(item) != NEWS_PROFILE}

        def combine_ids(previous: list[str], current: list[str]) -> list[str]:
            return [item_id for item_id in previous if item_id in original_ids] + current

        threshold_ids = combine_ids(initial.threshold_ids, selected_news.threshold_ids)
        topic_ids = combine_ids(initial.topic_ids, selected_news.topic_ids)
        eligible_ids = combine_ids(initial.eligible_ids, selected_news.eligible_ids)
        eligible_set = set(eligible_ids)
        balanced = self.orchestrator.apply_balanced_digest([item for item in analyzed if item.id in eligible_set])
        result = FilteringPipelineResult(
            items=balanced.items,
            threshold_count=len(threshold_ids),
            topic_dedup_count=len(topic_ids),
            topic_dedup_removed=len(threshold_ids) - len(topic_ids),
            balanced_digest=balanced,
            eligible_count=len(eligible_ids),
            threshold_ids=threshold_ids,
            topic_ids=topic_ids,
            eligible_ids=eligible_ids,
        )
        self.report["selected"] = sum(self._profile(item) == NEWS_PROFILE for item in result.items)
        self.report["status"] = "recovered" if self.report["selected"] else "still_empty"
        return raw, analyzed, result
