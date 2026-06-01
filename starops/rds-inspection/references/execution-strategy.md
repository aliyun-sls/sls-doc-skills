# RDS 巡检执行策略

## 工具路线定义

| 数据类型 | 工具 | 命令 |
|---|---|---|
| 指标数据 | SLS PromQL | `starops sls promql query` |
| 日志数据 | SLS 日志查询 | `starops sls log query` |
| 拓扑数据 | UModel | `starops umodel topology` |

## 批量执行原则

1. **四个脚本可并行执行**：核心 / 性能 / 安全 / 关联日志脚本相互独立
2. **公共引擎复用**：所有脚本共享 `rds_inspection_common.py`，避免重复逻辑
3. **快速失败**：单个巡检项失败不阻断其他项
4. **结构化错误**：所有错误返回 `status=error` + `error` 字段

## 快速失败与跳过规则

| 场景 | 行为 |
|---|---|
| PromQL 查询超时 | 返回 `status=error`，`error="CLI timeout (60s)"` |
| 日志查询权限不足 | 返回 `status=error`，`error="CLI error (rc=...)"` |
| JSON 解析失败 | 返回 `status=error`，`error="JSON parse error: ..."` |
| `--audit-logstore` 缺失 | 日志脚本直接返回 error，提示参数缺失 |
| 拓扑查询失败 | 降级为空拓扑 `{"upstream": [], "downstream": [], "error": "..."}` |
| 无匹配实体 | 返回 `status=no_problem_found` |

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

## JSON 输出结构示例

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
      "error": ""
    }
  ]
}
```

## 状态说明

| status | 含义 | 触发条件 |
|---|---|---|
| `pass` | 通过 | 所有实体均未超过阈值 |
| `find_problem` | 发现问题 | 至少一个实体超过阈值（含持续时间判断） |
| `no_problem_found` | 未发现问题 | 无数据或无匹配实体 |
| `error` | 错误 | 查询失败（超时、权限、解析错误、参数缺失） |
