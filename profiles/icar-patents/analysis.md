# Evaluation goal

Evaluate the innovative value, technical completeness, and patent barrier significance of patent publications in **Vehicle Motion Control (VMC) / Intelligent Chassis Systems** for chassis control architects, R&D engineers, and patent analysts.

# Language requirement

**统一使用中文进行分析与总结**。若输入为外文专利（英文/德文/日文等），必须自动将其技术方案、解决的问题与创新点准确翻译并提炼为专业地道的中文。

# Scoring rules & rubric

Calculate the score (0 to 10) based on VMC technical relevance, applicant tier, and patent barrier:

### Scoring Weights
- **P0 Topic / Core VMC (线控转向SBW, 线控制动EMB/EHB, 主动悬架, VMC整车运动控制, 侧偏角估计, 状态观测器, 容错冗余)**: +5
- **P0 核心供应商 / 主机厂 (博世, 采埃孚, 大陆, 伯特利, 同驭, 拿森, 耐世特, 舍弗勒, 比亚迪, 华为等)**: +4
- **P1 强相关底盘主题 / Tier-1 (分布式驱动, 扭矩矢量, CDC减振, 英创汇智, 利氪, 格陆博等)**: +3 / +2
- **实用结构或控制创新 (双冗余电机驱动, 间隙自适应估计, 备份制动策略)**: +2

### Score Scale
- **9-10: 突破性核心专利**。范式级底层架构创新（如纯解耦EMB电机械制动夹紧力与间隙估计、SBW手感模拟与角传动比控制、底盘集中域控容错算法等），具有极高行业技术壁垒。
- **7-8: 高价值工程专利**。针对具体工程痛点（故障诊断、冗余切换、迟滞补偿、传感器丢失估计算法、制动能量回收协同）提出扎实完整的技术交底与控制逻辑。
- **5-6: 实用型专利**。常规机械结构改进、标准传感器布置或渐进式电控逻辑。
- **3-4: 边缘/低优先级专利**。简单装饰件、非关键工装夹具，或技术壁垒较低的常规实用新型。
- **0-2: 噪声/无关专利**。与车辆运动控制和底盘系统无关的专利（纯车机界面、非底盘内饰配件、普通日用品等）。

# Tagging Requirement

In the `tags` field, select **2 to 4 tags strictly from the 16 standard categories**:
`#vehicle-motion-control`, `#control-allocation`, `#stability-control`, `#braking`, `#steering`, `#distributed-drive`, `#suspension`, `#state-estimation`, `#tire-road-estimation`, `#control-algorithms`, `#software-defined-chassis`, `#ai-vehicle-dynamics`, `#simulation-validation`, `#supplier-news`, `#research-paper`, `#open-source`.
