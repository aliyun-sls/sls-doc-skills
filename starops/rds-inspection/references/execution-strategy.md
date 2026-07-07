# RDS 巡检执行策略

## 工具路线定义

| 数据类型 | 工具 | 命令 |
|---|---|---|
| 指标数据（首选） | SLS PromQL | `starops sls promql query` |
| 指标数据（降级） | CloudMonitor 基础指标 | `starops observe metric_set query` |
| 日志数据 | SLS 日志查询 | `starops sls log query` |
| 拓扑数据 | UModel | `starops umodel topology` |

## 数据源策略：SLS PromQL 优先，CloudMonitor 降级

### 优先级定义

| 优先级 | 数据源 | 工具 | 适用场景 |
|---|---|---|---|
| **P0（首选）** | SLS MetricStore PromQL | `starops sls promql query` | 所有指标类巡检项（核心/性能/安全/趋势） |
| **P1（降级）** | CloudMonitor 基础指标 | `starops observe metric_set query` | SLS PromQL 查询失败或超时时降级 |
| **P2（日志）** | SLS LogStore 日志查询 | `starops sls log query` | 关联日志巡检项（慢 SQL、ERROR 日志） |

### 降级触发条件

| 场景 | 触发条件 | 降级行为 |
|---|---|---|
| PromQL 查询超时 | CLI 返回超时（60s） | 自动切换 CloudMonitor 数据源重试一次 |
| PromQL 无数据 | 返回空结果集 | 如提供 CloudMonitor 命名空间则尝试降级；仍无数据则记录 `error`，不静默 `pass` |
| PromQL 权限不足 | CLI 返回权限错误 | 记录 `error`，提示用户检查权限 |
| CloudMonitor 也无数据 | 降级后仍无数据 | 最终记录 `error`，说明数据源缺失 |

### 降级实现逻辑

```python
def query_with_fallback(promql, cloudmonitor_params, ...):
    """SLS PromQL 优先，失败时降级到 CloudMonitor"""
    # 1. 尝试 SLS PromQL
    result = sls_promql_query(promql, ...)
    if result["success"]:
        return result

    # 2. 判断是否可降级
    if result["error_type"] == "timeout":
        # 超时 → 降级到 CloudMonitor
        fallback_result = cloudmonitor_query(cloudmonitor_params, ...)
        if fallback_result["success"]:
            fallback_result["data_source"] = "cloudmonitor"
            return fallback_result

    # 3. 不可降级或降级也失败 → 返回错误
    return result
```

### 趋势检测不支持降级

趋势检测巡检项（`rds-trend-inspection.py`）必须使用 SLS PromQL 获取完整时序数据，不支持降级到 CloudMonitor。原因：
- 趋势分析需要连续的时间序列数据点
- CloudMonitor 基础指标的数据粒度和时间范围可能不满足趋势分析需求
- 降级后数据不一致会导致增长率判断不可靠

## 批量执行原则

1. **五个脚本可并行执行**：核心 / 性能 / 安全 / 关联日志 / 趋势检测脚本相互独立
2. **公共引擎复用**：所有脚本共享 `rds_inspection_common.py`，避免重复逻辑
3. **快速失败**：单个巡检项失败不阻断其他项
4. **结构化错误**：所有错误返回 `status=error` + `error` 字段

## 快速失败与跳过规则

| 场景 | 行为 |
|---|---|
| PromQL 查询超时 | 降级到 CloudMonitor 重试一次；仍失败则返回 `status=error`，`error="CLI timeout (60s)"` |
| 日志查询权限不足 | 返回 `status=error`，`error="CLI error (rc=...)"` |
| JSON 解析失败 | 返回 `status=error`，`error="JSON parse error: ..."` |
| `--audit-logstore` 缺失 | 日志脚本直接返回 error，提示参数缺失 |
| 拓扑查询失败 | 降级为空拓扑 `{"upstream": [], "downstream": [], "error": "..."}` |
| 无匹配实体 / 无指标数据 | 返回 `status=error`，说明数据源未返回可评估样本 |
| 趋势分析数据不足 | 返回 `status=error`，`error="Insufficient data points for trend analysis"` |

## 脚本参数说明

### 通用参数（所有脚本）

| 参数 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `--region` | 是 | - | 阿里云 region |
| `--project` | 是 | - | SLS project |
| `--metricstore` | 是 | - | SLS metricstore |
| `--time-range` | 是 | - | 时间范围，如 `last_1h` |
| `--limit` | 否 | 10 | raw_samples 最大条数 |
| `--cases` | 否 | 全部 | 指定巡检项 case_id 列表 |
| `--list-cases` | 否 | - | 列出所有巡检项并退出 |

### 日志脚本专用参数

| 参数 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `--audit-logstore` | **是** | - | 审计日志 logstore |

### CloudMonitor 降级参数

| 参数 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `--cloudmonitor-namespace` | 否 | 空 | 指标脚本 CloudMonitor 降级命名空间；趋势脚本不使用 |

## JSON 输出结构示例

### 标准巡检项输出

```json
{
  "total_cases": 7,
  "passed": 5,
  "find_problem_cases": 1,
  "errors": 1,
  "no_problem_found": 0,
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
            "upstream": [
              {"entity_id": "app-01", "type": "apm.service", "title": "frontend-app"}
            ],
            "downstream": []
          }
        }
      ],
      "raw_query": "avg by (instance_id) (rate(rds_cpu_usage_total[3m])) / 100 * 100",
      "data_source": "promql",
      "error": ""
    }
  ]
}
```

### 趋势检测项输出

```json
{
  "case_id": "rds_cpu_trend",
  "item": "CPU 使用率趋势检测",
  "severity": "P2",
  "status": "find_problem",
  "time_range": "last_6h",
  "total_entities": 3,
  "abnormal_count": 1,
  "abnormal_resources": [
    {
      "entity_id": "rm-xxx",
      "entity_name": "rm-xxx",
      "metric_value": 72.3,
      "threshold": 80.0,
      "trend": {
        "trend_direction": "increasing",
        "growth_rate": 18.4,
        "start_value": 61.1,
        "end_value": 72.3,
        "data_points": 168,
        "completeness": "high"
      }
    }
  ],
  "raw_query": "avg by (instance_id) (rate(rds_cpu_usage_total[3m])) / 100 * 100",
  "data_source": "promql",
  "error": ""
}
```

### CloudMonitor 降级标记

当数据来自 CloudMonitor 降级时，`data_source` 字段标记为 `cloudmonitor`：

```json
{
  "case_id": "rds_cpu_high",
  "data_source": "cloudmonitor",
  "raw_query": "CloudMonitor: acs_rds_dashboard / CpuUsage",
  "..."
}
```

## 状态说明

| status | 含义 | 触发条件 |
|---|---|---|
| `pass` | 通过 | 所有实体均未超过阈值 |
| `find_problem` | 发现问题 | 至少一个实体超过阈值（含持续时间判断） |
| `no_problem_found` | 未发现问题 | 保留状态；当前实现优先使用 `pass` 表示有数据且未越线，数据源缺失使用 `error` |
| `error` | 错误 | 查询失败（超时、权限、解析错误、参数缺失） |

## 并行执行示例

```bash
# 五个脚本并行执行（推荐）
python3 rds-core-inspection.py --region cn-hangzhou --project my-project --metricstore my-ms --time-range last_1h &
python3 rds-performance-inspection.py --region cn-hangzhou --project my-project --metricstore my-ms --time-range last_1h &
python3 rds-security-inspection.py --region cn-hangzhou --project my-project --metricstore my-ms --time-range last_1h &
python3 rds-logs-inspection.py --region cn-hangzhou --project my-project --metricstore my-ms --time-range last_1h --audit-logstore my-audit-log &
python3 rds-trend-inspection.py --region cn-hangzhou --project my-project --metricstore my-ms --time-range last_6h &
wait

# 合并五个脚本的 JSON 输出
python3 -c "
import json, glob
merged = {'total_cases': 0, 'passed': 0, 'find_problem_cases': 0, 'errors': 0, 'no_problem_found': 0, 'results': []}
for f in glob.glob('rds-*-output.json'):
    with open(f) as fh:
        data = json.load(fh)
        merged['total_cases'] += data['total_cases']
        merged['passed'] += data['passed']
        merged['find_problem_cases'] += data['find_problem_cases']
        merged['errors'] += data['errors']
        merged['no_problem_found'] += data['no_problem_found']
        merged['results'].extend(data['results'])
merged['has_find_problem'] = merged['find_problem_cases'] > 0
with open('rds-inspection-report.json', 'w') as out:
    json.dump(merged, out, indent=2, ensure_ascii=False)
"
```
