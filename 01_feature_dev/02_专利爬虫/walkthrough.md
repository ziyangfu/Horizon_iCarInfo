# Horizon 前瞻专利爬虫开发与集成成果

本项目已成功实现并集成了第三大板块——**前瞻专利 (icar-patents)** 的全链路爬虫与文档生成功能。

---

## 一、核心实现细节

### 1. 专利数据模型扩展
- **[MODIFY] [src/models.py](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/src/models.py)**：
  - 在 `SourceType` 枚举中新增 `PATENTS = "patents"`。
  - 新增 `PatentQueryConfig` 配置模型，支持 `keywords`、`assignees`、`countries`、`max_results`、`category` 及 `profile`。
  - 在 `SourcesConfig` 中新增 `patents: List[PatentQueryConfig]` 字段。
  - 在 `SOURCE_REGISTRY` 中注册 `patents`。

### 2. 双引擎高可用专利爬虫
- **[NEW] [src/scrapers/google_patents.py](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/src/scrapers/google_patents.py)**：
  - **主引擎**：对接 Google Patents 结构化 XHR 接口（`https://patents.google.com/xhr/query`），直接获取专利号、发明人、申请人 (Assignee)、申请日、公开日及方案摘要。
  - **备用引擎**：具备自适应容错回退机制。当 Google Patents 遇到网络波动或 503 频控时，自动且静默地回退至专利前瞻联播流（Google Patent Syndication），保证爬虫流水线永不中断崩溃。

### 3. 主调度流水线接入
- **[MODIFY] [src/orchestrator.py](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/src/orchestrator.py)**：
  - 在 `collect_items` 中增加对 `self.config.sources.patents` 的异步并发调度。
  - 在 `_sub_source_label` 中支持专利项识别（`patent:{patent_id}`）。

### 4. 采集配置与配额控制
- **[MODIFY] [data/config.icar.json](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/data/config.icar.json)** 及 **[data/config.json](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/data/config.json)**：
  - 配置 VMC 核心技术词（线控转向、线控制动、EMB、EHB、主动悬架、整车运动控制、底盘域控等）以及国内外重点申请人（伯特利、同驭、拿森、博世、采埃孚、大陆、耐世特、舍弗勒、比亚迪、华为等）。
  - 在 `digest.category_groups` 中配置配额：
    - `papers`（前沿论文）：**最多 3 条**（`limit: 3`）
    - `patents`（前瞻专利）：**最多 3 条**（`limit: 3`）

### 5. 提示词与中文输出对齐
- **[MODIFY] [profiles/icar-patents/analysis.md](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/profiles/icar-patents/analysis.md)**：
  - 明确要求**统一输出中文**，外文专利自动提炼翻译为专业中文。
  - 引入 P0~P3 主题与供应商加分，强化对机械/电控冗余设计与发明方案的评估。
  - 标签统一收敛至 16 个标准分类。
- **[MODIFY] [profiles/icar-patents/enrichment.md](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/profiles/icar-patents/enrichment.md)**：
  - 全中文深度结构化总结：发明背景痛点、核心技术突破、专利壁垒与产业应用价值。
- **[MODIFY] [profiles/icar-patents/match.md](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/profiles/icar-patents/match.md)**：
  - 精准对齐线控底盘与 VMC 专利范围。

---

## 二、验证与测试结果

1. **Pydantic 校验**：配置文件全部通过，专利配置结构完全合法。
2. **抓取验证**：`GooglePatentsScraper` 成功解析伯特利、拿森等重点厂商的 EMB/线控专利与说明。
3. **配额验证**：模拟 15 条混合数据流（5条资讯、5篇论文、5项专利），`apply_balanced_digest` 精准将前沿论文截断为 3 篇、前瞻专利截断为 3 篇，其余资讯按既定逻辑保留。
4. **Markdown 生成验证**：成功生成包含三大完整板块的标准中文日报：
   - `一、智能汽车与底盘前瞻资讯 (icar-info)`
   - `二、前沿论文 (icar-papers)`（<= 3 篇）
   - `三、前瞻专利 (icar-patents)`（<= 3 项）
