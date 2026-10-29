"""Explain every content selection decision without calling the model again."""

from collections import Counter, defaultdict
from typing import Any

from ..models import ContentItem, ProcessingConfig


def selection_diagnostics(
    items: list[ContentItem],
    settings: ProcessingConfig,
    threshold_ids: list[str],
    topic_ids: list[str],
    eligible_ids: list[str],
    selected_ids: list[str],
) -> dict[str, Any]:
    threshold_set = set(threshold_ids)
    topic_set = set(topic_ids)
    eligible_set = set(eligible_ids)
    selected_set = set(selected_ids)
    profiles: dict[str, Counter] = defaultdict(Counter)
    decisions = []
    for item in items:
        analysis = item.processing.analysis if item.processing else None
        profile = item.processing.classification.profile if item.processing else "unclassified"
        preference = settings.profile_settings.get(profile)
        threshold = preference.threshold if preference else None
        score = analysis.score if analysis else None
        if analysis is None or score is None:
            decision = "analysis_failed"
        elif item.id not in threshold_set:
            decision = "below_threshold"
        elif item.id not in topic_set:
            decision = "topic_duplicate"
        elif item.id not in eligible_set:
            decision = "below_threshold_after_reanalysis"
        elif item.id not in selected_set:
            decision = "digest_quota"
        else:
            decision = "selected"
        counts = profiles[profile]
        counts["analyzed"] += 1
        counts[decision] += 1
        if score is not None:
            counts[f"score_{int(score)}"] += 1
        decisions.append({
            "id": item.id,
            "title": item.title,
            "source": item.source_type.value,
            "profile": profile,
            "score": score,
            "threshold": threshold,
            "decision": decision,
            "reason": analysis.reason if analysis else "Profile resolution or analysis failed",
            "item": item.model_dump(mode="json"),
        })
    return {
        "stages": {"analyzed": len(items), "threshold": len(threshold_ids), "topic_dedup": len(topic_ids), "eligible": len(eligible_ids), "selected": len(selected_ids)},
        "profiles": {key: dict(value) for key, value in profiles.items()},
        "decisions": decisions,
    }


def render_selection_report(report: dict[str, Any]) -> str:
    labels = {
        "analysis_failed": "分析失败",
        "below_threshold": "低于阈值",
        "topic_duplicate": "同事件去重",
        "below_threshold_after_reanalysis": "复评后低于阈值",
        "digest_quota": "板块／总量限额",
        "selected": "入选",
    }
    lines = [f"# 筛选诊断 - {report['date']}", "", f"采集起点（UTC）：{report['since']}", ""]
    if report.get("stages"):
        stages = report["stages"]
        lines.extend([f"原始采集 {len(report.get('raw_items', []))} 条 → 分析 {stages['analyzed']} 条 → 阈值通过 {stages['threshold']} 条 → 同事件去重后 {stages['topic_dedup']} 条 → 复评通过 {stages['eligible']} 条 → 最终入选 {stages['selected']} 条。", ""])
    lines.extend(["| 板块 | 分析数 | 入选 | 低于阈值 | 分析失败 | 去重 | 限额 |", "|---|---:|---:|---:|---:|---:|---:|"])
    for profile, counts in report.get("profiles", {}).items():
        lines.append(f"| {profile} | {counts['analyzed']} | {counts.get('selected', 0)} | {counts.get('below_threshold', 0) + counts.get('below_threshold_after_reanalysis', 0)} | {counts.get('analysis_failed', 0)} | {counts.get('topic_duplicate', 0)} | {counts.get('digest_quota', 0)} |")
    lines.extend(["", "每条内容的评分、阈值、去留原因如下；完整采集内容及模型输出保存在同名 JSON 中。", "", "| 内容 | 来源／板块 | 分数／阈值 | 处理结果 | 模型理由 |", "|---|---|---|---|---|"])

    def cell(value: Any) -> str:
        return str(value).replace("|", "／").replace("\n", " ").replace("<", "&lt;").replace(">", "&gt;")

    for decision in report.get("decisions", []):
        lines.append(f"| {cell(decision['title'])} | {cell(decision['source'])}／{cell(decision['profile'])} | {decision['score']}／{decision['threshold']} | {labels[decision['decision']]} | {cell(decision['reason'])} |")
    if report.get("enrichment"):
        enrichment = report["enrichment"]
        lines.extend(["", f"深度解读成功：{enrichment['succeeded']}；失败：{len(enrichment['failures'])}。"])
        for item_id, error in enrichment["failures"].items():
            lines.append(f"- {cell(item_id)}：{cell(error)}")
    return "\n".join(lines) + "\n"
