---
name: log-insight-pattern-sop
description: 日志洞察 SOP。引导用户在 STAROps 控制台「长期任务 → 新建长期任务」模态弹窗内 1 击「日志模式洞察」场景卡建任务，由 AI 在 chat 内编排 5 步（场景卡 1 击 → chat 自然语言收集参数 → VerifyMission → ApplyMission → 等 cron 触发）让巡检报告按 cron 自动产出送达；附录保留 5 步会话路径覆盖单次深度排查。
---

# 通过 STAROps 配置日志模式定时巡检 — SOP Skill

> 本仓 **SOP Skill** 入口：把 [人读版实践文档](https://sls.aliyun.com/doc/starops/practices/log-insight-pattern/article.html) 的 SOP 固化为 Agent 可加载形态。
>
> 区分：本实践无 meta skill 样品（主路径完整复用平台内置 Blueprint `log-pattern-inspection`，本仓不重复造副本）。

## 何时触发本 SOP

以下提问应路由到本 SOP Skill 的**主路径**：
- "帮我配一个日志模式定时巡检"
- "让 STAROps 自动给我看日志模式有没有变化"
- "想要每天自动收到日志聚类报告"
- "Logstore 日志想做周期性巡检"
- "新增模式 / 异常模式自动告知 oncall"
- "多个 Logstore 一起做模式巡检"

以下提问应路由到本 SOP 的**附录路径**（§ 附录）：
- "我现在就想看看这个 Logstore 有什么模式"（一次性深度排查）
- "应急排查 / 单次根因分析"
- "想自定义提问角度 / 临时改 prompt"

以下提问不应路由到本 SOP：
- 告警触发后的被动排查 → `alert-rca-flow-sop`
- 日志采集配置 → 日志接入专项
- 日志存储成本优化 → 日志治理专项
- **垂直产品级巡检**（RDS / Redis / Kafka 等专项巡检）→ 路由到 `rds-inspection-via-script-sop`（自定义 Skill 包装路线，本实践场景卡路线只覆盖平台预设 5 类标准场景）

## 主路径 SOP 概览

5 步配置流程，章节顺序与 [人读版实践文档 步骤一～步骤五](https://sls.aliyun.com/doc/starops/practices/log-insight-pattern/article.html) 一一对应：

1. 控制台「长期任务 → 新建长期任务」 → 1 击「日志模式洞察」场景卡
2. chat 内 AI 自然语言收集配置（Logstore / 聚类字段 / 过滤 / 窗口 / 对比 / cron / 通知）
3. AI 写 staging/mission.{yaml,md} + VerifyMission 校验 + 输出「本次调整」摘要
4. 用户确认 yes → ApplyMission（staging→plan 提升）→ 任务进入 active
5. 等 cron 触发 → 报告写 `artifacts/` + 通知通道送达

## 步骤 1：控制台「长期任务 → 新建长期任务」 → 1 击「日志模式洞察」场景卡

**Agent 动作**：引导用户进入 STAROps 控制台左侧导航「长期任务」→ 右上角「新建长期任务」按钮 → 模态弹窗内选择「日志模式洞察」场景卡 1 击建任务。

**Agent 引导话术**：

> "请打开 STAROps 控制台，左侧导航点击「长期任务」，右上角「新建长期任务」按钮会弹出模态弹窗，里面有 5 张固定场景卡（容器智能巡检 / 日志模式洞察 / 告警智能洞察 / RUM 智能巡检 / 主机智能巡检）。请 1 击「日志模式洞察」卡片。平台会自动创建新的 chat thread 并注入预设 prompt，由我接管对话陪您完成剩下 4 步配置。"

**输出要求**：
- 顶部任务名出现「日志模式定时巡检」
- AI 主动询问要巡检的 Logstore

**L0 声明**：本步骤只读，不发起任何变更。

## 步骤 2：chat 内 AI 自然语言收集配置

**Agent 动作**：在 chat 内依次询问 6 个参数，用户用自然语言回答，不需要写 YAML 或参数表。如果用户答的 Logstore 数据为空或聚类字段不存在，主动调 `starops sls query` 探查并给出候选 Logstore 数据量与字段对比。

**询问清单**（按顺序）：

| 询问项 | 用户回答示例 | 不指定时默认值 |
|---|---|---|
| 要巡检的日志库 | `<project> / <logstore>` 格式 | 无默认，必填 |
| 聚类字段 | `content` / `message` / `msg` / `__line__` | `message` |
| 聚合字段（可选）| `level` / `service` | 无 |
| 过滤语句（可选）| `(ERROR or WARN) not chaos-daemon` | 无 |
| 分析窗口 | `最近 1 小时` / `最近 24 小时` | 最近 1 小时 |
| 对比策略（可选）| `-1h` / `-1d` / `-7d`；冷启动场景临时用 `-3min` | `-1h` |
| 通知对象 | 数字员工通知目标名 | 无默认 |
| cron 表达式 | `每 1 小时执行一次` / `每天 09:00` | `0 * * * *` |

**门控规则**（Agent 必须强制执行）：
- 数据量预检（Blueprint 内嵌）：单窗口 ≤ 5 万条 → 通过；> 5 万条 → 引导追加 `filter` 业务关键词，或显式 `samplingAcknowledged: true` 接受采样（报告标注 `sampled=true` + 降级可信度）
- 字段连通性检查：聚类字段必须存在；v2 行索引 Logstore 需在 SLS 控制台开启字段索引

**Agent 引导话术**：

> "请告诉我要巡检的日志库（按 `<project> / <logstore>` 格式）。我会自动探查数据量与字段，必要时给您建议过滤条件。其他参数（聚类字段 / 过滤 / 窗口 / 对比 / cron / 通知对象）您可以逐项告诉我，也可以一次性给出，没指定的我会用默认值。"

**输出要求**：
- 6 个必填参数（Logstore + cron + 通知对象至少）明确
- 数据量预检结论清晰（条数 + 决策）

**L0 声明**：本步骤只读，不发起任何变更。

## 步骤 3：AI 写 staging + VerifyMission 校验

**Agent 动作**：参数收齐后按以下顺序自动执行——

1. ListDir 平台 Blueprint 模板路径：`/home/starops/skills/builtin/starops/mission/blueprint-guide/references/templates/log-pattern-inspection/`
2. Read 模板内 `mission.yaml` + `mission.md`
3. DescribeNotificationTargets 校验通知对象有效性
4. Bash 创建任务工作目录下的 `staging/` 子目录
5. Write `staging/mission.yaml`（配置项）+ `staging/mission.md`（说明文件）
6. VerifyMission 校验（语法 + 数据连通性 + 时间窗口）
7. 输出「本次调整」摘要：任务名称 / 执行计划 cron / 通知对象 / 调整说明 / 当前计划概览 / 子计划清单 / 「是否需要我立即提交此计划配置？」

**关键参数表**：

| 字段 | 推荐取值 | 注意事项 |
|---|---|---|
| `cronExpression` | `0 9 * * *`（每日 09:00）/ `0 */1 * * *`（每小时整点） | 5 段式，间隔 ≥ 5 min |
| `timeZone` | `Asia/Shanghai`（默认） | 不要按 UTC 思路配 |
| `--compare-offset` | 生产推荐 `-1h` / `-1d`；冷启动 / 新接入 logstore 无 1 小时历史时临时用 `-3min` 验证连通性 | `-3min` 仅适用冷启动；数据积累到 1 小时以上必须切回 `-1h` / `-1d` |
| `analysisMode` | 单库固定 `independent`；多库强相关填 `correlated`，无关联填 `independent` | `correlated` 仅在 2-5 库真实强相关时使用 |
| `--max-patterns` | 默认 100；噪声大时调小为 50 | 可选 |

**Agent 引导话术**（VerifyMission 通过后）：

> "我已写入 staging 草稿并通过 VerifyMission 校验。本次调整：任务名称 `<task-name>` / cron `<cron>` / 通知对象 `<target>` / 巡检目标 `<project>/<logstore>` / 产物路径 `artifacts/YYYY-MM/MM-DD/inspection-report-YYYY-MM-DD-hh-mm.md`。是否需要我立即提交此计划配置？回复 yes 即可激活。"

**Agent 引导话术**（VerifyMission 失败时）：

> "校验失败：`<具体哪一项>`（如 cronExpression 非 5 段式 / 通知对象不存在 / 数据连通性失败）。您可以追加自然语言修改指令（例如『把 logstore 换成 demo-logs，聚类字段换成 content』），我会重新走 Read → Edit → VerifyMission 流程。"

**输出要求**：
- VerifyMission 一次通过（或显式说明失败项 + 修改路径）
- 「本次调整」摘要清晰

**L0 声明**：本步骤只读，不发起任何变更。

## 步骤 4：用户 yes → ApplyMission → 任务激活

**Agent 动作**：用户输入 `yes`（或「确认」「应用」等等价表达）后按顺序执行——

1. 「更新长期任务」工具调用（提交配置）
2. 「应用计划」工具调用（staging→plan 提升）
3. 输出「当前计划状态」摘要：计划名称 / 执行频率 / 通知对象 / 巡检目标
4. 提示「系统当前读取的计划视图及说明文件也已同步」

**Agent 引导话术**：

> "已应用计划，任务进入活跃状态。当前计划：`<计划名称>` / 执行频率 `<cron>` / 通知对象 `<target>` / 巡检目标 `<project>/<logstore>`。下次 cron 触发时刻：`<next-trigger>`。如果您希望立即验证一次，可以追加『现在立刻执行并且测试一次』，我会即时触发一轮测试运行，测试触发不影响 cron 时刻表。"

**输出要求**：
- 控制台右上角任务状态 badge = 活跃
- 下次 cron 触发时刻已计算并展示

**L0 声明**：本步骤只读，不发起任何变更（Mission 启用 / 暂停 / 删除全部走 STAROps 控制台标准入口）。

## 步骤 5：等 cron 触发 → 报告 + 通知

**Agent 动作**：等待首次 cron 触发时刻；触发后引导用户在两处确认结果——控制台「报告」tab + 绑定的通知通道。

**期望产物**：

| 产物 | 路径 |
|---|---|
| 主报告 | `/home/starops/missions/mission-<taskId>/artifacts/YYYY-MM/MM-DD/inspection-report-YYYY-MM-DD-hh-mm.md` |
| 各库洞察 | `artifacts/patterns/{project}/{logstore}/important-information.md` |
| 多库汇总（仅 `correlated`）| `artifacts/patterns/cross-logstore-summary.md` |
| 原始 JSON | `run_scope/{project}/{logstore}/log-pattern-{YYYY-MM-DD-HH-mm}.json` |
| 通知 | 通道收到摘要 + 报告链接（邮件主题：「日志模式定时巡检 - 对比分析完成」）|

**控制台「报告」tab**：左侧按月/日/patterns 分类目录树（如 `2026-06 / 06-03 / inspection-report-2026-06-03-11-24.md` + `patterns/<project>/<logstore>/important-information.md`），右侧渲染报告内容。

**Agent 引导话术**：

> "首次 cron 触发后，请确认两点：（1）主报告是否落到 `artifacts/YYYY-MM/MM-DD/` 路径且控制台「报告」tab 可见；（2）通知通道是否收到摘要消息 + 报告链接。两者都到 → 配置完成。仅其一到达 → 我陪您排查通知通道配置或执行日志。"

**输出要求**（首次 cron 触发后）：
- 报告文件名时间 = cron 触发时刻 = 当前窗口结束时刻（三者一致）
- 通知通道收到摘要消息，含报告链接可直接跳转

**L0 声明**：本步骤只读，不发起任何变更。

## 输出与交付

主路径 SOP 跑完后客户能拿到：

- **持续运转的长期任务**：按 `cronExpression` 周期自动触发
- **巡检报告**：模式聚类表 + 变更（新增/消失/显著变化）+ 单库风险评估 + 跨库汇总（多库 `correlated`）
- **通知送达**：摘要 + 报告链接主动到达指定通道
- **历史归档**：每次触发的报告与原始 JSON 均落盘可追溯

## 失败与回滚

L0 只读，无回滚需求。常见失败处置：

| 步骤 | 可能失败 | 处置 |
|---|---|---|
| 步骤 1 | 模态弹窗加载不出场景卡 | 检查 STAROps 实例是否开通对应权限；联系平台团队 |
| 步骤 2 | 数据量超过 5 万条且业务关键词不清晰 | 引导接受采样风险（`samplingAcknowledged: true`），并提示报告会标注降级可信度 |
| 步骤 2 | 聚类字段不存在（v2 行索引）| 引导用户回 SLS 控制台为 `content` / `message` / `__line__` 字段开启字段索引 |
| 步骤 3 | `cronExpression` 校验失败 | 检查是否为 5 段式且间隔 ≥ 5 min |
| 步骤 3 | `--compare-offset` 在测试触发时报「no log data」 | Blueprint 已内嵌降级为双查询对比；如双查询也失败，检查 Logstore 数据保留期；冷启动场景临时用 `-3min` 验证连通性 |
| 步骤 3 | `correlated` 输出为空 | 改回 `independent`，或确认 Logstore 业务相关性 |
| 步骤 4 | ApplyMission 提示通知对象未绑定 | 回步骤 2 重新确认 DescribeNotificationTargets 结果 |
| 步骤 5 | 通知通道未送达 | 检查目标地址（webhook URL / 邮箱），核对企业出口 IP 白名单 |
| 任意 | 任务触发后没有报告 | 按以下顺序排查：active 状态 → 预检通过 → cron 有效 → 通知绑定 → 控制台执行记录查 `missionTaskId` / `run_id` 错误日志 |

## 附录：手动深度排查（5 步会话路径）

> **优先路径**：日常咨询直接在 STAROps 控制台 @AI 提问——chat 内的 AI 持有当前任务上下文（已配置的 logstore / cron / 过滤条件），给出的答案比离线照搬本附录更精准。本附录适用于 Agent 不可用的离线场景，或想理解 5 步会话路径机制的兜底参考。
>
> 适用：单次深度排查 / 应急根因分析 / 用户不希望走 cron 周期任务的场景。

### 附录步骤 1：日志模式聚类

```
@LogStore-<LogStore 名> 对最近 <时间范围> 的日志做模式聚类，列出 Top <N> 高频模式，每个模式给出出现次数、占比、代表关键词
```

注意：prompt 必须显式指定 project 名称；占比 >80% 的模式通常是噪声候选。

### 附录步骤 2：新增模式检测

```
@LogStore-<LogStore 名> 对比基线，检测最近 <时间范围> 内新增的日志模式（之前 <基线天数> 未出现过的模式），列出新增模式及其出现次数、代表关键词
```

注意：`--compare-offset` 失败时 AI 自主降级为双查询对比。

### 附录步骤 3：错误趋势分析

```
@LogStore-<LogStore 名> 对最近 <时间范围> 的错误类日志（ERROR / WARN / Exception）做趋势分析，按小时粒度统计错误数量变化趋势，判断是否在恶化
```

注意："判断是否在恶化"是关键触发词，驱动 AI 做定量对比而非仅罗列数据。

### 附录步骤 4：代表样本采集

```
@LogStore-<LogStore 名> 对最近 <时间范围> 的关键日志模式，每个模式取 1-2 条代表性原始日志样本，包含完整字段（时间戳、级别、服务名、消息体、traceID 等）
```

注意：traceID 并非所有日志都有，作为期望字段而非强制字段。

### 附录步骤 5：影响判断

```
@LogStore-<LogStore 名> 综合最近 24 小时的日志模式聚类结果、新增模式检测、错误趋势分析和代表样本，判断当前日志整体健康状况，给出影响范围评估和严重程度判断（P0-P3），以及需要关注的风险点
```

注意：必须在同一 thread 内执行 5 个步骤，AI 才能自动回顾 Phase 1-4 结果。

### 附录路径的判别

| 场景 | 选主路径（场景卡 1 击）| 选附录（5 步会话）|
|---|---|---|
| 日常巡检（每日 / 每小时）| ✅ | ❌ |
| 突发个案排查 | ❌ | ✅ |
| oncall 想被动收报告 | ✅ | ❌ |
| 想自定义提问角度 / 临时改 prompt | ❌ | ✅ |
| 多 Logstore 批量巡检 | ✅（最多 5 个）| ❌（5 phase 为单库设计）|
