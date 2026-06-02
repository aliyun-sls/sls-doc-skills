---
name: umodel-metric-entity-sop
description: UModel 指标语义与实体拓扑教学 SOP Skill，加载后 Agent 将按 5 个样例引导用户避开 @ 实体提问的常见陷阱，覆盖单位、聚合口径、实体维度、拓扑链与缺失字段 5 类问题
---

# UModel 指标语义与实体拓扑 — SOP Skill

> 本仓 **SOP Skill** 入口：把 [人读版实践文档](https://sls.aliyun.com/doc/starops/practices/umodel-metric-entity/article.html) 的 5 样例教学固化为 Agent 可加载形态。
>
> 区分：本实践无 meta skill 样品（产物是提问范式的纠偏经验，不是可执行业务 Skill）。

## SOP 概览

5 个样例覆盖 5 类常见提问陷阱，章节顺序与 [人读版实践文档 样例 1～样例 5](https://sls.aliyun.com/doc/starops/practices/umodel-metric-entity/article.html) 一一对应：

1. 指标单位确认 — 单位 / data_format 必须显式取
2. 聚合口径选择 — UModel 提供的是否就是用户想要的口径
3. 实体维度锁定 — 跨实例 avg 会掩盖单实例异常
4. 拓扑关系分析 — 沿 Relation 链精确到具体应用与跳数
5. UModel 缺失字段补全 — 阈值 / 采集源 / 多核归一化等业务语义需显式声明

每个样例都用「正例提问 → 期望返回 → 关键字段确认 + 反例对照」三段结构。Agent 加载本 Skill 后，遇到用户用反例方式提问时，应主动纠偏到正例。

## 步骤 1：指标单位确认

**Agent 指令**：

1. 用户提到指标值的高低判断时，先确认指标的单位与 data_format
2. 如果原值已是百分比标度（0-100），不要二次乘以 100
3. 如果是 ratio（0-1），需显式换算
4. 在回答中始终带上 `unit` 和 `data_format` 两个字段

**用户提问示例（正例）**：

```
@<rds-instance-id> 查 CPU 使用率，标注单位与 data_format
```

**反例对照**：

- 反例：`查 CPU 高不高` — 不确认单位，0.143 可能被误读为 14.3% 或 0.143%
- Agent 纠偏：先取 `unit` 和 `data_format`，再判断高低

**输出要求**：

- 指标值 + `unit`（如 `%`）+ `data_format`（如 `percent`）
- 明确指出当前值是否需要再换算

## 步骤 2：聚合口径选择

**Agent 指令**：

1. 用户问 P99、P95 等分位值时，先确认 UModel 在该实体上是否真有对应指标
2. APM 服务层指标多为 generator 预聚合的平均值（如 `avg_request_latency_seconds`），**不直接提供请求级 P99**
3. 对预聚合平均序列再做 P99 ≠ 请求级 P99，必须向用户说明区别
4. 想要请求级 P99 必须走 trace duration 分布或落地到 SLS 上对原始 span 做分位聚合

**用户提问示例（正例）**：

```
@<app-name> 查最近 1h 的 avg_request_latency_seconds，列出 mean / min / max / p50 / p75 / p95 关键统计量；这些统计量是基于哪一层数据计算的？
```

**反例对照**：

- 反例：`@<app-name> 查响应延迟的 P99` — UModel 没有该指标，模型可能把"对 avg 序列做 P99"误称为"请求级 P99"
- Agent 纠偏：主动告知"UModel APM 服务层无 P99"，并给出 avg 序列 + 统计量的替代提问方式；若用户确实需要请求级 P99，引导到 trace duration 分布或 SLS span 分位聚合

**输出要求**：

- 关键统计量表（mean / min / max / p50 / p75 / p95）+ 单位
- 明确声明"这些是对预聚合平均序列再分位，不是请求级 P99"

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
- Agent 纠偏：先锁定具体 EntitySet（如 `acs.rds.instance`），按 instanceId 维度独立返回时间序列，再让用户决定是否再聚合

**输出要求**：

- EntitySet 名称（如 `acs.rds.instance`）
- 按 instanceId 独立的时间序列或当前值
- 明确声明未做跨实例平均

## 步骤 4：拓扑关系分析

**Agent 指令**：

1. 用户问"某资源挂了影响什么"时，先沿 UModel Relation 链展开，**不要靠猜**
2. 不同域的实体可能指向同一物理对象（如 `acs.rds.instance` ↔ `apm.external.database`），需做跨域映射
3. 展开后列出受影响实体清单 + 跳数，按 BFS 层级排序
4. 如果某层展开不到（N=0），说明 trace 未覆盖或该资源在 APM 层无对应实体，必须告知用户

**用户提问示例（正例）**：

```
@<rds-instance-id> 如果该实例不可用，会影响哪些应用？请沿 acs.rds.instance → apm.external.database → apm.service 三层 Relation 链展开，列出受影响应用清单与跳数
```

**反例对照**：

- 反例：`RDS 挂了影响什么` — 不锁拓扑，模型可能猜"影响所有应用"或漏掉间接依赖
- Agent 纠偏：先确认该 RDS 在 APM 层是否有对应 `apm.external.database` 实体；有则展开三层链给出 N 个受影响应用；无则告知用户拓扑展开不到，建议换实例或补齐 APM 探针

**输出要求**：

- 三层 EntitySet 展开表（每层实体数）
- 受影响应用清单（按跳数排列）+ 调用类型
- 如 N=0，明确说明原因（trace 未覆盖 / APM 探针缺失）

## 步骤 5：UModel 缺失字段补全

**Agent 指令**：

1. UModel 只提供技术元数据（指标名称 / 单位 / 数据类型 / 统计周期 / 适用实体）
2. UModel **不提供**业务语义字段：异常阈值、采集源（Host OS vs Engine 内部）、多核归一化（100% 是单核满载还是全核总满载）
3. 用户问"这个指标算不算告警 / 算不算高"时，必须显式声明阈值来源，不要用模型内部猜测阈值
4. 阈值来源 3 选 1：行业建议 / 历史基线 / 业务规则

**用户提问示例（正例）**：

```
@<rds-instance-id> 查 CPU 使用率并判断是否需要告警；同时显式声明阈值来源（行业建议 / 历史基线 / 业务规则）
```

**反例对照**：

- 反例：`这个 CPU 算高吗` — 模型用未声明的内部默认阈值，无法追溯依据
- Agent 纠偏：返回指标值时同时给出"阈值来源 = <来源类型>: <具体阈值>"，让告警判断可追溯、可复核

**输出要求**：

- 指标值（带单位）
- 显式声明的阈值 + 来源
- 是否触发告警的结论 + 依据
- 如阈值来源不可靠（如纯模型猜测），主动建议用户补充业务规则

## 输出与交付

SOP 跑完后客户能拿到：

- **正例提问模板**：5 类陷阱对应的可直接套用的提问句式
- **反例 → 正例对照**：哪些写法会误导 Agent、应该怎么改
- **关键字段清单**：每类提问应该取哪些字段（unit / data_format / EntitySet / Relation / 阈值来源）
- **拓扑展开规范**：跨域映射 + 跳数标注 + N=0 的兜底说明

## 失败与回滚

教学型 Skill，无变更操作，无回滚需求。各样例失败处置：

| 样例 | 可能失败 | 处置 |
|---|---|---|
| 样例 1 | 指标无 `data_format` 字段 | UModel 未声明，需联系 UModel 治理方补元数据；prompt 中临时由用户提供 |
| 样例 2 | UModel 上确实只有 avg，没有 P99 | 引导走 trace duration 分布或 SLS span 分位聚合；不要伪造 P99 |
| 样例 3 | 用户坚持要集群级聚合 | 先按实体独立返回，再追加跨实例聚合结果，对比给出 |
| 样例 4 | 拓扑展开 N=0 | 告知用户该资源在 APM 层无 `apm.external.database` 实体，可能因 trace 未覆盖；建议换一个有 APM 调用方的实例 |
| 样例 5 | 用户未提供阈值来源 | Agent 主动列出 3 类来源（行业建议 / 历史基线 / 业务规则）请用户选，不要私自取默认 |

需要人工介入：UModel 元数据缺失（需治理方补字段）、APM 探针未覆盖关键依赖（需埋点团队补）、业务规则阈值未沉淀（需 SRE 与业务方共同定）。

## 召回 Routing

以下提问应路由到本 SOP Skill：

- "这个指标算不算高 / 算不算告警"
- "查 CPU / 内存 / QPS 但没说单位"
- "查 P99 延迟"（先确认是否走 UModel APM 服务层指标）
- "这个资源挂了影响哪些应用"
- "@ 一个集群 / 一组实例 查指标"
- "为什么 STAROps 回答的数值跟我看到的不一样"

以下提问不应路由：

- 告警触发后的被动 RCA → `alert-rca-flow`
- 业务可靠性主动巡检 → `business-reliability-flow`
- RDS 周期性巡检脚本编排 → `rds-inspection-via-script`
- 一般 prompt 工程范式 → `effective-prompts`
