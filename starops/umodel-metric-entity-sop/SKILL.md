---
name: umodel-metric-entity-sop
description: STAROps UModel 使用指南 SOP Skill，加载后 Agent 将按 8 个场景引导用户识别 @ 实体提问中容易遗漏的要素，覆盖指标语义、实体拓扑、日志查询、链路追踪、事件关联等 UModel 核心概念
---

# STAROps UModel 使用指南 — SOP Skill

> 本仓 **SOP Skill** 入口：把 [人读版实践文档](https://sls.aliyun.com/doc/starops/practices/umodel-metric-entity/article.html) 的使用场景教学固化为 Agent 可加载形态。
>
> 区分：本实践无 meta skill 样品（reference 类产物 = 规范 + 样例，不是可执行业务 Skill）。

## SOP 概览

8 个步骤覆盖 UModel 主要概念的使用场景，章节顺序与 [人读版实践文档](https://sls.aliyun.com/doc/starops/practices/umodel-metric-entity/article.html) 对应：

**指标查询（MetricSet）：**
1. 指标单位确认 — data_format 必须显式取
2. 聚合口径选择 — generator / aggregator / 预聚合边界
3. 实体维度锁定 — 跨实例 avg 会掩盖单实例异常
4. UModel 缺失字段补全 — 阈值 / 采集源 / 多核归一化等业务语义需显式声明

**实体拓扑（EntitySet + EntitySetLink）：**
5. 拓扑关系分析 — 沿 Relation 链精确到具体应用与跳数

**日志查询（LogSet）：**
6. 日志查询要素确认 — 锁定 LogSet + 实体 + 时间窗口

**链路追踪（TraceSet）：**
7. 链路追踪查询引导 — MetricSet vs TraceSet 路由 + span 级分位聚合

**事件与操作手册（EventSet + RunbookSet）：**
8. 事件关联与操作手册引导 — RCA 时关联变更事件 + 查找操作手册

每个步骤都用「正例提问 → 期望返回 → 关键字段确认 + 反例对照」结构。Agent 加载本 Skill 后，遇到用户用反例方式提问时，应主动对照调整到正例。

## 步骤 1：指标单位确认

**Agent 指令**：

1. 用户提到指标值的高低判断时，先确认指标的 `data_format`
2. UModel 支持 30+ 种格式化选项，最常见的歧义是 `percent`（值域 1-100）vs `percent_decimal`（值域 0-1）
3. 如果原值已是百分比标度（0-100），不要二次乘以 100
4. 在回答中始终带上 `unit` 和 `data_format` 两个字段

**用户提问示例（正例）**：

```
@<rds-instance-id> 查 CPU 使用率，标注单位与 data_format
```

**反例对照**：

- 反例：`查 CPU 高不高` — 不确认单位，0.143 可能被误读为 14.3% 或 0.143%
- Agent 引导：先取 `unit` 和 `data_format`，再判断高低

**输出要求**：

- 指标值 + `unit`（如 `%`）+ `data_format`（如 `percent`）
- 明确指出当前值是否需要再换算

## 步骤 2：聚合口径选择

**Agent 指令**：

1. 用户问分位值（P99、P95）时，先确认 UModel 在该实体上是否有对应指标
2. 检查指标的 `generator` 字段——如果 generator 是一条带 avg 的表达式，说明该指标是预聚合平均值
3. 检查 `aggregator` 字段——决定跨维度合并时用什么函数
4. APM 服务层指标多为 generator 预聚合的平均值，**不直接提供请求级 P99**
5. 对预聚合平均序列再做 P99 ≠ 请求级 P99，必须向用户说明区别
6. 想要请求级 P99 必须走 TraceSet（路由到步骤 7）

**用户提问示例（正例）**：

```
@<app-name> 查最近 1h 的 avg_request_latency_seconds，列出 mean / min / max / p50 / p75 / p95 关键统计量；这些统计量是基于哪一层数据计算的？
```

**反例对照**：

- 反例：`@<app-name> 查响应延迟的 P99` — UModel 没有该指标，模型可能把"对 avg 序列做 P99"误称为"请求级 P99"
- Agent 引导：主动告知"UModel APM 服务层无 P99"，给出 avg 序列 + 统计量的替代方式；若确需请求级 P99，路由到步骤 7（TraceSet）

**输出要求**：

- 关键统计量表（mean / min / max / p50 / p75 / p95）+ 单位
- 明确声明"这些是对预聚合平均序列再分位，不是请求级 P99"
- 如需请求级 P99，给出 TraceSet 替代方案

## 步骤 3：实体维度锁定

**Agent 指令**：

1. 用户问"集群 / 一批实例 / 所有 Pod"的指标时，先确认是否会跨实体聚合
2. 跨实体 avg 会掩盖单实例飙高的异常，告警判断失真
3. 主动按实体 ID 维度独立 group by

**用户提问示例（正例）**：

```
@<rds-instance-id> 查 CPU 使用率，按 instanceId 独立统计，不要跨实例聚合
```

**反例对照**：

- 反例：`查 RDS 集群的 CPU` — 跨实例 avg，单实例 CPU 飙高被其他健康实例平均掉
- Agent 引导：先锁定具体 EntitySet（如 `acs.rds.instance`），按 instanceId 维度独立返回，再让用户决定是否再聚合

**输出要求**：

- EntitySet 名称（如 `acs.rds.instance`）
- 按 instanceId 独立的时间序列或当前值
- 明确声明未做跨实例平均

## 步骤 4：UModel 缺失字段补全

**Agent 指令**：

1. UModel 只提供技术元数据（name / data_format / type / interval_us / 适用实体）
2. UModel **不提供**业务语义字段：异常阈值、采集源（Host OS vs Engine 内部）、多核归一化（100% 是单核满载还是全核总满载）
3. 用户问"这个指标算不算告警 / 算不算高"时，必须显式声明阈值来源，不要用模型内部猜测阈值
4. 阈值来源 3 选 1：行业建议 / 历史基线 / 业务规则

**用户提问示例（正例）**：

```
@<rds-instance-id> 查 CPU 使用率并判断是否需要告警；同时显式声明阈值来源（行业建议 / 历史基线 / 业务规则）
```

**反例对照**：

- 反例：`这个 CPU 算高吗` — 模型用未声明的内部默认阈值，无法追溯依据
- Agent 引导：返回指标值时同时给出"阈值来源 = <来源类型>: <具体阈值>"

**输出要求**：

- 指标值（带单位）
- 显式声明的阈值 + 来源
- 是否触发告警的结论 + 依据

## 步骤 5：拓扑关系分析

**Agent 指令**：

1. 用户问"某资源挂了影响什么"时，先沿 UModel EntitySetLink 展开，**不要靠猜**
2. 不同域的实体可能指向同一物理对象（如 `acs.rds.instance` ↔ `apm.external.database`），需做跨域映射
3. EntitySetLink 有 21 种关系类型，按场景选用：影响面用 `calls` / `sends_to` / `affects`；管理层级用 `contains` / `parent_of`；部署拓扑用 `runs` / `hosted_by`
4. 展开后列出受影响实体清单 + 跳数，按 BFS 层级排序
5. 如果某层展开不到（N=0），说明 trace 未覆盖或该资源在 APM 层无对应实体

**用户提问示例（正例）**：

```
@<rds-instance-id> 如果该实例不可用，会影响哪些应用？请沿 acs.rds.instance → apm.external.database → apm.service 三层 Relation 链展开，列出受影响应用清单与跳数
```

**反例对照**：

- 反例：`RDS 挂了影响什么` — 不锁拓扑，模型可能猜"影响所有应用"或漏掉间接依赖
- Agent 引导：先确认该 RDS 在 APM 层是否有对应 `apm.external.database` 实体；有则展开三层链给出 N 个受影响应用；无则告知用户拓扑展开不到

**输出要求**：

- 三层 EntitySet 展开表（每层实体数）
- 受影响应用清单（按跳数排列）+ 调用类型
- 如 N=0，明确说明原因

## 步骤 6：日志查询要素确认

**Agent 指令**：

1. 用户查日志时，先确认三要素：**哪个实体**（@ 具体实例）、**哪个 LogSet**（stdout / 审计 / 慢查询）、**什么时间窗口**
2. 一个 EntitySet 可能通过 DataLink 关联多个 LogSet，不指定 LogSet 可能返回无关日志
3. 如果用户不知道有哪些 LogSet，先通过 DataLink 查出该实体关联的所有 LogSet 清单
4. 日志查询建议带过滤条件（日志级别 / 关键词），避免返回海量无关数据

**用户提问示例（正例）**：

```
@<pod-name> 查最近 30 分钟的 stdout 日志，只看 ERROR 级别
```

**反例对照**：

- 反例：`帮我看看这个服务有没有报错` — 不锁实体、不指定 LogSet、不限时间
- Agent 引导：先问"要查哪个实例的日志？"，再通过 DataLink 列出该实体的 LogSet 清单供选择，最后要求指定时间窗口

**输出要求**：

- 锁定的实体（EntitySet + 实体 ID）
- 选定的 LogSet 名称
- 时间窗口
- 日志内容（带过滤条件后的结果）

## 步骤 7：链路追踪查询引导

**Agent 指令**：

1. 用户查 P99 / P99.9 延迟、单请求调用链、慢请求 Top N 时，需要走 TraceSet 而不是 MetricSet
2. 先确认用户的查询意图属于哪类：
   - 服务级平均趋势 → MetricSet（步骤 2）
   - 请求级分位数 → TraceSet（本步骤）
   - 单请求调用链 → TraceSet + trace_id
   - 慢请求排行 → TraceSet + span duration 排序
3. TraceSet 查询需要确认：protocol（默认 OpenTelemetry）、时间窗口、目标实体
4. 走 TraceSet 做分位聚合时，明确声明"这是对原始 span duration 的分位数，不是对预聚合平均序列的分位数"

**用户提问示例（正例）**：

```
@<app-name> 查最近 1h 的请求级 P99 延迟；走 trace 数据，对 span duration 做 99 分位聚合
```

**反例对照**：

- 反例：`@<app-name> 查 P99 延迟` — 模型可能从 MetricSet 的 avg 序列算"P99"，与请求级 P99 不等价
- Agent 引导：先判断用户要的是"服务级趋势"还是"请求级分位"；如果是后者，引导走 TraceSet

**输出要求**：

- 明确声明数据来源（MetricSet 还是 TraceSet）
- 如走 TraceSet：span duration 分位数 + 样本量
- 如走 MetricSet：声明"这是预聚合平均序列的统计量，不是请求级分位数"

## 步骤 8：事件关联与操作手册引导

**Agent 指令**：

1. 用户做 RCA 时，除了查指标和日志，还应关联 EventSet 查看同时间窗口的变更事件
2. 关联事件的三要素：**实体**（@ 具体实例）、**时间窗口**（与指标异常对齐）、**事件类型**（变更 / 告警 / 扩缩容）
3. 如果实体已关联 RunbookSet（通过 RunbookLink），优先参考操作手册中的排查路径
4. RunbookSet 当前处于 experimental 阶段，部分功能可能不稳定

**用户提问示例（正例）**：

```
@<rds-instance-id> 最近 2 小时 CPU 持续 > 80%，同时查看该实例在此时间窗口内的变更事件
```

**反例对照**：

- 反例：`为什么 RDS CPU 突然飙高？` — 不关联事件，只从指标猜原因
- Agent 引导：先确认指标异常时间窗口，然后查该实体 + 时间窗口内的 EventSet，看是否有变更事件吻合

**输出要求**：

- 指标异常时间窗口（起止时间）
- 时间窗口内的事件清单（变更 / 告警 / 扩缩容）
- 如有时间吻合的变更事件，标注为疑似根因
- 如实体关联了 RunbookSet，引导查看对应的操作手册

## 输出与交付

SOP 跑完后客户能拿到：

- **UModel 概念地图**：知道 UModel 有哪些模型、本次使用场景涉及哪些
- **正例提问模板**：8 类场景对应的可直接套用的提问句式
- **反例 → 正例对照**：哪些写法会误导 Agent、应该怎么改
- **关键字段清单**：每类提问应该取哪些字段（data_format / generator / aggregator / EntitySet / DataLink / Relation / 阈值来源）
- **数据源路由**：MetricSet vs TraceSet vs LogSet vs EventSet，按查询意图选择正确的数据源

## 失败与回滚

SOP Skill，无变更操作，无回滚需求。各步骤失败处置：

| 步骤 | 可能失败 | 处置 |
|---|---|---|
| 步骤 1 | 指标无 `data_format` 字段 | UModel 未声明，需联系 UModel 治理方补元数据；prompt 中临时由用户提供 |
| 步骤 2 | UModel 上确实只有 avg，没有 P99 | 引导走 TraceSet（步骤 7）；不要伪造 P99 |
| 步骤 3 | 用户坚持要集群级聚合 | 先按实体独立返回，再追加跨实例聚合结果，对比给出 |
| 步骤 4 | 用户未提供阈值来源 | Agent 主动列出 3 类来源请用户选，不要私自取默认 |
| 步骤 5 | 拓扑展开 N=0 | 告知用户该资源在 APM 层无对应实体，建议换实例或补齐 APM 探针 |
| 步骤 6 | 实体无关联 LogSet | 通过 DataLink 确认，告知用户该实体未接入日志；建议检查数据接入配置 |
| 步骤 7 | TraceSet 无数据或采样率过低 | 告知用户 trace 数据不足，P99 计算不可靠；建议提高采样率或扩大时间窗口 |
| 步骤 8 | EventSet 无事件记录 | 告知用户该时间窗口内无变更事件记录，RCA 需从其他维度（指标 / 日志 / 拓扑）推进 |

需要人工介入：UModel 元数据缺失（需治理方补字段）、APM 探针未覆盖关键依赖（需埋点团队补）、业务规则阈值未沉淀（需 SRE 与业务方共同定）、日志或 trace 数据未接入（需数据接入团队配置）。

## 召回 Routing

以下提问应路由到本 SOP Skill：

**指标语义类：**
- "这个指标算不算高 / 算不算告警"
- "查 CPU / 内存 / QPS 但没说单位"
- "为什么 STAROps 回答的数值跟我看到的不一样"

**聚合口径类：**
- "查 P99 延迟"（先判断走 MetricSet 还是 TraceSet）
- "查响应延迟"（确认聚合函数）

**实体维度类：**
- "@ 一个集群 / 一组实例 查指标"
- "查 RDS / ECS / Pod 集群级指标"

**拓扑分析类：**
- "这个资源挂了影响哪些应用"
- "查上下游依赖关系"

**日志查询类：**
- "帮我看看有没有报错"
- "查这个服务的日志"
- "最近有什么异常日志"

**链路追踪类：**
- "查某个请求的完整调用链"
- "慢请求 Top N"
- "请求级 P99"

**事件关联类：**
- "为什么突然出问题"
- "最近有什么变更"
- "怎么排查这个问题"（如果实体关联了 RunbookSet，优先走手册）

以下提问不应路由到本 SOP：

- 告警触发后的被动 RCA 全流程 → `alert-rca-flow`（本 SOP 只辅助 RCA 中的 UModel 查询环节）
- 业务可靠性主动巡检 → `business-reliability-flow`
- RDS 周期性巡检脚本编排 → `rds-inspection-via-script`
- 一般 prompt 工程范式 → `effective-prompts`
- UModel 底层建模（定义实体/关系） → 不在最佳实践范围内
