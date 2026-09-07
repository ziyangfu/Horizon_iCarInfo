# Horizon VMC/CMC 技术雷达系统升级实施成果

本项目已完成对 Horizon_iCarInfo 的全链路升级，全面落实了 **《Horizon VMC Topic & Supplier Whitelist》**，并支持用户自定义维护白名单与主题。

---

## 核心改动概览

### 1. 用户可维护白名单与配置
- **[NEW] [data/vmc_whitelist.json](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/data/vmc_whitelist.json)**：
  - 完整收录 P0~P3 技术主题（49项P0核心主题、48项P1强相关、50项P2方法工具、19项P3泛控制词）。
  - 完整收录 P0~P3 供应商与厂商（博世、采埃孚、大陆、耐世特、伯特利、同驭、拿森等核心Tier-1，以及京西重工、爱信、克诺尔、英创汇智、利氪科技等专业供应商与主要车企）。
  - 配置强降噪扣分词汇（销量、促销、车机娱乐、纯视觉感知、财报等）与自动驾驶/AI上下文约束。
  - 规范 16 个标准化推荐日报分类。
- **[NEW] [docs/vmc_whitelist_guide.md](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/docs/vmc_whitelist_guide.md)**：
  - 用户操作指南，说明如何随时向 `data/vmc_whitelist.json` 中增删感兴趣的厂商、产品或关键词。
- **[NEW] [src/processing/whitelist.py](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/src/processing/whitelist.py)**：
  - 白名单加载器，支持热更新自动读取 `data/vmc_whitelist.json` 并动态格式化为 Markdown 提示词块。

### 2. 资料搜集配置升级
- **[MODIFY] [data/config.icar.json](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/data/config.icar.json)** 及 **[data/config.json](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/data/config.json)**：
  - **ArXiv 数据源**：定向增加核心关键词：`"vehicle motion control"`, `"chassis control"`, `"control allocation"`, `"sideslip angle estimation"`, `"torque vectoring"` 等。
  - **Google News 数据源**：检索 Query 增强：增加整车运动控制、底盘域控及核心 Tier-1 线控量产动态（伯特利线控、同驭科技、拿森科技、博世底盘、采埃孚底盘、大陆制动等）。
  - **生成配额控制**：在 `digest.category_groups` 中保持配置论文类最多入选 3 篇。

### 3. AI 分析打分与分类规则
- **[MODIFY] [src/ai/prompting/analysis.py](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/src/ai/prompting/analysis.py)**：
  - 动态注入从 `data/vmc_whitelist.json` 加载的最新白名单规则，用户对白名单的修改将立即可见。
- **[MODIFY] [profiles/icar-info/analysis.md](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/profiles/icar-info/analysis.md)** 与 **[profiles/icar-papers/analysis.md](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/profiles/icar-papers/analysis.md)**：
  - 嵌入量化加分权重（P0 Topic +5，P1 Topic +3，P0 Supplier +4，P1 Supplier +2 等）。
  - 强制执行 6 组准入布尔逻辑（不满足准入条件的内容直接判定为 Noise，得分 <= 2.0）。
  - 强制执行降噪扣分惩罚（销量、降价、座舱娱乐、纯感知）。
  - 规范标签输出，要求统一使用 16 个标准分类。
- **[MODIFY] [profiles/icar-info/match.md](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/profiles/icar-info/match.md)** 与 **[profiles/icar-papers/match.md](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/profiles/icar-papers/match.md)**：
  - 精准对齐 VMC/CMC 底盘与车辆运动控制定位。

---

## 验证与测试结果

运行系统自检脚本，全部通过：
- `data/config.icar.json` 与 `data/config.json`：Pydantic 校验 100% 通过。
- `data/vmc_whitelist.json`：成功解析全部 4 级主题（49项P0主题）与供应商（38项P0核心供应商）。
- `ProfileRegistry`：成功加载 `icar-info`, `icar-papers`, `icar-patents` 3大板块。
- `analysis_system_prompt`：系统提示词成功动态注入用户白名单与评分规则。
