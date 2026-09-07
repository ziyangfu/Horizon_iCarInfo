# Horizon VMC Topic & Supplier Whitelist 用户自定义指南

本文档介绍如何通过配置文件 [data/vmc_whitelist.json](file:///home/fzy/Documents/03_competition/Horizon_iCarInfo/data/vmc_whitelist.json) 自定义您关注的 **Vehicle Motion Control (VMC) / Chassis Motion Control (CMC)** 主题、厂商、产品及降噪规则。

---

## 一、配置文件位置

- 文件路径：`data/vmc_whitelist.json`
- 格式：标准 JSON 格式

系统在运行内容分析（AI打分与筛选）时，会**自动、动态**地读取该文件中的全部配置并注入到底层 AI 评分提示词中。因此，**您在此文件中添加或修改任何内容，无需改动任何代码，立即在下次运行时生效**。

---

## 二、配置结构说明

`data/vmc_whitelist.json` 包含四大主要部分：

### 1. `topics`（技术主题白名单）
分为四个优先级分级：
- **`p0_core`（核心主题，命中权重 +5）**：
  整车运动控制顶层架构、控制分配、线控转向/制动/悬架、状态估计、直接横摆力矩控制等最核心主题。
  *示例*：
  ```json
  "p0_core": [
    "vehicle motion control",
    "steer-by-wire",
    "brake-by-wire",
    "sideslip angle estimation"
  ]
  ```
- **`p1_strongly_related`（强相关主题，命中权重 +3）**：
  分布式驱动、四电机控制、主动后轮转向、电控减振 CDC、路面附着估计等。
- **`p2_methods_tools_ai`（算法/软件/工具/仿真，命中权重 +1）**：
  先进控制算法（MPC、滑模、卡尔曼滤波）、底盘域控软件架构、动力学仿真（CarSim、HiL）。
- **`p3_broad_context_required`（泛汽车/需结合上下文，单独命中为 0 分）**：
  通用控制词（如通用 MPC、Kalman 等）。**必须与 P0/P1 主题共同命中才计算**。

> **如何添加新主题或产品**：
> 直接在对应分级的数组中添加英/中文关键词字符串即可。例如在 `p0_core` 中添加 `"EMB clamping force control"`（EMB 夹紧力控制）。

---

### 2. `suppliers`（供应商与厂商白名单）
分为四个分级：
- **`p0_core`（核心 Tier-1 供应商，命中权重 +4）**：
  如博世 (Bosch)、采埃孚 (ZF)、大陆 (Continental)、耐世特 (Nexteer)、伯特利 (Bethel)、同驭科技、拿森科技等。
- **`p1_tier1`（专业底盘/转向/制动/悬架供应商，命中权重 +2）**：
  如京西重工 (BWI)、KYB、天纳克 (Tenneco)、蒂森克虏伯、英创汇智、利氪科技、格陆博科技、经纬恒润等。
- **`p2_tools_software_services`（工程工具/软件/服务商，命中权重 +1）**：
  如 Vector、dSPACE、IPG Automotive、MathWorks、Ansys 等。
- **`p3_oem`（整车厂 OEM，单独命中为 0 分，必须与 P0/P1 主题结合）**：
  如比亚迪、吉利、蔚来、理想、小鹏、特斯拉、华为乾崑等。

> **如何添加感兴趣的厂商**：
> 如果您关注某家新的线控底盘供应商（例如“比博斯特”或某新兴创业团队），只需将其添加到 `p0_core` 或 `p1_tier1` 的列表中即可：
> ```json
> "p0_core": [
>   "Bosch",
>   "博世",
>   "比博斯特",
>   "Bibo"
> ]
> ```

---

### 3. `noise_reduction`（降噪与扣分规则）
- **`penalize_keywords`（强降噪词）**：
  命中此类词汇（如车型月度销量、降价促销、车机娱乐、纯视觉识别、财报股票等），内容得分将被**强制压低至 2 分以下（Noise 丢弃）**。
- **`protected_keywords` 与 `required_vmc_context`（保护项）**：
  自动驾驶 (Autonomous Driving)、ADAS、AI 等词汇不会直接一刀切剔除，但**必须且仅当其与底盘运动控制、动力学、轮胎、转向、制动等上下文结合时才被保留**。

---

### 4. `daily_categories`（16 个标准日报标签分类）
系统在分析产出 `tags` 标签时，统一收敛在这 16 个标准化分类：
1. `vehicle-motion-control`（整车运动控制）
2. `control-allocation`（控制分配与协调）
3. `stability-control`（稳定性与横摆力矩）
4. `braking`（线控制动）
5. `steering`（线控转向）
6. `distributed-drive`（分布式驱动）
7. `suspension`（主动与半主动悬架）
8. `state-estimation`（车辆状态估计）
9. `tire-road-estimation`（路面附着与轮胎力估计）
10. `control-algorithms`（先进控制算法）
11. `software-defined-chassis`（软件定义底盘）
12. `ai-vehicle-dynamics`（AI与动力学校准）
13. `simulation-validation`（动力学仿真与虚拟标定）
14. `supplier-news`（核心供应商动态）
15. `research-paper`（前沿学术论文）
16. `open-source`（开源项目与模型）

---

## 三、修改生效验证方法

修改完成后，您可以在终端运行以下命令快速验证 JSON 语法和动态注入效果：

```bash
uv run python -c "from src.processing.whitelist import load_vmc_whitelist; print('VMC 规则已正确加载，P0核心词数:', len(load_vmc_whitelist()['topics']['p0_core']))"
```
