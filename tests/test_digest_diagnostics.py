import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

from src.ai.summarizer import DailySummarizer
from src.models import (
    ClassificationResult, ContentAnalysis, ContentArtifact, ContentBlock,
    ContentItem, DigestConfig, ProcessingConfig, ProcessingResult,
    ProfileSettingsConfig, SourceType,
)
from src.orchestrator import HorizonOrchestrator
from src.processing import ProfileRegistry
from src.processing.diagnostics import selection_diagnostics
from src.storage.manager import StorageManager
from src.ui.parser import parse_summary_markdown


def item(item_id, score):
    return ContentItem(
        id=item_id, source_type=SourceType.RSS, title=item_id,
        url=f"https://example.com/{item_id}", published_at=datetime.now(timezone.utc),
        profile="icar-info", processing=ProcessingResult(
            classification=ClassificationResult(profile="icar-info", method="source_override"),
            analysis=ContentAnalysis(score=score, reason="工程进展", summary="制动控制工程进展"),
        ),
    )


def test_selection_report_distinguishes_every_filter_stage(tmp_path):
    items = [item("failed", None), item("low", 2), item("duplicate", 6), item("quota", 6), item("kept", 7), item("recheck", 3)]
    settings = ProcessingConfig(profile_settings={"icar-info": ProfileSettingsConfig(threshold=4)})
    report = {"date": "2026-10-28", "since": "2026-10-27T00:00:00+00:00"}
    report.update(selection_diagnostics(items, settings,
        ["duplicate", "quota", "kept", "recheck"],
        ["quota", "kept", "recheck"], ["quota", "kept"], ["kept"]))
    assert [entry["decision"] for entry in report["decisions"]] == [
        "analysis_failed", "below_threshold", "topic_duplicate", "digest_quota", "selected", "below_threshold_after_reanalysis",
    ]
    storage = StorageManager(str(tmp_path))
    path = storage.save_pipeline_report("2026-10-28", report)
    saved = json.loads(path.read_text())
    assert saved["profiles"]["icar-info"]["analyzed"] == 6
    assert saved["decisions"][4]["item"]["processing"]["analysis"]["score"] == 7
    assert "同事件去重" in path.with_suffix(".md").read_text()


def test_filter_preserves_relevant_incremental_items_and_stage_ids():
    from types import SimpleNamespace
    from rich.console import Console
    from io import StringIO
    orchestrator = HorizonOrchestrator.__new__(HorizonOrchestrator)
    orchestrator.config = SimpleNamespace(
        processing=ProcessingConfig(profile_settings={"icar-info": ProfileSettingsConfig(threshold=4)}),
        digest=DigestConfig(),
    )
    orchestrator.profiles = ProfileRegistry.load(Path("profiles"), "icar-info")
    orchestrator.console = Console(file=StringIO())
    orchestrator.merge_topic_duplicates = AsyncMock(side_effect=lambda items, **kwargs: items)
    orchestrator._expand_twitter_discussion = AsyncMock()
    result = asyncio.run(orchestrator.select_digest_items([item("noise", 2), item("engineering", 4.5), item("major", 8)]))
    assert [entry.id for entry in result.items] == ["major", "engineering"]
    assert result.threshold_ids == result.topic_ids == result.eligible_ids == ["major", "engineering"]


def test_extended_window_and_block_ids_survive_markdown_dashboard_roundtrip():
    entry = item("paper", 5)
    entry.source_type = SourceType.CROSSREF
    entry.processing.classification.profile = "icar-papers"
    entry.published_at -= timedelta(days=3)
    entry.metadata["collection_window_hours"] = 168
    entry.processing.analysis.tags = ["#steering"]
    entry.processing.artifacts["zh"] = ContentArtifact(language="zh", title="转向论文", blocks=[
        ContentBlock(id="summary", title="概述", content="论文提出转向控制方法。", primary=True),
        ContentBlock(id="background", title="模型随意生成的标题", content="现有控制存在工程局限。"),
        ContentBlock(id="technical_breakthrough", title="另一个标题", content="给出控制律。"),
        ContentBlock(id="impact", title="应用意义", content="有助于后续验证。"),
    ])
    md = asyncio.run(DailySummarizer().generate_summary([entry], "2026-10-28", 1, language="zh"))
    assert "近 168 小时" in md
    assert entry.published_at.strftime("%Y-%m-%d") in md
    assert "`#steering`" in md
    parsed = parse_summary_markdown(md, "horizon-2026-10-28-zh.md")
    assert parsed["items"][0]["background"] == "现有控制存在工程局限。"
    assert parsed["items"][0]["breakthrough"] == "给出控制律。"
    assert parsed["items"][0]["impact"] == "有助于后续验证。"


def test_empty_patent_section_explains_missing_content():
    summarizer = DailySummarizer(profile_order=["icar-info", "icar-papers", "icar-patents"], profile_names={
        "icar-info": {"zh": "行业资讯"}, "icar-papers": {"zh": "前沿论文"}, "icar-patents": {"zh": "前瞻专利"},
    })
    md = asyncio.run(summarizer.generate_summary([item("news", 5)], "2026-10-28", 1, language="zh"))
    assert "## 前瞻专利\n\n本期暂无符合收录条件的内容。" in md


def test_topic_dedup_preserves_different_patent_publications(monkeypatch):
    from types import SimpleNamespace
    orchestrator = HorizonOrchestrator.__new__(HorizonOrchestrator)
    orchestrator.config = SimpleNamespace(ai=object())
    entries = [item("primary", 8), item("other", 7)]
    entries[0].metadata["publication_number"] = "CN119734755A"
    entries[1].metadata["publication_number"] = "CN103587576A"
    client = SimpleNamespace(complete=AsyncMock(return_value='{"duplicates": [[1, 0], [null, "invalid"]]}'))
    monkeypatch.setattr("src.orchestrator.create_ai_client", lambda config: client)
    result = asyncio.run(orchestrator.merge_topic_duplicates(entries, log=False))
    assert [entry.id for entry in result] == ["primary", "other"]


def test_topic_dedup_keeps_highest_scored_item_when_model_reverses_order(monkeypatch):
    from types import SimpleNamespace
    orchestrator = HorizonOrchestrator.__new__(HorizonOrchestrator)
    orchestrator.config = SimpleNamespace(ai=object())
    client = SimpleNamespace(complete=AsyncMock(return_value='{"duplicates": [[1, 0]]}'))
    monkeypatch.setattr("src.orchestrator.create_ai_client", lambda config: client)
    result = asyncio.run(orchestrator.merge_topic_duplicates([item("high", 8), item("low", 5)], log=False))
    assert [entry.id for entry in result] == ["high"]
