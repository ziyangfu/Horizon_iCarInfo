# Horizon_iCarInfo 智能汽车底盘前瞻情报看板 (Web UI Dashboard) 实施计划

本文档规划为项目搭建一个独立、轻量级、具备现代科技感与高颜值视觉表现的 **智能汽车底盘前瞻情报看板 (Chassis Intelligence Dashboard)**。

## 目标与原则
1. **完全可插拔 (Pluggable)**：UI 作为独立模块存在于 `src/ui/`，零侵入原有 CLI 抓取与生成管线。
2. **不影响终端使用 (Zero Interference)**：现有终端命令（如 `uv run horizon --config ...`）、日志输出、飞书推送逻辑保持 100% 不变。
3. **极速与零额外依赖 (Zero Extra Dependency)**：后端采用 Python 3.11+ 标准库 `http.server` 与多线程，无需引入复杂的重量级框架，秒级启动。
4. **高颜值与路演级设计 (Visual Excellence for Competition)**：采用现代暗色调微光设计（Dark Mode Glassmorphism）、汽车底盘电光蓝/琥珀色点缀、精美排版与微动效，专为比赛演示与工程日常使用打造。

---

## 拟修改与新增文件

### 1. 结构解析与后端服务
- **[NEW] [src/ui/__init__.py](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/src/ui/__init__.py)**: 模块初始化。
- **[NEW] [src/ui/parser.py](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/src/ui/parser.py)**:
  - 将 `data/summaries/*.md` 精准解析为结构化 JSON 数据（提取标题、星级评分、三大板块分类、标签、技术背景、技术突破、行业影响、参考链接、Open Access 标记及法律专利公开号/申请人）。
- **[NEW] [src/ui/server.py](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/src/ui/server.py)**:
  - 轻量多线程 HTTP 服务器，提供静态文件服务及 REST API：
    - `GET /api/reports`: 获取历史速递期数列表及元数据。
    - `GET /api/reports/{filename}`: 获取指定日期的结构化报告详情。
    - `GET /api/whitelist`: 获取领域白名单统计（P0~P3 主题与厂商清单），供前端知识图谱抽屉使用。
    - `GET /api/health`: 健康检查。

### 2. 前端界面与交互设计 (Vanilla CSS + JS)
- **[NEW] [src/ui/static/index.html](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/src/ui/static/index.html)**:
  - 现代化语义 HTML5 骨架，包含顶栏指挥控制区、核心 KPI 态势卡片、分类与技术标签筛选器、三大板块流式瀑布卡片、领域白名单查看抽屉。
- **[NEW] [src/ui/static/css/dashboard.css](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/src/ui/static/css/dashboard.css)**:
  - 精心调配的暗黑科技风设计系统（深灰/深蓝渐变底色、毛玻璃微反光、发光徽标、优雅圆角与响应式自适应网格）。
- **[NEW] [src/ui/static/js/dashboard.js](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/src/ui/static/js/dashboard.js)**:
  - 响应式交互逻辑：期数动态切换、板块切换过滤（资讯/论文/专利）、实时关键词搜索、白名单抽屉弹窗、折叠展开详情与一键直达。

### 3. CLI 快速启动集成 (可选便捷指令)
- **[MODIFY] [pyproject.toml](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/pyproject.toml)**:
  - 在 `[project.scripts]` 中新增 `horizon-ui = "src.ui.server:main"`，支持一键 `uv run horizon-ui` 启动看板。

---

## 验证计划

1. **服务独立性验证**：
   - 启动 UI 服务：`python3 -m src.ui.server --port 8888`
   - 确认在 UI 服务运行期间，终端执行 `uv run horizon --help` 或实际抓取命令完全不受干扰。
2. **数据解析与渲染验证**：
   - 验证 `data/summaries/` 下的最新日报（如 `horizon-2026-09-07-zh.md`）能够正确解析出：
     - 资讯卡片与深度解构（背景、突破、影响）
     - 论文卡片与 Open Access 标识
     - 专利卡片与法律专利号/申请人元数据
3. **页面功能与交互验证**：
   - 使用浏览器进行界面访问，验证：
     - KPI 指标卡片数值渲染正确
     - 分类切换（全部 / 资讯 / 论文 / 专利）实时生效
     - 搜索框实时筛选响应正常
     - 知识图谱抽屉打开流畅
