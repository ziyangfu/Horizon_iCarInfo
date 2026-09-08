"""Automated tests for Horizon_iCarInfo Pluggable Web UI & Dashboard."""

import threading
import time
from pathlib import Path
import httpx
import pytest

from src.ui.parser import list_all_reports, parse_summary_markdown
from src.ui.server import DashboardRequestHandler, ThreadingHTTPServer, SUMMARIES_DIR


def test_parser_basic():
    """Verify markdown parser extracts metrics and items properly."""
    sample_md = """# 智能汽车资讯每日速递 - 2026-09-07
> 从 60 条内容中筛选出 2 条重要资讯。

---

## 智能汽车与底盘前瞻资讯

<a id="item-icar-info-1"></a>
### [同驭汽车线控转向系统申报金辑奖](https://example.com/item1) ⭐️ 4.5/10

同驭汽车线控转向系统首发。

google_news · 同驭 · 9月7日 10:00

**「技术突破」** 转向执行与触觉反馈独立解耦。

**标签**: `#steering`, `#vehicle-motion-control`

---

## 前瞻专利

<a id="item-icar-patents-1"></a>
### [采埃孚线控转向专利申报](https://example.com/item2) ⭐️ 5.0/10

Google Patents · 专利号: CN112590921B · 申请人: 采埃孚(ZF) · 公开日: 2026-09-01

**标签**: `#steering`, `#supplier-news`
"""
    parsed = parse_summary_markdown(sample_md, "horizon-2026-09-07-zh.md")
    assert parsed["title"] == "智能汽车资讯每日速递 - 2026-09-07"
    assert parsed["metrics"]["total_raw"] == 60
    assert parsed["metrics"]["selected_total"] == 2
    assert parsed["metrics"]["patents_count"] == 1
    assert parsed["metrics"]["info_count"] == 1
    assert len(parsed["items"]) == 2

    # Check patent details
    patent_item = parsed["items"][1]
    assert patent_item["category"] == "icar-patents"
    assert patent_item["patent_number"] == "CN112590921B"
    assert patent_item["patent_applicant"] == "采埃孚(ZF)"
    assert patent_item["patent_pub_date"] == "2026-09-01"


def test_list_all_reports():
    """Verify listing existing reports returns valid records."""
    reports = list_all_reports(SUMMARIES_DIR)
    assert isinstance(reports, list)
    assert len(reports) > 0
    assert any("2026-09-07" in r["filename"] for r in reports)


def test_ui_http_server_endpoints():
    """Verify HTTP server endpoints return valid JSON and HTML."""
    # Spin up test server on port 8999
    port = 8999
    httpd = ThreadingHTTPServer(("127.0.0.1", port), DashboardRequestHandler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    time.sleep(0.3)

    try:
        base_url = f"http://127.0.0.1:{port}"

        # 1. Health endpoint
        res = httpx.get(f"{base_url}/api/health", timeout=5.0)
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

        # 2. Reports list endpoint
        res = httpx.get(f"{base_url}/api/reports", timeout=5.0)
        assert res.status_code == 200
        reports_data = res.json()
        assert reports_data["code"] == 0
        assert len(reports_data["data"]) > 0

        # 3. Report detail endpoint
        target_filename = reports_data["data"][0]["filename"]
        res = httpx.get(f"{base_url}/api/reports/{target_filename}", timeout=5.0)
        assert res.status_code == 200
        detail = res.json()["data"]
        assert "metrics" in detail
        assert "items" in detail

        # 4. Whitelist GET endpoint
        res = httpx.get(f"{base_url}/api/whitelist", timeout=5.0)
        assert res.status_code == 200
        wl_data = res.json()["data"]
        assert "stats" in wl_data
        assert "raw_config" in wl_data
        assert wl_data["stats"]["p0_topics_count"] > 0

        # 5. Whitelist POST endpoint
        raw_config = wl_data["raw_config"]
        # Backup original list
        orig_p0 = list(raw_config.get("topics", {}).get("p0_core", []))
        test_keyword = "__test_vmc_auto_tuning_term__"
        raw_config["topics"]["p0_core"].insert(0, test_keyword)

        post_res = httpx.post(f"{base_url}/api/whitelist", json=raw_config, timeout=5.0)
        assert post_res.status_code == 200
        post_json = post_res.json()
        assert post_json["code"] == 0

        # Verify through subsequent GET
        verify_res = httpx.get(f"{base_url}/api/whitelist", timeout=5.0)
        assert verify_res.status_code == 200
        verify_data = verify_res.json()["data"]
        assert verify_data["raw_config"]["topics"]["p0_core"][0] == test_keyword

        # Clean up: restore original configuration
        raw_config["topics"]["p0_core"] = orig_p0
        restore_res = httpx.post(f"{base_url}/api/whitelist", json=raw_config, timeout=5.0)
        assert restore_res.status_code == 200

        # 6. HTML Index
        res = httpx.get(f"{base_url}/", timeout=5.0)
        assert res.status_code == 200
        assert "Horizon_iCarInfo" in res.text
        assert "CHASSIS RADAR" in res.text

    finally:
        httpd.shutdown()
        httpd.server_close()

