---
name: capacity-risk-prediction-sop
description: 饱和度评估与风险预测 SOP Skill，引导 Agent 按 Phase 1 算子认知、Phase 2 Meta Skill 构建、Phase 3 长期任务运营三步复现容量风险预测实践。三阶段已由真实 STAROps thread 跑通；meta-skill-sample 中的 capacity-risk-prediction Meta Skill 已验证。
---

# 饱和度评估与风险预测 — SOP Skill

> 本仓 **SOP Skill** 入口：指导 Agent 复现 [人读版实践文档]({ARTICLE_URL}) 的三阶段流程。
>
> 重要边界：`meta-skill-sample/` 是已验证的业务 Meta Skill，负责真正执行 4 域 15 项容量巡检；本 SOP Skill 固化的三阶段流程已由三个 STAROps thread 跑通。后续发布到 skill 分发仓时，只需验证分发形态和加载入口。

## 产物关系

| 产物 | 作用 | 状态 |
|---|---|---|
| 文章 | 客户向解释三阶段和 SLS 算子 | 已补强 |
| SOP Skill | 教 Agent 复现三阶段 | 三阶段已跑通，待发布形态验证 |
| Meta Skill | 执行 4 域 15 项容量巡检 | 已验证 |

## 步骤 1：Phase 1 算子认知

目标：先确认当前 STAROps workspace 支持哪些时序算子，明确 MetricStore / Logstore / APM 的数据路径边界。

Agent 应向 STAROps 确认：

| 路径 | 要确认的能力 | 结论口径 |
|---|---|---|
| MetricStore / PromQL | `deriv`、`predict_linear`、`holt_winters`、`offset`、`avg_over_time` | acs/k8s 指标走 PromQL |
| Logstore / SLS SQL | `ts_predicate_arma`、`ts_decompose`、`ts_anomaly_filter` | log 域走 SLS SQL |
| APM / metric_set | `starops observe metric_set query` | APM 预聚合指标不走 PromQL |

必须显式说明：SLS SQL 的 `ts_*` 函数只能用于 Logstore 日志衍生时序，不能直接用于 MetricStore 云监控指标。

当前已验证不可用项：`ts_linearregress`、`ts_smooth`、`ts_cp`、`ts_outlier`、`ts_period_extract`、`ts_density`、`ts_correlate` 在 cn-hongkong 实例未注册。

交付物：算子可用性表、数据路径选择表、不可用函数清单。

## 步骤 2：Phase 2 构建并验证 Meta Skill

目标：使用 `replay-prompt.md` 构建 `capacity-risk-prediction` Meta Skill，并完成结构验证和真实执行验证。

构建要求：

- 4 域：acs、k8s、apm、log。
- 15 项：acs 6 + k8s 3 + apm 3 + log 3。
- 7 策略：趋势预测、基线偏离、缓慢增长、阈值突破、短期波动、ARIMA 预测、趋势分解与异常检测。
- 架构：数据驱动声明 + 公共引擎。
- 环境参数全部由 CLI 传入，不写死 region / project / metricstore / logstore / entity-id。

验证要求：

```bash
find . -type f | sort
python3 -m py_compile scripts/*.py
python3 scripts/infra-capacity-prediction.py --list-cases
python3 scripts/k8s-capacity-prediction.py --list-cases
python3 scripts/apm-risk-prediction.py --list-cases
python3 scripts/log-capacity-prediction.py --list-cases
```

验收：`--list-cases` 总数为 15，脚本可执行，真实数据执行能输出结构化风险报告，并能打包为 `capacity-risk-prediction.tar.gz`。

SLS 适配要求：

| 适配点 | 要求 |
|---|---|
| `ts_predicate_arma` 参数 | `p` / `q` 默认值不得小于 2 |
| 错误日志过滤 | 不依赖未建索引字段的冒号搜索；优先从 `content` 字段提取 HTTP status 或用 SQL 条件过滤 |
| `ts_decompose` 返回 | 按 SLS `logs` 数组解析 `unixtime` / `src` / `trend` / `season` / `residual` |

交付物：Meta Skill 目录、验证命令输出、真实执行报告、tar.gz。

## 步骤 3：Phase 3 长期任务运营

目标：把已验证 Meta Skill 配置为 STAROps 长期任务，并验证通知闭环。

执行参数需覆盖：

- acs 域：region / project / metricstore / time-range。
- k8s 域：region / project / metricstore / time-range。
- apm 域：workspace / entity-domain / entity-type / entity-id / time-range。
- log 域：logstore-project / logstore / log-filter / region / time-range。

长期任务建议配置：

| 项 | 建议值 |
|---|---|
| 任务名 | 容量风险预测巡检计划 |
| 执行计划 | 每个工作日 09:50（cron: `50 9 * * 1-5`） |
| 通知规则 | Warning / Critical 时邮件通知；全部 Normal 仅保存报告 |

已验证结果：任务 `mission-q98nn71adi6y604x6b` 创建成功；巡检结果为 Critical 0、Warning 3、Normal 11、Error 0、NoData 1；通知测试已发送。

交付物：长期任务 ID、子计划 ID、下次执行时间、通知配置、一次完整巡检报告。

## 失败与回滚

本 SOP 指导的是只读查询、Skill 生成和长期任务配置。业务资源不被修改。

| 失败点 | 表现 | 处理 |
|---|---|---|
| 算子不可用 | STAROps 返回函数未注册 | 从策略中移除，不写成可执行路径 |
| MetricStore / Logstore 混用 | `ts_*` 无法作用于云监控指标 | 回到路径选择表，MetricStore 走 PromQL |
| Meta Skill 结构不符 | 文件数、frontmatter、脚本编译失败 | 修 replay prompt 后重新生成 |
| Log 域脚本报错 | 参数、过滤条件或返回格式不匹配 | 按 SLS 适配要求修复 |
| 长期任务提交失败 | mission yaml 校验失败或 description 超长 | 缩短描述并重跑 VerifyMission |

## 召回 Routing

应路由到本 SOP：

- “做容量评估 / 容量预测”
- “这个指标还能撑多久”
- “预测一下磁盘什么时候满”
- “请求量有没有异常突增”
- “业务负载有没有周期性规律”
- “把容量预测做成长期任务”

不应路由到本 SOP：

- 已触发告警的 RCA → `alert-rca-flow`
- RDS 周期性巡检（看当前值而非预测）→ `rds-inspection-via-script`
- 指标语义确认（单位/聚合口径）→ `umodel-metric-entity`
- 业务可靠性守护（订单/支付级别）→ `business-reliability-flow`
