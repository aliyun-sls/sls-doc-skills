---
name: rds-inspection
description: 使用脚本批量执行阿里云 RDS 健康巡检，覆盖核心指标、性能、安全、关联日志、趋势检测五个维度，输出结构化巡检报告并附带原始采样与上下游影响。
---

# RDS 数据库实例健康巡检

## 能力上下文边界

本 Skill 用于对阿里云 RDS 数据库实例进行**只读健康巡检**，覆盖以下五个维度：

| 维度 | 脚本 | 巡检项数 | 数据来源 |
|---|---|---|---|
| 核心指标 | `rds-core-inspection.py` | 7 | PromQL（`starops sls promql query`） |
| 性能 | `rds-performance-inspection.py` | 6 | PromQL（`starops sls promql query`） |
| 安全 | `rds-security-inspection.py` | 6 | PromQL（`starops sls promql query`） |
| 关联日志 | `rds-logs-inspection.py` | 2 | SLS 日志查询（`starops sls log query`） |
| 趋势检测 | `rds-trend-inspection.py` | 6 | PromQL + 趋势分析算法 |

**总计：27 项巡检（7+6+6+2+6）**

### 边界约束

- **不执行任何变更操作**：仅读取指标与日志，不修改 RDS 配置、不执行 SQL、不重启实例
- **不访问数据库执行 SQL**：所有数据通过可观测性平台（SLS MetricStore / LogStore）获取
- **不展示敏感信息**：输出中自动脱敏账号、IP、密码、Token 等字段；SQL 文本超过 100 字符自动截断
- **跨 workspace / region 复用**：不依赖固定环境，通过 `--region` / `--project` / `--metricstore` 参数驱动

---

## 数据源策略

### 优先级：SLS PromQL 优先，CloudMonitor 降级

巡检数据获取遵循以下优先级策略：

| 优先级 | 数据源 | 工具 | 适用场景 |
|---|---|---|---|
| **P0（首选）** | SLS MetricStore PromQL | `starops sls promql query` | 所有指标类巡检项（核心/性能/安全/趋势） |
| **P1（降级）** | CloudMonitor 基础指标 | `starops observe metric_set query` | SLS PromQL 查询失败或无数据时降级 |
| **P2（日志）** | SLS LogStore 日志查询 | `starops sls log query` | 关联日志巡检项（慢 SQL、ERROR 日志） |

### 降级触发条件

| 场景 | 触发条件 | 降级行为 |
|---|---|---|
| PromQL 查询超时 | CLI 返回超时（60s） | 自动切换 CloudMonitor 数据源重试一次 |
| PromQL 无数据 | 返回空结果集 | 如提供 CloudMonitor 命名空间则尝试降级；仍无数据则记录 `error`，不静默 `pass` |
| PromQL 权限不足 | CLI 返回权限错误 | 记录 `error`，提示用户检查权限 |
| CloudMonitor 也无数据 | 降级后仍无数据 | 最终记录 `error`，说明数据源缺失 |

### 数据源选择原则

1. **SLS PromQL 为首选**：支持灵活的聚合、rate、increase 等 PromQL 函数，适合复杂阈值判断
2. **CloudMonitor 为降级**：当 SLS 不可用时，使用 CloudMonitor 基础指标作为备选
3. **日志查询独立**：关联日志巡检项直接使用 SLS LogStore 查询，不参与降级逻辑
4. **趋势分析依赖时序数据**：趋势检测巡检项必须使用 SLS PromQL 获取完整时序数据，不支持降级

---

## 执行策略

### 批量执行原则

1. **巡检前必须先列 todo list**：明确要执行的维度与巡检项
2. **优先使用 `scripts/` 下脚本批量执行**：不手动逐条查询
3. **五个脚本可并行执行**：核心 / 性能 / 安全 / 关联日志 / 趋势检测脚本相互独立，可同时运行
4. **使用 `references/report-template.md` 生成报告**：将 JSON 输出渲染为可读报告

### 快速失败与跳过规则

- 单个巡检项查询失败（超时、权限不足、JSON 解析失败）返回 `status=error`，**不阻断其他巡检项**
- `--audit-logstore` 未传入时，日志脚本直接返回 `error` 并提示参数缺失，不执行查询
- 拓扑查询失败降级为空数组并记录 error，不阻断巡检主流程
- 趋势分析算法失败（数据点不足、序列过短）返回 `status=error`，不阻断其他趋势项

### 脚本参数说明

| 参数 | 必填 | 说明 |
|---|---|---|
| `--region` | 是 | 阿里云 region |
| `--project` | 是 | SLS project |
| `--metricstore` | 是 | SLS metricstore |
| `--time-range` | 是 | 时间范围，如 `last_1h` |
| `--limit` | 否 | raw_samples 最大条数（默认 10） |
| `--cases` | 否 | 指定巡检项 case_id 列表 |
| `--list-cases` | 否 | 列出所有巡检项并退出 |
| `--audit-logstore` | 日志脚本必填 | 审计日志 logstore |

### 并行执行示例

```bash
# 五个脚本并行执行
python3 rds-core-inspection.py --region cn-hangzhou --project my-project --metricstore my-ms --time-range last_1h &
python3 rds-performance-inspection.py --region cn-hangzhou --project my-project --metricstore my-ms --time-range last_1h &
python3 rds-security-inspection.py --region cn-hangzhou --project my-project --metricstore my-ms --time-range last_1h &
python3 rds-logs-inspection.py --region cn-hangzhou --project my-project --metricstore my-ms --time-range last_1h --audit-logstore my-audit-log &
python3 rds-trend-inspection.py --region cn-hangzhou --project my-project --metricstore my-ms --time-range last_6h &
wait
```

---

## 组件巡检目录

### 核心指标（7 项）

详见 `references/core.md`

| case_id | severity | 描述 |
|---|---|---|
| rds_cpu_high | P1 | CPU > 80%，持续 5 分钟 |
| rds_memory_high | P1 | 内存 > 85%，持续 5 分钟 |
| rds_disk_high | P2 | 磁盘 > 80%，持续 10 分钟 |
| rds_iops_high | P2 | IOPS > 80%，持续 5 分钟 |
| rds_connections_high | P2 | 连接数 > 80%，持续 5 分钟 |
| rds_instance_down | P1 | 实例状态异常 |
| rds_replication_lag | P2 | 复制延迟 > 10s，持续 5 分钟 |

### 性能（6 项）

详见 `references/performance.md`

| case_id | severity | 描述 |
|---|---|---|
| rds_slow_queries | P2 | 慢查询 > 10 / 5min |
| rds_lock_waits | P2 | 锁等待 > 5 |
| rds_buffer_hit_ratio_low | P3 | 缓冲池命中率 < 95% |
| rds_temp_tables_high | P3 | 临时表占比 > 20% |
| rds_qps_spike | P3 | QPS > 1000 |
| rds_latency_high | P2 | 响应延迟 > 100ms |

### 安全（6 项）

详见 `references/security.md`

| case_id | severity | 描述 |
|---|---|---|
| rds_ssl_disabled | P2 | SSL 未启用 |
| rds_public_access | P1 | 公网访问开启 |
| rds_backup_failed | P1 | 备份失败 |
| rds_backup_retention_low | P3 | 备份保留天数 < 7 |
| rds_audit_log_disabled | P2 | 审计日志未启用 |
| rds_high_privilege_accounts | P2 | 存在高权限账号 |

### 关联日志（2 项）

详见 `references/logs.md`

| case_id | severity | 描述 |
|---|---|---|
| rds_slow_sql_high | P2 | 慢 SQL > 10 / 5min（审计日志） |
| rds_error_log_high | P2 | ERROR 日志 > 10 / 5min（错误日志） |

### 趋势检测（6 项）

详见 `references/trend.md`

| case_id | severity | 描述 |
|---|---|---|
| rds_disk_trend | P2 | 磁盘使用率周增长率异常 |
| rds_iops_trend | P2 | IOPS 使用率周增长率异常 |
| rds_cpu_trend | P3 | CPU 使用率周增长率异常 |
| rds_memory_trend | P3 | 内存使用率周增长率异常 |
| rds_connections_trend | P3 | 连接数使用率周增长率异常 |
| rds_slow_sql_trend | P3 | 慢查询数量周增长率异常 |

---

## 渐进式加载策略

1. **第一层：快速概览** — 执行 `--list-cases` 确认巡检项清单
2. **第二层：批量执行** — 并行运行五个脚本，获取结构化 JSON
3. **第三层：异常聚焦** — 对 `status=find_problem` 的项，查看 `raw_samples` 与 `topology`
4. **第四层：趋势分析** — 对趋势检测项，查看 `trend` 字段中的增长率、趋势方向、样本数和完整性
5. **第五层：报告生成** — 使用 `references/report-template.md` 渲染完整报告

---

## 巡检等级定义

| 等级 | 含义 | 响应要求 |
|---|---|---|
| P1 | 严重 — 直接影响可用性或数据安全 | 立即处理 |
| P2 | 警告 — 性能下降或安全风险 | 24 小时内处理 |
| P3 | 提示 — 优化建议 | 纳入优化计划 |

---

## 操作分级与安全护栏

| 级别 | 操作 | 本 Skill 范围 |
|---|---|---|
| 只读 | 查询指标、日志、拓扑 | ✅ 全部在此范围 |
| 低风险 | 修改告警阈值、调整巡检频率 | ❌ 不执行 |
| 中风险 | 变更 RDS 参数、重启实例 | ❌ 不执行 |
| 高风险 | 删除实例、修改网络配置 | ❌ 不执行 |

**安全护栏**：
- 所有脚本为只读查询，无写操作
- 不拼接用户输入到 SQL 或 shell 命令中（使用 subprocess 参数列表）
- 敏感字段自动脱敏

---

## 诊断逻辑流

```
用户请求 RDS 巡检
    │
    ├─ 1. 列 todo list（明确维度与巡检项）
    │
    ├─ 2. 并行执行五个脚本
    │   ├─ rds-core-inspection.py        → 7 项核心指标
    │   ├─ rds-performance-inspection.py → 6 项性能指标
    │   ├─ rds-security-inspection.py    → 6 项安全指标
    │   ├─ rds-logs-inspection.py        → 2 项关联日志
    │   └─ rds-trend-inspection.py       → 6 项趋势检测
    │
    ├─ 3. 聚合 JSON 输出
    │   ├─ 统计 pass / find_problem / error / no_problem_found
    │   ├─ 提取 find_problem 项的 raw_samples 与 topology
    │   └─ 提取趋势检测项的 trend 字段
    │
    ├─ 4. 生成报告（references/report-template.md）
    │   ├─ 健康状态总览
    │   ├─ 异常项汇总（按 P1/P2/P3 分类）
    │   ├─ 趋势检测汇总（按风险等级分类）
    │   ├─ 分维度详情
    │   └─ 修复建议
    │
    └─ 5. 输出结论与建议
```

---

## Routing

| 用户意图 | 路由 |
|---|---|
| "RDS 巡检" / "数据库健康检查" | 并行执行五个脚本 |
| "只看核心指标" | `rds-core-inspection.py` |
| "只看性能" | `rds-performance-inspection.py` |
| "只看安全" | `rds-security-inspection.py` |
| "看日志" | `rds-logs-inspection.py`（需 `--audit-logstore`） |
| "看趋势" / "趋势检测" | `rds-trend-inspection.py` |
| "列出巡检项" | 任一脚本 `--list-cases` |
| "指定巡检项" | `--cases rds_cpu_high rds_memory_high` |

---

## 输出格式化规范

### JSON 输出结构

```json
{
  "total_cases": 27,
  "passed": 20,
  "find_problem_cases": 5,
  "errors": 1,
  "no_problem_found": 1,
  "has_find_problem": true,
  "results": [
    {
      "case_id": "rds_cpu_high",
      "item": "RDS CPU 使用率过高",
      "severity": "P1",
      "status": "find_problem",
      "duration_seconds": 300,
      "time_range": "last_1h",
      "total_entities": 3,
      "abnormal_count": 1,
      "abnormal_resources": [
        {
          "entity_id": "rm-xxx",
          "entity_name": "rm-xxx",
          "metric_value": 92.5,
          "threshold": 80.0,
          "raw_samples": [
            {"ts": 1780207800, "value": 92.5},
            {"ts": 1780207860, "value": 93.1}
          ],
          "topology": {
            "upstream": [{"entity_id": "app-01", "type": "apm.service"}],
            "downstream": []
          }
        }
      ],
      "raw_query": "avg by (instance_id) (rate(rds_cpu_usage_total[3m])) / 100 * 100",
      "error": ""
    }
  ]
}
```

### 状态枚举

| status | 含义 |
|---|---|
| `pass` | 所有实体均通过阈值检查 |
| `find_problem` | 发现异常实体 |
| `no_problem_found` | 保留状态；当前实现优先使用 `pass` 表示有数据且未越线，数据源缺失使用 `error` |
| `error` | 查询失败（超时、权限、解析错误） |

---

## 确定性设计原则

### 架构模式：数据驱动声明 + 公共引擎

- **业务脚本**（rds-core / rds-performance / rds-security / rds-logs / rds-trend）：只声明巡检项配置（`InspectionCase`），**零计算逻辑**
- **公共引擎**（rds_inspection_common.py）：承载所有计算（查询、解析、评估、格式化、聚合、采样、拓扑查询、趋势分析）
- **新增巡检项 = 新增一个 `InspectionCase` 数据项**，不需要写新的计算代码

### 4 类确定性计算

| 计算类型 | 实现 | 示例 |
|---|---|---|
| 单位换算 | 纯函数，同输入同输出 | `format_bytes(value)` / `format_percent(value)` |
| 聚合计算 | PromQL 层完成聚合，脚本只消费结果 | PromQL 内的 `avg by (instance_id) (rate(...))` |
| 阈值+持续时间 | 阈值、持续时间、比较方向全在数据声明里 | `InspectionCase(duration=300, compare="gt")` + `calc_sustained_seconds()` |
| 输出标准化 | 固定 dataclass → JSON，status 枚举固定 | `InspectionResult(status="pass"/"find_problem"/"no_problem_found"/"error")` |

### 确定性保证

- 所有数值计算函数为**纯函数**（无随机数、无当前时间依赖、无全局状态）
- **同输入同输出**（可复跑验证）
- 脚本独立可运行（不依赖 Skill 上下文）
- 错误处理结构化（超时、解析失败、权限不足都返回 `{"success": false, "error": "..."}`）

---

## LLM 复核辅助字段说明

### raw_samples

- **用途**：异常实例最近 N 条原始时间序列样本或命中日志（N≤10），供 LLM 二次复核
- **填充规则**：仅在 `status=find_problem` 时填充，正常实例（`status=pass`）一律不采样，避免输出膨胀
- **不参与状态判定**：纯附加信息
- **确定性验证时须剥离**：因为依赖外部时刻状态

### topology

- **用途**：通过 UModel 查询异常实例的上下游依赖（应用 / Logstore / 上游数据库等），用于影响面分析
- **查询失败降级**：填充 `{"upstream": [], "downstream": [], "error": "..."}`，不阻断巡检主流程
- **不参与状态判定**：纯附加信息
- **确定性验证时须剥离**：因为依赖外部时刻状态

### investigation_hints

- **用途**：为 LLM 提供排查方向提示，包含可能的根因、关联指标、建议操作
- **填充规则**：在 `InspectionCase` 声明中静态定义，不依赖运行时状态
- **参与报告生成**：用于生成修复建议章节
- **确定性验证时保留**：因为是静态声明

### trend（趋势检测专用）

- **用途**：趋势检测巡检项的附加字段，包含增长率、起始值、结束值、样本数、完整性和趋势方向
- **填充规则**：仅在趋势检测脚本中填充，包含 `growth_rate`、`start_value`、`end_value`、`data_points`、`completeness`、`trend_direction`
- **不参与状态判定**：纯附加信息
- **确定性验证时须剥离**：因为依赖外部时刻状态

### 剥离方法

```bash
jq 'walk(if type=="object" then del(.raw_samples, .topology, .trend) else . end)' output.json > stripped.json
```

---

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/execution-strategy.md` | 工具路线、数据源策略、批量执行、参数说明、JSON 结构 |
| `references/report-template.md` | 报告模板 |
| `references/core.md` | 核心指标巡检项清单与修复建议（含 investigation_hints） |
| `references/performance.md` | 性能巡检项清单与修复建议 |
| `references/security.md` | 安全巡检项清单与修复建议 |
| `references/logs.md` | 关联日志巡检项清单与修复建议 |
| `references/trend.md` | 趋势检测巡检项清单与趋势分析方法 |
