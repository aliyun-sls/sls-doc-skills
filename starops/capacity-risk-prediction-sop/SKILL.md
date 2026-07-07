---
name: capacity-risk-prediction-sop
description: 容量风险预测 Guide Skill，引导 Agent 按 design 完成 STAROps Mission + Runtime Skill 的创建、验证和证据回写。预测层使用 SLS series_forecast 与 series_describe，由 Mission Profile 驱动，已在 checkout 链路 demo 跑通 Mission 验证。
---

# 容量风险预测 Mission Guide Skill

本 Guide Skill 用于指导 Agent 或用户把容量风险预测落成 STAROps 长期 Mission。目标是让数字员工绑定容量风险预测 Runtime Skill，按 Mission Profile 周期运行，输出风险报告，并在 Warning / Critical 或跨产品共振时通知。

## 重要边界

- `meta-skill-sample/` 是按最新 design 实现的 Runtime Skill，使用 SLS `series_forecast` / `series_describe`，由 Mission Profile 驱动，对象、数据源、阈值、维度均为参数注入，skill 内部不写死具体服务或资源。
- 旧版 4 域 15 项、PromQL `predict_linear` / `holt_winters`、SLS SQL `ts_predicate_arma` / `ts_decompose` 已不在当前 Runtime Skill 主路径，不得作为当前验收结论。
- Mission 验证已在 demo checkout 链路跑通，证据见 `verification.md` 与 `assets/thread-data/`（discovery、skill 构建、mission 执行三个 replay JSON）。
- 本 Skill 只指导只读预测、解释、报告和通知，不执行扩容、限流、配置修改或生产变更。

## 使用场景

当用户提出以下需求时，使用本 Skill：

- 做容量风险预测 Mission。
- 预测资源或服务还剩多久触阈。
- 把容量预测配置成长期任务。
- 让数字员工定期产出容量风险报告。
- 用 SLS 时序预测结果解释业务容量风险。
- 验证容量预测 Runtime Skill 是否符合最新 design。

不使用本 Skill 的情况：

| 需求 | 应转向 |
|---|---|
| 已触发告警的根因诊断 | `alert-rca-flow` |
| RDS 当前水位和健康巡检 | `rds-inspection-via-script` |
| 指标语义、单位或实体确认 | `umodel-metric-entity` |
| 订单、支付等业务可靠性守护 | `business-reliability-flow` |

## 前置条件

执行前必须确认：

| 条件 | 要求 |
|---|---|
| STAROps 控制台 | 可创建数字员工、配置 Skill、创建 Mission、查看报告和通知 |
| 数据源 | 至少一个真实对象具备 MetricStore、Prometheus、Logstore、APM、云产品 API 或业务指标数据 |
| 序列 | 能构造等间隔时间序列，历史窗口足够执行预测 |
| 阈值 | 有百分比阈值、产品配额、人工阈值、预算或业务 SLO |
| UModel | 至少能绑定对象、业务归属、owner 或上下游关系；缺失时需要记录降级 |
| 权限 | 全流程只读，允许查询指标、日志、拓扑和报告，不允许执行生产变更 |

## 执行流程

### 1. 生成 Mission Profile

先完成 discovery，不要让运行阶段临场猜数据源和阈值。

Profile 至少包含：

| 输入项 | 内容 |
|---|---|
| 预测对象 | 资源、实例、服务、接口、队列、bucket、Logstore、业务计数等 |
| 数据源 | MetricStore、Prometheus、Logstore、APM、云产品 API、业务指标表 |
| 序列口径 | 查询语句、时间粒度、历史窗口、聚合方式 |
| 阈值来源 | 百分比水位、产品配额、人工阈值、预算、业务 SLO |
| 候选维度 | service、route、tenant、region、namespace、bucket、caller、owner 等 |
| 运行策略 | 预测窗口、调度频率、Normal 静默、Warning / Critical 通知 |

对不可预测对象记录原因：无历史数据、字段未索引、阈值缺失、权限不足、UModel 关系缺失。

### 2. 检查 Runtime Skill 是否符合最新 design

Runtime Skill 必须实现以下预测协议：

1. 读取 Mission Profile。
2. 按 Profile 取数并构造等间隔序列。
3. 调用 `series_describe` 判断序列连续性、稳定性、周期性和显著趋势。
4. 调用 `series_forecast` 生成预测值、上界、下界和错误信息。
5. 结合阈值来源计算风险等级和触阈时间。
6. 归并单对象风险和跨产品共振。
7. 把需要解释的风险事件交给 InvestigationAgent。
8. 输出报告并触发 Mission 归档或通知。

预测函数的调用管道（实测口径，通用写法）：

- 命令走 `starops observe log_store query`，`--logstore` 指向 MetricStore 名称（不是 LogStore），`--query` 用 SPL 管道语法。
- 管道结构：`.metricstore | prom-call promql_query_range('<PromQL>') | extend ret = series_forecast(__value__, <步数>)`。`prom-call` 把 PromQL 结果转成 SPL 行集，`__value__` 是聚合值数组，`series_forecast` 在其上外推。
- `metric_store query` 只接受纯 PromQL，不支持 SPL 管道；`set session enable_remote_functions` 不需要。
- `series_forecast` 返回 8 元素数组：完整时间戳序列、完整值序列（历史加 null 填充）、预测值数组、上界数组、下界数组、输入数据点数、预测步数、null。
- `series_describe` 返回统计量（max / min / mean / std / p50 / p95）、segments（STABLE_PLATEAU / SPIKE_RECOVERY / CURVED_PEAK 等）和 transitions（TREND_REVERSAL 等）。
- 数据点需 >= 200；5 分钟粒度近 1 天约 289 点可用，1 小时粒度仅 25 点会失败。
- 比率信号（error_rate 等）在低值区噪声大，外推值可能是当前均值的数十倍。Runtime Skill 应检测这种噪声外推，标记 `confidence=unreliable` 并降级为 Normal，不直接升级为 Critical。
- CloudMonitor 云产品指标返回 JSON 格式（`__ts__` / `__value__` / `__summary__`），Runtime Skill 需按数据源类型路由解析器，不能统一按 CSV 处理。
- CloudMonitor 对象用平台 entity_id（UModel 实体 id），不是云资源 ID（如 RDS 的 `rm-...`）。

如果 Runtime Skill 仍依赖旧版 4 域 15 项、PromQL `predict_linear`、`holt_winters`、`ts_predicate_arma` 或 `ts_decompose` 作为主路径，只能标为旧版样例，不得标为当前 design 验收通过。

### 3. 创建数字员工和 Mission

在 STAROps 中创建用于容量运营的数字员工，并绑定符合最新 design 的 Runtime Skill。

Mission 配置必须引用 Profile，并明确：

- 运行频率。
- 覆盖对象范围。
- 预测窗口。
- 通知策略。
- Normal 是否静默归档。
- Warning / Critical 或共振事件的通知目标。

### 4. 运行一次真实预测

从 Profile 中选择至少一个真实对象，完成一次端到端运行。

运行结果必须能证明：

- 序列由真实数据构造。
- `series_describe` 返回序列质量信息。
- `series_forecast` 返回预测值、上界、下界或错误信息。
- 阈值来源可追溯。
- 报告包含触阈时间或明确的不可预测原因。

### 5. 验证风险归并和 Investigation handoff

当多个对象在同一时间窗共同上升时，尝试归并为一个风险事件。

归并必须有以下支撑之一：

- 共享业务。
- 共享服务。
- 共享 owner。
- 共享 region 或 namespace。
- UModel 调用关系。
- 同一时间窗的共同趋势。

需要解释的风险事件必须向 InvestigationAgent 提供预测结果、实体、时间窗、阈值来源和候选维度。Agent 输出应包含支撑证据、反证、缺口和建议。

### 6. 回写验证证据

控制台跑通后更新：

| 文件或目录 | 回写内容 |
|---|---|
| `verification.md` | Mission Profile、SLS 预测结果、风险报告、通知和 Investigation handoff 证据，记录 discovery、skill 构建、mission 执行三个 thread id |
| `meta.yaml` | Runtime Skill validation、package 状态、version changes |
| `assets/thread-data/` | discovery、skill 构建、mission 执行三个 replay JSON，脱敏后入库 |
| `assets/` | Profile、报告、通知、必要截图或样例输出 |
| `meta-skill-sample/` | 符合最新 design 的 Runtime Skill 实现 |

## 输出结构

最终报告应按风险事件组织，而不是按产品清单堆叠。

| 模块 | 内容 |
|---|---|
| 风险摘要 | 风险等级、预计触阈时间、影响业务、建议响应时限 |
| 预测证据 | 当前值、预测值、预测上界 / 下界、序列描述、算法错误信息 |
| 阈值来源 | 产品百分比阈值、人工阈值、产品配额、文档规格、历史基线或业务 SLO |
| 共振证据 | 同一时间窗同步上升的产品、服务、维度组合 |
| Agent 解释 | 主贡献维度、支撑证据、反证、证据缺口、置信度 |
| 处置建议 | 扩容、限流、错峰、优化、配额调整、缓存、降噪、后续验证 |

## 降级规则

| 情况 | 处理 |
|---|---|
| 序列点不足 | 标注历史数据不足，不运行预测 |
| 预测函数返回错误 | 保留错误信息和对象上下文，不写成预测成功 |
| 阈值缺失 | 保留预测结果和补阈值建议，不升级为 Critical |
| 数据源不可读 | 在 Mission Profile 中标注排除或待补权限 |
| UModel 关系缺失 | Investigation 降级为维度贡献分析，并给出补关系建议 |
| 多信号证据冲突 | 保留反证和缺口，进入人工复核或开放调查 |
| 比率信号噪声外推 | 标记 `unreliable` 并降级为 Normal，不升级为 Critical |

## 验收标准

| 验收项 | 通过标准 |
|---|---|
| Runtime Skill | 使用 `series_describe` 和 `series_forecast` 执行预测，不用大模型做数值外推 |
| Mission Profile | 包含预测对象、数据源、序列口径、阈值来源、候选维度、调度和通知规则 |
| discovery | 每个对象都有可用、降级或排除结论；缺阈值对象不得直接进入 Critical |
| 真实预测 | 至少一个真实对象完成 SLS 预测，报告展示预测值、上下界、序列质量和触阈时间 |
| 风险归并 | 能把相关对象共同上升归并为风险事件，或明确证明当前无共振 |
| Investigation handoff | 解释型风险事件能交付实体、时间窗、阈值来源和候选维度 |
| 报告通知 | Normal 归档，Warning / Critical 或共振事件通知，报告保留支撑证据、反证和缺口 |

demo checkout 链路的验证记录见 `verification.md`，replay 见 `assets/thread-data/`。
