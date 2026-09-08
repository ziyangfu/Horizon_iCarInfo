# 前瞻专利纯净度治理与真专利硬隔离执行记录

## 任务背景
用户提出明确要求：**“专利这一部分，必须是确定的专利，也就是仅仅来源于例如 google patents 等专门用于爬取专利的数据搜集器。”**
并且确认：
1. **当指定时间窗口内无真实专利时，第三板块保持为空或不展示，绝不填充任何新闻代替**。
2. **扩充专利关键词与申请人名单**，涵盖更多整车运动控制、智能控制相关专利及国内外核心线控 Tier-1 / OEM。

---

## 核心排查结论与整改详情

### 1. 拔除伪专利新闻回退漏洞 (`src/scrapers/google_patents.py`)
- **根因**：原 `GooglePatentsScraper` 在 Attempt 1（XHR 接口）遇到 503 限流或超时时，会回退到 `_fetch_from_patent_syndication`，通过 `news.google.com/rss/search` 抓取媒体新闻报道并打上 `[专利]` 标签冒充专利。
- **整改**：
  - 彻底删除了全部基于 Google News RSS 的伪专利回退逻辑。
  - 坚守**宁缺毋滥**原则：若无确凿的专利公开，直接返回空列表 `[]`，绝不拿新闻资讯充数。

### 2. 重构 Google Patents 真实专利检索与双重防御通道
- **修复 URL 编码与检索结构**：消除了 XHR 接口调用中的双重 URL 编码问题。
- **真专利定向索引检索备选通道**：
  - 当 Google Patents XHR 遭遇偶发 503 拦截时，通过专用通道对 `site:patents.google.com/patent/` 进行定向专利检索。
  - **严格专利号校验**：只接受匹配 `^[A-Z]{2}[0-9A-Z]{5,}$`（如 `CN114735076B`, `US2026...`）的真实法律专利文献，提取官方 Google Patents 直达页面（`https://patents.google.com/patent/{pub_num}/zh`），确保每个条目都具备国家知识产权局公开号与官方专利库出处。

### 3. 数据源强隔离守卫 (`src/ai/classifier.py`)
- 在分类器 `ContentClassifier.resolve` 中增加硬隔离断言：
  - **非 `SourceType.PATENTS` 来源的任何数据（如 RSS、Google News、Twitter 等），绝对禁止被赋予 `icar-patents` 档案**，即使内容包含“专利”字样或显式指定，也会强制剔除或降级为默认资讯，阻断资讯类文章误入专利板块的任何可能。

### 4. 扩充运动控制/智能控制关键词与申请人名单 (`data/config.icar.json`, `data/config.json`)
- **扩充关键词**：
  - 新增：`整车运动控制`, `运动控制`, `智能控制`, `控制分配`, `纵横向协同控制`, `车身姿态控制`, `动力学控制`, `底盘域控`, `转矩矢量`, `侧偏角估计`, `质心侧偏角`, `滑移率控制`, `制动能量回收`, `主动后轮转向`, `容错控制`, `control allocation`, `torque vectoring`。
- **扩充申请人 (Tier-1 与前沿车企)**：
  - 国内线控新锐：伯特利、同驭、拿森、利氪、格陆博、英创汇智、恒隆、万向、亚太机电、拓普。
  - 国际一线巨头：博世(Bosch)、采埃孚(ZF)、大陆(Continental)、耐世特(Nexteer)、舍弗勒(Schaeffler)、布雷博(Brembo)、日立(Hitachi)。
  - 整车厂与科技厂商：比亚迪、华为、地平线、吉利、蔚来、小鹏、理想、小米汽车。

### 5. 格式化排版增强 (`src/ai/summarizer.py`)
- 专利板块生成时，来源行由原本通用的作者信息，升级为专业的专利法律标识：
  `Google Patents · 专利号: CN121822331A · 申请人: 比亚迪股份有限公司 · 公开日: 2026-04-10`

---

## 验证结果

1. **单元测试**：
   - 运行 `.venv/bin/pytest tests/test_google_patents.py -v`（7 个测试全部通过）：
     - `test_google_patents_scraper_disabled`: PASS
     - `test_google_patents_valid_publication_number_check`: PASS
     - `test_google_patents_fetch_from_xhr_valid`: PASS
     - `test_google_patents_empty_when_no_genuine_patents_found`: PASS (验证无专利时返回空，不回退新闻)
     - `test_google_patents_index_fallback_only_accepts_patent_urls`: PASS (验证非专利新闻链接被严格丢弃)
     - `test_classifier_strictly_isolates_icar_patents`: PASS (验证非 PATENTS 数据源绝对无法进入 icar-patents)
     - `test_summarizer_renders_patent_metadata`: PASS (验证专利号、申请人、公开日正规排版展示)

2. **真实网络调用实测**：
   - 运行真实爬虫获取最新专利，成功抓取 5 项真实底盘与运动控制发明专利：
     - `CN112590921B`: 一种智能汽车冗余线控转向装置及其控制方法
     - `CN114735076B`: 一种差动协同线控转向的容错控制方法
     - `CN110901761A`: 线控转向系统和用于估计线控转向系统的齿条力的方法
     - `CN107000782B`: 转向装置以及用于控制转向装置的方法
     - `CN119239743A`: 一种双路冗余转向机械结构
   - 所有条目均为带国别公开号的真实法律专利文献，直达 Google Patents 官方页面，100% 杜绝媒体新闻。
