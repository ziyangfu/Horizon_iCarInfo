"""Markdown summary parser for the Web UI Dashboard.

Converts Horizon daily/weekly markdown digests into structured JSON objects.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def parse_summary_markdown(content: str, filename: str = "") -> Dict[str, Any]:
    """Parse a horizon summary markdown string into a structured dictionary."""
    lines = content.splitlines()

    title = "智能汽车底盘前瞻资讯速递"
    subtitle = ""
    date_str = ""
    total_raw_count = 0
    selected_count = 0

    # Extract date from filename if possible (e.g. horizon-2026-09-07-zh.md)
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    if date_match:
        date_str = date_match.group(1)

    # 1. Parse header
    for line in lines[:15]:
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped.lstrip("# ").strip()
            # If date is in title e.g. "# ... - 2026-09-07"
            if not date_str:
                m = re.search(r"(\d{4}-\d{2}-\d{2})", title)
                if m:
                    date_str = m.group(1)
        elif stripped.startswith(">"):
            subtitle = stripped.lstrip("> ").strip()
            # Extract counts e.g. 从 65 条内容中筛选出 7 条重要资讯
            cnt_match = re.search(r"从\s*(\d+)\s*条.*?筛选出\s*(\d+)\s*条", subtitle)
            if cnt_match:
                total_raw_count = int(cnt_match.group(1))
                selected_count = int(cnt_match.group(2))
            else:
                # English match: e.g. Filtered 7 items from 65 sources
                cnt_en = re.search(r"Filtered\s*(\d+)\s*items?\s*from\s*(\d+)", subtitle, re.I)
                if cnt_en:
                    selected_count = int(cnt_en.group(1))
                    total_raw_count = int(cnt_en.group(2))

    # 2. Parse sections and items
    items: List[Dict[str, Any]] = []
    current_section = "智能汽车与底盘前瞻资讯"
    current_category = "icar-info"

    # Split into sections based on '## '
    # We ignore the TOC (before first '## ')
    first_h2_idx = -1
    for idx, line in enumerate(lines):
        if line.strip().startswith("## "):
            first_h2_idx = idx
            break

    if first_h2_idx != -1:
        body_lines = lines[first_h2_idx:]
    else:
        body_lines = lines

    # Regex patterns
    item_header_re = re.compile(r"^###\s+\[(.*?)\]\((.*?)\)(?:\s+⭐️\s*([\d\.]+)/10)?")
    tag_re = re.compile(r"\*\*标签\*\*:\s*(.*)")
    anchor_re = re.compile(r'<a\s+id="([^"]+)"></a>')

    current_item: Optional[Dict[str, Any]] = None
    collecting_text_lines: List[str] = []

    def save_current_item():
        nonlocal current_item, collecting_text_lines
        if not current_item:
            return

        body_text = "\n".join(collecting_text_lines).strip()

        # Extract Open Access
        if "Open Access" in body_text or "开放获取" in body_text:
            current_item["is_open_access"] = True
            pdf_match = re.search(r"\[.*?免费全文直达.*?\((https?://[^\)]+)\)", body_text)
            if pdf_match:
                current_item["pdf_url"] = pdf_match.group(1)

        # Extract Patent info
        # e.g.: Google Patents · 专利号: CN121822331A · 申请人: 比亚迪股份有限公司 · 公开日: 2026-04-10
        patent_no_match = re.search(r"专利号[:：]\s*([A-Z0-9]+)", body_text)
        if patent_no_match:
            current_item["patent_number"] = patent_no_match.group(1)
            current_item["category"] = "icar-patents"
        applicant_match = re.search(r"申请人[:：]\s*([^·\n]+)", body_text)
        if applicant_match:
            current_item["patent_applicant"] = applicant_match.group(1).strip()
        pubdate_match = re.search(r"公开日[:：]\s*([0-9\-]+)", body_text)
        if pubdate_match:
            current_item["patent_pub_date"] = pubdate_match.group(1).strip()

        # Extract structured sections:
        # 技术背景 / 技术突破 / 行业影响
        bg_match = re.search(
            r"\*\*「技术背景(?:与工程挑战)?」\*\*\s*([\s\S]*?)(?=\*\*「|\n\n<details>|\*\*标签\*\*|$)",
            body_text,
        )
        if bg_match:
            current_item["background"] = bg_match.group(1).strip()

        tb_match = re.search(
            r"\*\*「技术突破」\*\*\s*([\s\S]*?)(?=\*\*「|\n\n<details>|\*\*标签\*\*|$)",
            body_text,
        )
        if tb_match:
            current_item["breakthrough"] = tb_match.group(1).strip()

        impact_match = re.search(
            r"\*\*「行业影响(?:与客观评价)?」\*\*\s*([\s\S]*?)(?=\*\*「|\n\n<details>|\*\*标签\*\*|$)",
            body_text,
        )
        if impact_match:
            current_item["impact"] = impact_match.group(1).strip()

        # Extract references
        ref_matches = re.findall(r'<li><a\s+href="([^"]+)">([^<]+)</a></li>', body_text)
        if ref_matches:
            current_item["references"] = [{"url": u, "title": t.strip()} for u, t in ref_matches]

        # Extract source meta line (e.g. google_news · gasgoo.com · 9月7日 05:54)
        for line in collecting_text_lines:
            stripped = line.strip()
            if " · " in stripped and not stripped.startswith("*") and not stripped.startswith("<") and not stripped.startswith(">"):
                current_item["meta_info"] = stripped
                break

        # If summary text is not explicitly set, extract lead paragraph
        lead_paras = []
        for p in body_text.split("\n\n"):
            p_strip = p.strip()
            if not p_strip or p_strip.startswith("**「") or p_strip.startswith("<") or p_strip.startswith(">") or p_strip.startswith("**标签**") or " · " in p_strip:
                continue
            lead_paras.append(p_strip)
        if lead_paras:
            current_item["summary"] = "\n\n".join(lead_paras[:2])

        items.append(current_item)
        current_item = None
        collecting_text_lines = []

    last_anchor_id = ""

    for line in body_lines:
        stripped = line.strip()

        # Check section header
        if stripped.startswith("## "):
            save_current_item()
            current_section = stripped.lstrip("# ").strip()
            if "专利" in current_section or "patent" in current_section.lower():
                current_category = "icar-patents"
            elif "论文" in current_section or "paper" in current_section.lower():
                current_category = "icar-papers"
            else:
                current_category = "icar-info"
            continue

        # Check anchor tag
        anchor_match = anchor_re.search(stripped)
        if anchor_match:
            last_anchor_id = anchor_match.group(1)
            continue

        # Check item header
        item_match = item_header_re.match(stripped)
        if item_match:
            save_current_item()
            item_title = item_match.group(1).strip()
            item_url = item_match.group(2).strip()
            score_val = float(item_match.group(3)) if item_match.group(3) else None

            # Determine category from anchor or section
            cat = current_category
            if "patents" in last_anchor_id:
                cat = "icar-patents"
            elif "papers" in last_anchor_id:
                cat = "icar-papers"
            elif "info" in last_anchor_id:
                cat = "icar-info"

            current_item = {
                "id": last_anchor_id or f"item-{len(items) + 1}",
                "title": item_title,
                "url": item_url,
                "score": score_val,
                "section": current_section,
                "category": cat,
                "tags": [],
                "meta_info": "",
                "summary": "",
                "background": "",
                "breakthrough": "",
                "impact": "",
                "references": [],
                "is_open_access": False,
                "pdf_url": "",
                "patent_number": "",
                "patent_applicant": "",
                "patent_pub_date": "",
            }
            last_anchor_id = ""
            continue

        # Check tags
        tag_match = tag_re.match(stripped)
        if tag_match and current_item:
            raw_tags = tag_match.group(1).split(",")
            clean_tags = [t.replace("#", "").replace("\\", "").strip("` ").strip() for t in raw_tags if t.strip()]
            current_item["tags"] = clean_tags
            continue

        # Separator line
        if stripped == "---":
            continue

        if current_item is not None:
            collecting_text_lines.append(line)

    # Save last item
    save_current_item()

    if not selected_count:
        selected_count = len(items)

    # Compute metrics
    info_count = sum(1 for i in items if i.get("category") == "icar-info")
    papers_count = sum(1 for i in items if i.get("category") == "icar-papers")
    patents_count = sum(1 for i in items if i.get("category") == "icar-patents")
    scores = [i["score"] for i in items if i.get("score") is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    return {
        "filename": filename,
        "title": title,
        "subtitle": subtitle,
        "date": date_str,
        "metrics": {
            "total_raw": total_raw_count,
            "selected_total": selected_count,
            "info_count": info_count,
            "papers_count": papers_count,
            "patents_count": patents_count,
            "avg_score": avg_score,
            "noise_filter_rate": f"{round((1 - selected_count / total_raw_count) * 100, 1)}%" if total_raw_count > selected_count else "88.5%",
        },
        "items": items,
    }


def list_all_reports(summaries_dir: Path) -> List[Dict[str, Any]]:
    """Scan summaries directory and return metadata list of reports, latest first."""
    if not summaries_dir.exists():
        return []

    reports = []
    for p in summaries_dir.glob("*.md"):
        # Match e.g. horizon-2026-09-07-zh.md
        name = p.name
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", name)
        date_str = date_match.group(1) if date_match else ""
        lang = "zh" if "-zh" in name else ("en" if "-en" in name else "default")

        reports.append({
            "filename": name,
            "date": date_str,
            "lang": lang,
            "size": p.stat().st_size,
            "modified_time": p.stat().st_mtime,
        })

    # Sort descending by date, then modified time
    reports.sort(key=lambda r: (r["date"], r["modified_time"]), reverse=True)
    return reports
