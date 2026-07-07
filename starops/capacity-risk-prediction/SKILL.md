---
name: capacity-risk-prediction
description: >
  通用容量风险预测执行引擎。接收 Mission Profile（预测对象列表、数据源坐标、阈值、候选维度、调度与通知规则），
  通过 series_forecast / series_describe 对任意数据源（MetricStore / Prometheus / CloudMonitor / SLS LogStore）
  构造等间隔时间序列并预测未来趋势，输出结构化风险报告。
  当 Mission 需要执行容量风险预测、服务饱和度评估、趋势外推、阈值突破预测时触发。
  不用于数据源发现（Phase 0 discovery）、UModel 建模、告警规则 CRUD、或单次指标查询。
metadata:
  name_cn: 容量风险预测执行引擎
  name_en: Capacity Risk Prediction Runtime
  description_cn: >
    通用容量风险预测执行引擎。接收 Mission Profile 注入的预测对象、数据源、阈值和维度，
    执行 9 步预测流水线，输出风险报告。所有对象坐标均为参数注入，skill 内部不写死任何具体服务或资源。
  description_en: >
    Generic capacity risk prediction runtime engine. Accepts Mission Profile with forecast targets,
    data source coordinates, thresholds, and dimensions. Executes 9-step prediction pipeline
    using series_forecast / series_describe. No hardcoded objects.
---

# 目标与完成标准

## 目标

作为 capacity-risk-prediction Mission 的运行时执行引擎，接收 Mission Profile 参数注入，对任意预测对象执行时间序列预测与风险评估，输出结构化风险报告。

## 完成标准

- 所有 Profile 中的 forecast_targets 均完成 series_forecast + series_describe
- 每个 target 产出：预测值序列、上下界、segments、transitions、数据质量
- 阈值评估完成，每个 target 有 risk_level（Normal / Warning / Critical）
- 共振检测完成（多信号同向恶化时标记 resonance）
- 风险报告 JSON + 可读 Markdown 已生成
- 通知规则已执行（Normal 静默，Warning/Critical 或共振事件通知）

# 输入契约

## Mission Profile（JSON）

所有预测对象、数据源坐标、阈值、维度均通过 Mission Profile 注入。Skill 内部不写死任何具体服务、资源 ID 或存储坐标。

```json
{
  "profile_id": "string",
  "profile_version": "1.0",
  "workspace": "string",
  "region": "string",
  "time_range": "last_24h | last_7d | now-Nd~now",
  "forecast_step": 30,
  "forecast_targets": [
    {
      "target_id": "unique_id",
      "object_ref": {
        "name": "display_name",
        "domain": "apm | k8s | acs | sls",
        "type": "apm.service | k8s.pod | acs.rds.instance | ...",
        "id": "entity_id_or_resource_id"
      },
      "data_source": {
        "type": "metricstore_prom_call | prometheus_query | cloudmonitor_entity | sls_logstore",
        "region": "cn-hangzhou",
        "project": "sls_project",
        "store": "metricstore_or_logstore_name",
        "prometheus_instance_id": "for prometheus_query type",
        "query_template": "PromQL or SPL template with {{variable}} placeholders",
        "metric_name": "for cloudmonitor type",
        "metric_set_domain": "for cloudmonitor type",
        "metric_set_name": "for cloudmonitor type"
      },
      "signals": [
        {
          "signal_id": "request_count",
          "query_template": "PromQL with {{service_name}} etc.",
          "data_format": "KMB | percent | s | reqps | ...",
          "direction": "higher_is_worse | lower_is_worse",
          "thresholds": {
            "warning": 100,
            "critical": 200
          }
        }
      ],
      "candidate_dimensions": ["service", "namespace", "pod"],
      "context": {
        "service_name": "checkout",
        "namespace": "cms-demo"
      }
    }
  ],
  "resonance": {
    "enabled": true,
    "group_by": ["chain", "namespace", "resource"],
    "min_signals": 2
  },
  "notification": {
    "normal": "silent",
    "warning": "notify",
    "critical": "notify",
    "resonance": "notify"
  }
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|:----:|------|
| `workspace` | Y | UModel workspace ID |
| `region` | Y | 阿里云 region |
| `time_range` | Y | 取数时间范围，需保证 >=200 数据点 |
| `forecast_step` | N | 预测步数，默认 30 |
| `forecast_targets[]` | Y | 预测对象列表 |
| `forecast_targets[].target_id` | Y | 唯一标识 |
| `forecast_targets[].object_ref` | Y | 对象引用（name/domain/type/id） |
| `forecast_targets[].data_source` | Y | 数据源坐标与查询模板 |
| `forecast_targets[].signals[]` | Y | 信号列表（每个信号一个 PromQL/SPL + 阈值） |
| `forecast_targets[].context` | N | 查询模板变量替换上下文 |
| `resonance` | N | 共振检测配置 |
| `notification` | N | 通知规则 |

### 数据源类型

| type | 适用场景 | 取数路径 |
|------|----------|----------|
| `metricstore_prom_call` | APM MetricStore 原始指标 | `log_store query --logstore <metricstore>` + SPL 管道 `.metricstore \| prom-call promql_query_range('<PromQL>')` |
| `prometheus_query` | K8s Prometheus 指标 | `metric_store query --prometheus-instance-id <id>` 或同上 SPL 管道 |
| `cloudmonitor_entity` | CloudMonitor 云产品指标（RDS/Redis/ECS） | `metric_store query --entity-domain acs --entity-type <type> --entity-id <id>` |
| `sls_logstore` | SLS LogStore 日志衍生时序 | `log_store query` + SLS SQL/SPL |

# 执行流程

## Step 1: 加载与校验 Profile

读取 Mission Profile JSON，校验必填字段完整性。

- 校验 `workspace`、`region`、`time_range` 非空
- 校验每个 `forecast_target` 有 `target_id`、`object_ref`、`data_source`、至少一个 `signal`
- 校验 `data_source.type` 是已知类型之一
- 将 `context` 中的键值对替换到 `query_template` 的 `{{variable}}` 占位符

**成功标准**：Profile 解析通过，所有 target 的 query_template 已完成变量替换。
**产出物**：resolved_targets 列表（供 Step 2 消费）。

## Step 2: 取数

按 `data_source.type` 路由到对应的取数模板（详见 `references/data-source-templates.md`）。

对每个 resolved_target 的每个 signal，执行 CLI 命令获取时间序列数据。

### 取数路由

| data_source.type | CLI 命令模式 |
|---|---|
| `metricstore_prom_call` | `starops observe log_store query --region <r> --project <p> --logstore <store> --query "<SPL>" --time-range '<tr>'` |
| `prometheus_query` | `starops observe metric_store query --prometheus-instance-id <id> --region <r> --query "<PromQL>" --time-range '<tr>'` |
| `cloudmonitor_entity` | `starops observe metric_store query -w <ws> --entity-domain acs --entity-type <type> --entity-id <id> --metric-set-domain <msd> --metric-set-name <msn> --query "<metric>" --time-range '<tr>' --raw` |
| `sls_logstore` | `starops observe log_store query --region <r> --project <p> --logstore <store> --query "<SLS_SQL>" --time-range '<tr>'` |

**成功标准**：每个 signal 返回非空时间序列数据。
**失败处理**：单个 signal 取数失败标记 `status=error`，不阻断其他 target。

## Step 3: 序列构造

确保取到的数据是等间隔时间序列，且数据点数 >= 200（series_forecast 最低要求）。

- 检查时间粒度：`time_granularity` 从 series_describe 返回或从数据间隔推算
- 如果数据点 < 200：
  - 尝试扩大 time_range（如 last_24h → last_7d）
  - 如果仍不足，标记 `status=error, error="insufficient_data_points"`
- 如果数据有缺失点（missing_point_count > 0），记录但不阻断

**成功标准**：每个 signal 有 >= 200 个等间隔数据点。
**产出物**：validated_series 列表。

## Step 4: 统计描述（series_describe）

对每个 signal 的时间序列执行 `series_describe`，获取统计特征。

### SPL 管道

```
.metricstore | prom-call promql_query_range('<resolved_promql>') | extend desc = series_describe(__value__)
```

### 解析 desc 返回值

`desc` 是 2 元素数组，`desc[0]` 为 JSON 字符串，解析后包含：

| 字段 | 含义 |
|------|------|
| `max / min / mean / sum / std` | 基础统计量 |
| `p5 / p25 / p50 / p75 / p95` | 分位数 |
| `actual_point_count` | 实际数据点数 |
| `missing_point_count` | 缺失点数 |
| `time_granularity` | 时间粒度（纳秒） |
| `segments[]` | 分段形状检测（STABLE_PLATEAU / STEP_UP / SPIKE_RECOVERY / CURVED_PEAK 等） |
| `transitions[]` | 转换点检测（含置信度） |

**成功标准**：desc 解析成功，segments 和 transitions 非空。
**产出物**：describe_results（供 Step 8 报告消费）。

## Step 5: 预测（series_forecast）

对每个 signal 的时间序列执行 `series_forecast`，获取未来 N 步预测值 + 上下界。

### SPL 管道

```
.metricstore | prom-call promql_query_range('<resolved_promql>') | extend ret = series_forecast(__value__, <forecast_step>)
```

### 解析 ret 返回值

`ret` 是 8 元素数组：

| 索引 | 含义 |
|:----:|------|
| ret[0] | 完整时间戳序列（历史 + 预测），纳秒 |
| ret[1] | 完整值序列（历史值 + null 填充预测位） |
| ret[2] | **预测值数组**（历史段为拟合值，后 N 步为外推预测） |
| ret[3] | **上界数组** |
| ret[4] | **下界数组** |
| ret[5] | 输入数据点数 |
| ret[6] | 预测步数 |
| ret[7] | 保留（null） |

### 提取关键值

- `predicted_values`：ret[2] 后 forecast_step 个非 null 值
- `upper_bound`：ret[3] 后 forecast_step 个值
- `lower_bound`：ret[4] 后 forecast_step 个值
- `predicted_max`：predicted_values 的最大值
- `predicted_min`：predicted_values 的最小值
- `predicted_trend`：predicted_values 的线性斜率

**成功标准**：ret 解析成功，predicted_values 非空。
**产出物**：forecast_results（供 Step 6 阈值评估消费）。

## Step 6: 阈值计算与风险评估

对每个 signal，基于预测值与阈值比较，评估风险等级。

### 评估逻辑

```
对于 direction=higher_is_worse 的信号：
  if predicted_max >= critical_threshold → risk_level = Critical
  elif predicted_max >= warning_threshold → risk_level = Warning
  else → risk_level = Normal

对于 direction=lower_is_worse 的信号：
  if predicted_min <= critical_threshold → risk_level = Critical
  elif predicted_min <= warning_threshold → risk_level = Warning
  else → risk_level = Normal
```

### 多信号归并

同一 target 有多个 signal 时，取最高风险等级：
- 任一 Critical → target risk = Critical
- 任一 Warning → target risk = Warning
- 全部 Normal → target risk = Normal

### 触阈时间估算

从 predicted_values 中找到首次超过阈值的索引 i，触阈时间 = 当前时间 + i * time_granularity。

**成功标准**：每个 target 有 risk_level 和触阈时间（或"未触阈"）。
**产出物**：risk_assessments。

## Step 7: 风险归并与共振检测

跨 target 跨 signal 归并风险，检测共振事件。

### 共振检测逻辑

当 `resonance.enabled=true` 时：

1. 按 `resonance.group_by` 分组（如 chain=checkout 链路下的所有服务）
2. 在每个分组内，检查是否有 >= `resonance.min_signals` 个信号同时满足：
   - risk_level >= Warning
   - direction 同向（同时恶化）
   - 触阈时间在同一个时间窗口内（如 24h 内）
3. 满足条件 → 标记为 resonance 事件，risk_level 提升一级

### 共振类型

| 类型 | 含义 |
|------|------|
| `multi_signal_resonance` | 同一对象的多个信号同时恶化（如 checkout 的 latency + error_rate + CPU 同时上升） |
| `multi_object_resonance` | 同一 chain/namespace 下多个对象同时恶化（如 checkout + inventory + payment 同时 latency 上升） |
| `cascading_resonance` | 上游对象的预测恶化与下游对象的预测恶化存在因果关系链 |

**成功标准**：共振检测结果已生成（或确认无共振）。
**产出物**：resonance_events。

## Step 8: Investigation Handoff（可选）

当存在 Critical 风险或共振事件时，将预测结果交给 InvestigationAgent 做深度根因分析。

### Handoff 内容

```
预测结果摘要：
- <target_id>: <signal_id> 预测值 <predicted_max> 将在 <触阈时间> 超过 <threshold>
  - 当前值: <current_value>, 预测趋势: <predicted_trend>
  - segments: <segment_shape_summary>
  - 置信度: 基于上下界宽度

实体关系：
- <object_ref> 的上下游关系（来自 Profile 或 UModel）

时间窗口：
- <time_range>

阈值来源：
- <threshold_source_description>

候选维度：
- <candidate_dimensions>
```

**成功标准**：InvestigationAgent 返回根因分析（或标记为跳过）。

## Step 9: 报告输出与通知

### 风险报告 JSON 结构

```json
{
  "profile_id": "string",
  "execution_time": "ISO8601",
  "time_range": "last_24h",
  "summary": {
    "total_targets": 8,
    "critical": 1,
    "warning": 2,
    "normal": 5,
    "errors": 0,
    "resonance_events": 1
  },
  "risk_items": [
    {
      "target_id": "checkout_request_count",
      "object_name": "checkout",
      "object_ref": {"domain": "apm", "type": "apm.service", "id": "..."},
      "signal_id": "request_count",
      "risk_level": "warning",
      "current_value": 107.67,
      "predicted_max": 125.3,
      "predicted_values": [102.48, 103.06, ...],
      "upper_bound": [119.83, 120.28, ...],
      "lower_bound": [87.17, 87.62, ...],
      "warning_threshold": 120,
      "critical_threshold": 150,
      "threshold_breach_time": "2026-07-02T06:00:00+08:00",
      "confidence": "medium",
      "segments": [{"shape": "STABLE_PLATEAU", "confidence": 0.94}, ...],
      "transitions": [{"type": "TREND_REVERSAL_TRANSITION", "confidence": 0.999}],
      "data_quality": {"actual_points": 289, "missing_points": 0},
      "evidence": "series_forecast 预测 30 步后最大值 125.3 超过 warning 阈值 120",
      "counter_evidence": "上下界宽度 32.66，置信度中等",
      "gaps": "P99/P95 不可用，仅使用 avg + error_rate 多信号收敛"
    }
  ],
  "resonance_events": [
    {
      "type": "multi_signal_resonance",
      "group": "checkout_chain",
      "targets": ["checkout_latency", "checkout_error_rate", "checkout_cpu"],
      "description": "checkout 服务 latency + error_rate + CPU 三信号同时恶化",
      "severity": "critical"
    }
  ]
}
```

### 通知规则

按 Profile 中 `notification` 配置执行：

| 条件 | 默认行为 |
|------|----------|
| 所有 target risk_level = Normal | 静默（不通知） |
| 任一 target risk_level = Warning | 通知 |
| 任一 target risk_level = Critical | 通知 |
| 存在 resonance_event | 通知 |

### 可读 Markdown 报告

使用 `references/report-template.md` 模板生成可读报告，包含：
- 总览（critical/warning/normal 计数）
- 风险项列表（按 risk_level 降序）
- 共振事件详情
- 每个风险项的证据、反证、缺口

**成功标准**：JSON 报告 + Markdown 报告均已生成。

# 常见错误处理

| 错误 | 原因 | 降级策略 |
|------|------|----------|
| `batch prediction failed` | 数据点 < 200 | 扩大 time_range（last_24h → last_7d），或降低粒度 |
| `Column '__value__' cannot be resolved` | 使用了 SQL 语法而非 SPL 管道 | 改用 `.metricstore \| prom-call ...` SPL 管道语法 |
| `strictly increasing timestamp` | 在 logstore-tracing 上使用 series_forecast | 改用 metricstore 路径 |
| PromQL parser 拒绝 `\|` | 在 metric_store query 中使用 SPL | 改用 log_store query + SPL 管道 |
| 空结果 | 无匹配数据 | 标记 `no_problem_found`，不重试 |
| 超时 | 查询范围过大 | 缩小 time_range 或减少 forecast_targets 并行度 |

# 参考文件

| 文件 | 用途 | 何时读取 |
|------|------|----------|
| `references/data-source-templates.md` | 各数据源的 SPL/PromQL 查询模板与 CLI 命令模式 | Step 2 取数前 |
| `references/report-template.md` | 风险报告 Markdown 模板 | Step 9 生成报告时 |
| `scripts/runtime_engine.py` | 执行引擎脚本（Profile 解析、结果解析、阈值评估、共振检测） | Step 1-9 全程 |
