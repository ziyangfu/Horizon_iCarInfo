# 智能汽车与底盘前瞻专利爬虫实现计划（已确认执行）

根据用户反馈与确认：
1. **检索模式**：采用**方案 1**（主动组合配置），在配置文件中配置核心检索词与重点跟踪的专利申请人（Bosch、ZF、Continental、伯特利、同驭科技、拿森科技、比亚迪、华为等）。
2. **入选配额**：每日生成文档中**最多保留 3 条**高质量专利（与前沿论文保持一致）。
3. **语言处理**：**统一使用中文**，外文专利通过 AI 翻译并提炼核心技术要点。

---

## 实施路线图

1. **[src/models.py](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/src/models.py)**：
   - 在 `SourceType` 中添加 `PATENTS = "patents"`。
   - 新增 `PatentQueryConfig` 模型，在 `SourcesConfig` 中新增 `patents: List[PatentQueryConfig]`。
   - 更新 `SOURCE_REGISTRY`。
2. **[src/scrapers/google_patents.py](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/src/scrapers/google_patents.py)**：
   - 编写专利抓取器 `GooglePatentsScraper`，基于 Google Patents XHR 接口，支持关键词与 Assignee 组合、排序与过滤。
   - 提取完整专利号、中英文专利标题、公开日期、申请日、申请人、发明人、摘要与 Google Patents 链接。
3. **[src/orchestrator.py](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/src/orchestrator.py)**：
   - 在采集阶段 `collect_items` 中调度 `GooglePatentsScraper`。
   - 在子来源标识 `_sub_source_label` 中支持专利展示。
4. **[data/config.icar.json](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/data/config.icar.json)** 及 **[data/config.json](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/data/config.json)**：
   - 添加 `sources.patents` 配置项（配置核心线控检索词及重点国内外供应商/OEM）。
   - 在 `digest.category_groups` 中配置 `patents` 配额为 3（`limit: 3`, `categories: ["chassis-patent"]`）。
5. **[profiles/icar-patents/](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/profiles/icar-patents/)**：
   - 升级 `analysis.md` 和 `enrichment.md`，要求输出中文、分析专利创新点与壁垒、打上 16 大分类标签。
6. **全面测试与验证**：
   - 验证爬虫抓取、配额截断、AI 分析打分及每日汇总展示。
