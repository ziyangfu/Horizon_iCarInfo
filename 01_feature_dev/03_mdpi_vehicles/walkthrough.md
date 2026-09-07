# MDPI Vehicles 前沿论文数据源接入与配额控制执行记录

## 任务背景
在每日文档生成的第二部分「二、前沿论文 (`icar-papers`)」中，原先仅接入了 ArXiv 数据源。现通过 Crossref API（ISSN: `2624-8921`）接入 **MDPI Vehicles** 期刊的学术论文，并确保第二板块「前沿论文」**总篇数最多只有 3 篇**。

---

## 核心实现说明

1. **数据模型扩展 (`src/models.py`)**：
   - 增加 `SourceType.CROSSREF = "crossref"` 枚举值及注册。
   - 新增 `CrossrefJournalConfig`，并在 `SourcesConfig` 中新增 `crossref: List[CrossrefJournalConfig]`。

2. **学术期刊抓取器 (`src/scrapers/crossref.py`)**：
   - 基于 Crossref 官方 Works 接口（`https://api.crossref.org/journals/{issn}/works`）实现。
   - 包含 Polite Pool 标识，免认证、零反爬风险。
   - 实现 JATS XML 标签清洗算法，提取纯净摘要；精确解析作者序列与多级发表时间。
   - 生成格式为 `ContentItem`，标题统一增加 `[Paper]` 前缀，元数据附带 `doi`、`issn`、`journal`、`summary` 与 `authors`。

3. **调度与展示集成 (`src/orchestrator.py`)**：
   - 在 `collect_items` 中增加对 `crossref` 抓取器的异步并发采集与进度提示。
   - 在 `_sub_source_label` 中支持 Crossref 论文显示 `MDPI Vehicles:10.3390/...`。

4. **配置与配额均衡 (`data/config.icar.json`, `data/config.json`)**：
   - 在 `sources` 中配置 `crossref` 数据源（ISSN `2624-8921`，MDPI Vehicles，`category: "mdpi-paper"`，`profile: "icar-papers"`）。
   - 在 `digest.category_groups.papers` 中将 categories 配置为 `["arxiv-paper", "mdpi-paper"]`，维持 `limit: 3`。
   - 论文在经过 AI 评分（基于 `icar-papers` 提示词与 VMC 白名单）后，由 `apply_balanced_digest` 按分值统一降序截断，严格限制 Section 2 选出的最优论文总数不超过 3 篇。

---

## 验证结果

1. **自动化单元测试**：
   - 运行 `.venv/bin/pytest tests/test_crossref.py -v`：
     - `test_crossref_scraper_disabled`: PASS
     - `test_crossref_scraper_clean_abstract`: PASS
     - `test_crossref_scraper_fetch_valid`: PASS
     - `test_crossref_scraper_date_filtering`: PASS
     - `test_papers_quota_limit_enforced_across_arxiv_and_mdpi`: PASS（验证模拟 3 篇 ArXiv + 3 篇 MDPI 论文通过初筛后，严格按最高分选出 3 篇前沿论文）。

2. **线上真实接口通信测试**：
   - 真实请求 Crossref API 获取 MDPI Vehicles 最近发表文献：
     - 成功获取今日与近期多篇真实论文（如 `Quantifying the “Mechanicalness” of Autonomous Trajectory Tracking`、`Trajectory Tracking Control Using MIMO-MPC` 等）。
     - 纯文本摘要长度均在 1000~2000 字符，格式完整无损，分类与链接均正确。
