# MDPI Vehicles 前沿论文数据源接入与配额控制实现计划

根据需求与用户确认：
1. **底层接口**：采用 **Crossref API**（通过 ISSN: `2624-8921`）合规、免 Key、免登录直接采集 MDPI Vehicles 期刊元数据。
2. **初筛与过滤机制**：采用**方案 A（全量拉取后由 LLM 提示词统一按 VMC 权重打分初筛）**，避免关键词漏检。
3. **配额与遴选规则**：针对「总的前沿论文栏目最多 3 篇」，采用**方案 A（质量优先自由竞争）**——将 ArXiv 论文（`arxiv-paper`）与 MDPI 论文（`mdpi-paper`）统一归入 `digest.category_groups.papers`（`limit: 3`），所有通过初筛的论文按 AI 分析得分从高到低统一排序，严格截取前 3 篇。
4. **配置项命名规范**：采用通用的 `sources.crossref` 列表结构（配置 `issn: "2624-8921"`, `journal_name: "MDPI Vehicles"`, `category: "mdpi-paper"`, `profile: "icar-papers"`）。

---

## 实施路线图

1. **[src/models.py](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/src/models.py)**：
   - 在 `SourceType` 中添加 `CROSSREF = "crossref"`。
   - 新增 `CrossrefJournalConfig` 模型，在 `SourcesConfig` 中新增 `crossref: List[CrossrefJournalConfig]`。
   - 更新 `SOURCE_REGISTRY`。
2. **[src/scrapers/crossref.py](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/src/scrapers/crossref.py)**：
   - 编写学术期刊抓取器 `CrossrefScraper`，基于 Crossref Works 接口获取期刊元数据。
   - 提取 DOI、中英文论文标题、发表日期、作者、去除 JATS XML 标签的高清摘要与 MDPI 官方链接。
3. **[src/orchestrator.py](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/src/orchestrator.py)**：
   - 在采集阶段 `collect_items` 中调度 `CrossrefScraper`。
   - 在子来源标识 `_sub_source_label` 中支持 DOI / 期刊名称展示。
4. **[data/config.icar.json](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/data/config.icar.json)** 及 **[data/config.json](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/data/config.json)**：
   - 添加 `sources.crossref` 配置项（配置 MDPI Vehicles, ISSN: 2624-8921）。
   - 在 `digest.category_groups.papers.categories` 中增加 `"mdpi-paper"`，保持 `limit: 3`。
5. **[tests/test_crossref.py](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/tests/test_crossref.py)**：
   - 编写单元测试，验证元数据解析、XML 摘要清洗、时间过滤以及 3 篇论文跨源混合配额截断。
