---
name: capacity-risk-prediction-sop
description: 容量风险预测与服务饱和度评估 SOP Skill，引导 Agent 按"选对象→查趋势→算预测→比基线→给结论"5 步完成跨域容量风险评估，覆盖 ECS/RDS/Redis/K8s/APM 三个域 4 种评估策略
---

# 容量风险预测与服务饱和度评估 — SOP Skill

> 本仓 **SOP Skill** 入口：把 [人读版实践文档](https://sls.aliyun.com/doc/starops/practices/capacity-risk-prediction/article.html) 的 5 步流程固化为 Agent 可加载形态。
>
> 区分：本实践的 meta skill（定时容量预测巡检）在 `meta-skill-sample/`，是客户直接消费的业务 Skill。本 SOP Skill 是教流程用的。

## SOP 概览

5 个步骤覆盖容量风险预测的完整流程：

1. 选择评估对象与指标 — 按域选实体 + 确认指标语义
2. 查看当前状态与趋势 — 当前值 + deriv 变化率 + 趋势图
3. 容量预测 — predict_linear 预测 + 剩余天数计算
4. 基线偏离检测 — 日环比 + 7 天基线对比
5. 结论与建议 — 汇总报告 + 风险等级 + 建议行动

## 步骤 1：选择评估对象与指标

**Agent 指令**：

1. 确认用户要评估哪个域：acs（ECS/RDS/Redis）/ k8s（Node/Pod）/ apm（业务服务）
2. @ 具体实体，获取 entity_id
3. 确认指标的 `data_format` 和 `type`（引用 umodel-metric-entity 规范）
4. 确认阈值来源（行业建议 / 历史基线 / 业务规则）

**用户提问示例**：

```
@i-j6c6y2n68f610xaa9a29 对这台 ECS 做容量风险评估，关注 CPU 使用率，Warning 阈值 85%
```

**输出要求**：

- 确认实体（EntitySet + entity_id + instanceId）
- 确认指标（名称 + data_format + type + unit）
- 确认阈值（Warning / Critical + 来源）

## 步骤 2：查看当前状态与趋势

**Agent 指令**：

1. 查询当前值（最近 1h 的 mean / max / min）
2. 计算变化率：`deriv(metric[6h])` × 3600 = 每小时增量
3. 判断趋势方向：正值 = 上升，负值 = 下降，接近零 = 平稳
4. acs / k8s 域用 PromQL，apm 域用 `starops observe entity metric-data` + 脚本计算

**PromQL 模板**：

```promql
# 当前值
avg_over_time({metric}{instanceId="{id}"}[1h])

# 变化率（每秒增量）
deriv({metric}{instanceId="{id}"}[6h])
```

**输出要求**：

- 当前值（带单位）
- 变化率（每小时 / 每天）
- 趋势方向（上升 / 下降 / 平稳）

## 步骤 3：容量预测

**Agent 指令**：

1. 用 `predict_linear(metric[6h], N)` 预测 N 秒后的值
2. 预测 1 天后（86400s）和 7 天后（604800s）
3. 计算"剩余天数"：`(threshold - current) / (deriv * 3600 * 24)`
4. 如果 deriv <= 0（平稳或下降），剩余天数 = 无穷（不会触及阈值）
5. APM 域不支持 predict_linear，用脚本内线性回归替代

**PromQL 模板**：

```promql
# 预测 7 天后的值
predict_linear({metric}{instanceId="{id}"}[6h], 604800)
```

**输出要求**：

- 1 天后预测值
- 7 天后预测值
- 预计触及 Warning 的剩余天数（或"不会触及"）
- 预计触及 Critical 的剩余天数

## 步骤 4：基线偏离检测

**Agent 指令**：

1. 日环比：`metric / metric offset 1d` — 看今天与昨天同时段的比值
2. 7 天基线：`avg_over_time(metric[7d])` — 过去 7 天的均值作为基线
3. 偏离幅度：`(当前值 - 基线) / 基线 × 100%`
4. 偏离超过 50% 标注异常（K8s Node 示例：日环比 +51pp 就是典型的基线偏离告警）

**PromQL 模板**：

```promql
# 日环比
{metric}{instanceId="{id}"} / {metric}{instanceId="{id}"} offset 1d

# 7 天基线
avg_over_time({metric}{instanceId="{id}"}[7d])
```

**输出要求**：

- 日环比（倍数或百分点差异）
- 基线偏离（当前值 vs 7 天均值的差异）
- 是否异常（偏离 > 50%）

## 步骤 5：结论与建议

**Agent 指令**：

1. 汇总上述 4 步的结果到一张表
2. 按风险等级分类：
   - **Critical**：当前值已超 Critical 阈值，或剩余天数 < 1 天
   - **Warning**：当前值超 Warning 阈值，或剩余天数 < 7 天，或基线偏离 > 50%
   - **Normal**：其余
3. 给出建议行动（扩容 / 优化 / 清理 / 观察）
4. 如果是定时巡检，对比上次报告的变化

**输出要求（汇总表）**：

```
| 指标 | 当前值 | 变化率 | 7天预测 | 日环比 | 基线偏离 | 阈值 | 剩余天数 | 风险 | 建议 |
```

## 失败与回滚

SOP Skill，只读操作，无回滚需求。

| 步骤 | 可能失败 | 处置 |
|---|---|---|
| 步骤 1 | 实体不在 UModel 中 | 提示用户确认实体是否已接入 |
| 步骤 2 | deriv 返回空（数据不足） | 告知"数据不足 6h，无法计算变化率"，用 1h 窗口降级 |
| 步骤 3 | predict_linear 返回空（APM 域） | 切换到脚本内线性回归；如果也无数据，标注"无法预测" |
| 步骤 4 | offset 1d 返回空（实体昨天不存在） | 标注"无历史数据可比"，跳过环比 |
| 步骤 5 | 全部巡检项都是 Normal | 正常结论，不是失败 |

## 召回 Routing

**应路由到本 SOP**：

- "做容量评估 / 容量预测"
- "这个指标还能撑多久"
- "预测一下磁盘什么时候满"
- "CPU 趋势怎么样"
- "和昨天比有变化吗"
- "风险评估 / 饱和度评估"

**不应路由到本 SOP**：

- 已触发告警的 RCA → `alert-rca-flow`
- RDS 周期性巡检（看当前值而非预测）→ `rds-inspection-via-script`
- 指标语义确认（单位/聚合口径）→ `umodel-metric-entity`
- 业务可靠性守护（订单/支付级别）→ `business-reliability-flow`
