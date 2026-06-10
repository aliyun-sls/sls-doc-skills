---
name: capacity-risk-prediction
description: 跨域容量风险预测与服务饱和度评估，覆盖 ECS/RDS/Redis/K8s/APM 三个域 12 项巡检，执行趋势预测、基线偏离、缓慢增长、阈值突破 4 种评估策略，输出结构化风险报告。
---

# 跨域容量风险预测与服务饱和度评估

## 能力上下文边界

本 Skill 用于对跨域基础设施与业务服务进行**容量风险预测与饱和度评估**，覆盖以下三个域：

| 域 | 脚本 | 巡检项数 | 数据来源 |
|---|---|---|---|
| acs 基础资源 | `infra-capacity-prediction.py` | 6 | PromQL（`starops sls promql query`） |
| k8s 集群资源 | `k8s-capacity-prediction.py` | 3 | PromQL（`starops sls promql query`） |
| apm 业务服务 | `apm-risk-prediction.py` | 3 | APM 指标（`starops observe metric_set query`） |

**总计：12 项巡检**

### 边界约束

- **不执行任何变更操作**：仅读取指标数据，不修改资源配置、不扩缩容、不重启实例
- **不访问数据库或容器**：所有数据通过可观测性平台（SLS MetricStore / APM MetricSet）获取
- **不展示敏感信息**：输出中自动脱敏账号、IP、密码、Token 等字段
- **跨 workspace / region 复用**：不依赖固定环境，通过 `--region` / `--project` / `--metricstore` 参数驱动

---

## 执行策略

### 批量执行原则

1. **巡检前必须先列 todo list**：明确要执行的域与巡检项
2. **优先使用 `scripts/` 下脚本批量执行**：不手动逐条查询
3. **三个脚本可并行执行**：acs / k8s / apm 脚本相互独立，可同时运行
4. **使用 `references/report-template.md` 生成报告**：将 JSON 输出渲染为可读报告

### 快速失败与跳过规则

- 单个巡检项查询失败（超时、权限不足、JSON 解析失败）返回 `status=error`，**不阻断其他巡检项**
- PromQL 查询返回空结果时，标记为 `no_problem_found`，不重试
- APM 域指标数据缺失时，标记为 `no_problem_found`，降级为空趋势

### 脚本参数说明

| 参数 | 必填 | 说明 |
|---|---|---|
| `--region` | 是 | 阿里云 region |
| `--project` | 是 | SLS project |
| `--metricstore` | 是 | SLS metricstore |
| `--time-range` | 是 | 时间范围，如 `last_6h` |
| `--cases` | 否 | 指定巡检项 case_id 列表 |
| `--list-cases` | 否 | 列出所有巡检项并退出 |

APM 域额外参数：

| 参数 | 必填 | 说明 |
|---|---|---|
| `--workspace` | 是 | UModel workspace |
| `--entity-domain` | 是 | 实体域，如 `apm` |
| `--entity-type` | 是 | 实体类型，如 `apm.service` |
| `--entity-id` | 是 | 实体 ID |

### 并行执行示例

```bash
# 三个脚本并行执行
python3 infra-capacity-prediction.py --region cn-hangzhou --project my-project --metricstore my-ms --time-range last_6h &
python3 k8s-capacity-prediction.py --region cn-hangzhou --project my-project --metricstore my-ms --time-range last_6h &
python3 apm-risk-prediction.py --workspace my-ws --entity-domain apm --entity-type apm.service --entity-id svc-xxx --time-range last_6h &
wait
```

---

## 4 种评估策略详解

### 策略 1：趋势预测（trend_prediction）

**适用场景**：当前值在阈值 50%-90%，且变化率 > 0（持续增长）

**核心 PromQL**：
- 当前值：`metric`
- 变化率：`deriv(metric[6h])`
- 预测值：`predict_linear(metric[6h], N)`（N 为预测窗口秒数）

**判定逻辑**：
1. 当前值 > warning_threshold * 0.5 且 < warning_threshold
2. deriv > 0（持续增长）
3. predict_linear 预测值 > warning_threshold → 触发风险
4. 计算 `days_to_warning`：剩余天数

**输出字段**：`current_value`, `deriv_value`, `predicted_value`, `days_to_warning`

### 策略 2：基线偏离（baseline_deviation）

**适用场景**：检测异常突增/突降，日环比或周基线偏离显著

**核心 PromQL**：
- 当前值：`metric`
- 昨日同期：`metric offset 1d`
- 7 天均值：`avg_over_time(metric[7d])`

**判定逻辑**：
1. 计算偏离倍数：`current / offset_1d`
2. 偏离倍数 > 2.0 或 < 0.5 → 触发风险
3. 计算偏离方向（spike / drop）

**输出字段**：`current_value`, `baseline_value`, `deviation_ratio`, `deviation_direction`

### 策略 3：缓慢增长（slow_growth）

**适用场景**：deriv > 0 但绝对值小，短期不会超阈值，长期有容量风险

**核心 PromQL**：
- 7 天预测：`predict_linear(metric[6h], 604800)`（604800 = 7 天秒数）
- 7 天均值：`avg_over_time(metric[7d])`

**判定逻辑**：
1. deriv > 0 但 predict_linear(6h) < warning_threshold
2. predict_linear(7d) > warning_threshold → 触发缓慢增长风险
3. 计算 7 天预测值与基线差

**输出字段**：`current_value`, `predicted_7d_value`, `avg_7d_value`, `days_to_warning`

### 策略 4：阈值突破（threshold_breach）

**适用场景**：当前值已超过 Warning 或 Critical 阈值

**核心计算**：
- 当前值 vs warning_threshold / critical_threshold

**判定逻辑**：
1. current > critical → Critical 风险
2. current > warning → Warning 风险
3. 计算超标幅度百分比

**输出字段**：`current_value`, `warning_threshold`, `critical_threshold`, `risk_level`, `exceed_percent`

---

## 巡检项目录

### acs 基础资源（6 项）

详见 `references/infra.md`

| case_id | 指标 | 策略 | 阈值 (W/C) | 级别 |
|---|---|---|---|---|
| ecs_cpu_trend | AliyunEcs_CPUUtilization | 趋势预测 | 85% / 95% | P1 |
| ecs_disk_trend | AliyunEcs_diskusage_utilization | 缓慢增长 | 80% / 90% | P1 |
| ecs_memory_trend | AliyunEcs_memory_usedutilization | 趋势预测 | 85% / 95% | P2 |
| rds_cpu_trend | AliyunRds_CpuUsage | 趋势预测 | 70% / 85% | P1 |
| rds_conn_trend | AliyunRds_ConnectionUsage | 趋势预测 | 70% / 85% | P2 |
| redis_memory_trend | AliyunKvstore_StandardMemoryUsage | 缓慢增长 | 75% / 90% | P1 |

### k8s 集群资源（3 项）

详见 `references/k8s.md`

| case_id | 指标 | 策略 | 阈值 (W/C) | 级别 |
|---|---|---|---|---|
| node_cpu_trend | node_cpu_seconds_total | 趋势预测 + 基线偏离 | 70% / 85% | P1 |
| node_memory_trend | node_memory_MemAvailable_bytes | 趋势预测 | 80% / 90% | P1 |
| pod_memory_trend | container_memory_working_set_bytes | 缓慢增长 | 80% / 95% | P2 |

### apm 业务服务（3 项）

详见 `references/apm.md`

| case_id | 指标 | 策略 | 阈值 (W/C) | 级别 |
|---|---|---|---|---|
| service_error_rate | error_rate | 阈值突破 | 5% / 10% | P1 |
| service_latency | avg_request_latency_seconds | 阈值突破 + 趋势 | 200ms / 500ms | P1 |
| service_qps_spike | request_count | 基线偏离 | 日环比 > 2x | P2 |

---

## 风险等级定义

| 等级 | 含义 | 响应要求 |
|---|---|---|
| Critical | 已超过 Critical 阈值或预测 24h 内超限 | 立即处理 |
| Warning | 超过 Warning 阈值或预测 7 天内超限 | 24 小时内处理 |
| Normal | 当前值正常且趋势平稳 | 持续观察 |

---

## 输出格式化规范

### JSON 输出结构

```json
{
  "total_cases": 12,
  "critical_cases": 1,
  "warning_cases": 3,
  "normal_cases": 7,
  "errors": 1,
  "no_problem_found": 0,
  "has_critical": true,
  "has_warning": true,
  "results": [
    {
      "case_id": "ecs_cpu_trend",
      "item": "ECS CPU 趋势预测",
      "severity": "P1",
      "strategy": "trend_prediction",
      "status": "find_problem",
      "risk_level": "warning",
      "time_range": "last_6h",
      "entity_id": "i-xxx",
      "entity_name": "web-server-01",
      "current_value": 78.5,
      "warning_threshold": 85.0,
      "critical_threshold": 95.0,
      "deriv_value": 2.3,
      "predicted_value": 92.1,
      "days_to_warning": 3.5,
      "baseline_value": null,
      "deviation_ratio": null,
      "exceed_percent": null,
      "raw_query": "avg by (instance_id) (AliyunEcs_CPUUtilization)",
      "error": ""
    }
  ]
}
```

### 状态枚举

| status | 含义 |
|---|---|
| `pass` | 所有实体均通过风险评估 |
| `find_problem` | 发现容量风险实体 |
| `no_problem_found` | 无数据或无匹配实体 |
| `error` | 查询失败（超时、权限、解析错误） |

### 风险等级枚举

| risk_level | 含义 |
|---|---|
| `critical` | 严重风险 |
| `warning` | 警告风险 |
| `normal` | 正常 |
| `null` | 无数据或错误 |

---

## 确定性设计原则

### 架构模式：数据驱动声明 + 公共引擎

- **业务脚本**（infra / k8s / apm）：只声明巡检项配置（`PredictionCase`），**零计算逻辑**
- **公共引擎**（capacity_prediction_common.py）：承载所有计算（查询、解析、评估、格式化、聚合）
- **新增巡检项 = 新增一个 `PredictionCase` 数据项**，不需要写新的计算代码

### 4 类确定性计算

| 计算类型 | 实现 | 示例 |
|---|---|---|
| PromQL 函数 | 服务端计算，脚本只消费结果 | `deriv()`, `predict_linear()`, `avg_over_time()` |
| 线性回归 | 纯函数，同输入同输出 | `linear_regression(timestamps, values)` |
| 阈值比较 | 纯函数，无时间依赖 | `evaluate_trend()`, `evaluate_threshold()` |
| 输出标准化 | 固定 dataclass → JSON，status/risk_level 枚举固定 | `PredictionResult` |

### 确定性保证

- 所有数值计算函数为**纯函数**（无随机数、无当前时间依赖、无全局状态）
- **同输入同输出**（可复跑验证）
- 脚本独立可运行（不依赖 Skill 上下文）
- 错误处理结构化（超时、解析失败、权限不足都返回 `{"status": "error", "error": "..."}`）

---

## 诊断逻辑流

```
用户请求容量风险预测
    │
    ├─ 1. 列 todo list（明确域与巡检项）
    │
    ├─ 2. 并行执行三个脚本
    │   ├─ infra-capacity-prediction.py  → 6 项 acs 资源
    │   ├─ k8s-capacity-prediction.py    → 3 项 k8s 资源
    │   └─ apm-risk-prediction.py        → 3 项 apm 服务
    │
    ├─ 3. 聚合 JSON 输出
    │   ├─ 统计 critical / warning / normal / error
    │   └─ 提取 find_problem 项的预测值与剩余天数
    │
    ├─ 4. 生成报告（references/report-template.md）
    │   ├─ 风险状态总览
    │   ├─ 按域分组的详细评估
    │   └─ 整体建议
    │
    └─ 5. 输出结论与建议
```

---

## Routing

| 用户意图 | 路由 |
|---|---|
| "容量风险预测" / "容量评估" / "饱和度分析" | 并行执行三个脚本 |
| "只看 acs 资源" / "ECS/RDS/Redis 容量" | `infra-capacity-prediction.py` |
| "只看 k8s" / "Node/Pod 容量" | `k8s-capacity-prediction.py` |
| "只看 APM" / "服务错误率/延迟/QPS" | `apm-risk-prediction.py` |
| "列出巡检项" | 任一脚本 `--list-cases` |
| "指定巡检项" | `--cases ecs_cpu_trend rds_cpu_trend` |
| "趋势预测" / "基线偏离" / "缓慢增长" / "阈值突破" | 按策略类型筛选 |

---

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/execution-strategy.md` | 工具路线、批量执行、参数说明、JSON 结构 |
| `references/report-template.md` | 报告模板 |
| `references/promql-templates.md` | 4 种策略的 PromQL 模板库 |
| `references/infra.md` | acs 域巡检项清单与修复建议 |
| `references/k8s.md` | k8s 域巡检项清单与修复建议 |
| `references/apm.md` | apm 域巡检项清单与修复建议 |
