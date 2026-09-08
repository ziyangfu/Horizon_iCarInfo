# Horizon_iCarInfo 智能汽车底盘前瞻情报看板 (Web UI Dashboard) 交付报告

我们已成功为 **Horizon_iCarInfo** 搭建了面向 AI 竞赛与日常工程研发的 **轻量级、可插拔、高颜值 Web UI 前瞻情报看板 (Chassis Intelligence Dashboard)**。

---

## 核心设计与特性

### 1. 架构可插拔与零干扰终端 (Pluggable & Zero Interference)
* **独立模块隔离**：所有 UI 服务端与前端资源均收敛在 `src/ui/` 目录下，完全不侵入 `src/main.py`、`src/orchestrator.py` 以及抓取/推理管线。
* **零额外重量级依赖**：后端基于 Python 3 标准库的多线程 `ThreadingHTTPServer` 实现，无需额外安装或配置复杂的全栈构建工具链，秒级冷启动。
* **终端独立运行**：用户可以在终端照常运行 `uv run horizon ...` 执行抓取或生成，同时在浏览器中打开 UI 看板，两者互不影响、各司其职。

### 2. 现代清爽通透的高级纯白/亮色设计 (Clean White / Light Tech Theme)
* **视觉语言**：底色采用柔和干净的暖白与浅灰（`#f8fafc`），主卡片与顶栏采用纯白表面（`#ffffff`），搭配极为淡雅的汽车工程科技蓝微光氛围。
* **清晰可读性**：标题与正文采用深沉雅致的高对比 Slate 墨黑（`#0f172a`、`#334155`），大幅提升长时间阅读专业底盘文献的舒适度。
* **微动效与沉浸式卡片**：
  - **4 态势大屏 KPI 卡片**：精选情报提纯数、降噪过滤比、顶刊论文数（带 `🔓 OA` 标识）、核心专利数、VMC 领域评分加权。
  - **板块专有色系与徽标**：行业资讯（清爽天蓝）、顶刊论文（翡翠绿）、核心专利（质感琥珀金）。
  - **深度技术解构手风琴**：支持一键展开【技术背景与工程挑战】、【技术突破】、【行业影响与客观评价】、【权威溯源参考】。

### 3. 便捷的功能交互
* **历史速递期数随心切换**：顶部下拉框自动扫描 `data/summaries/` 历史日报，秒级切换不同日期。
* **动态热点标签云**：自动统计当前期数中高频出现的动力学/控制术语（`#vehicle-motion-control`, `#braking`, `#steering` 等），点击即可单选过滤。
* **实时全文模糊检索**：输入厂商（如“伯特利”、“采埃孚”）或技术词汇（如“线控转向”、“EMB”），即刻过滤匹配。
* **底盘知识白名单在线可配置**：
  - 点击右上角「🧬 底盘知识白名单」，滑出全新升级的交互式配置面板。
  - **可视化编辑模式**：支持按 P0/P1 控制主题、Tier-1/OEM 核心供应商、负向降噪关键词切换维度；支持一键添加新词条（支持回车快捷添加）与点击 `✕` 删除词条。
  - **JSON 源码高级编辑模式**：提供内置代码高亮编辑器与「✨ 格式化 JSON」排版功能，并具备实时语法错误防御。
  - **原子保存与自动备份**：点击「💾 保存并生效」通过 `POST /api/whitelist` 接口保存到 `data/vmc_whitelist.json`，自动触发 `.bak` 备份并实时热重载，伴随优雅的 Toast 提示。

---

## 使用方法

### 方式一：使用内置快捷指令启动
在项目根目录运行：
```bash
uv run horizon-ui
```
或指定端口和绑定地址：
```bash
uv run horizon-ui --port 8080 --host 127.0.0.1
```

### 方式二：使用 Python 模块直接启动
```bash
python3 -m src.ui.server --port 8080
```

打开本地浏览器访问：**`http://127.0.0.1:8080`**

---

## 自动化测试与验证

自动化测试位于 `tests/test_ui_server.py`：
- `test_parser_basic`：验证 Markdown 摘要结构化解析（包含三大板块、评分、标签、深度字段、专利公开号）。
- `test_list_all_reports`：验证日报扫描与排序逻辑。
- `test_ui_http_server_endpoints`：验证 HTTP 服务端口上的 `/api/health`、`/api/reports`、`/api/whitelist` 及静态网页 `index.html` 响应。

**测试执行结果**：
```text
tests/test_ui_server.py ...                                              [100%]
============================== 3 passed in 1.04s ===============================
```
回归测试原有 `test_crossref.py` 与 `test_google_patents.py` 共 13 个用例全部通过，终端 `uv run horizon --help` 完美兼容。
