# 执行策略

## 工具路线

| 域 | 工具 | 命令 |
|---|---|---|
| acs / k8s | `starops sls promql query` | PromQL 查询，支持 deriv / predict_linear / avg_over_time / offset / holt_winters |
| apm | `starops observe metric_set query` | APM 预聚合指标摘要查询 |
| log | `starops sls query` | SLS SQL 查询，支持 ts_predicate_arma / ts_decompose |

## 批量执行原则

1. **巡检前必须先列 todo list**：明确要执行的域与巡检项
2. **优先使用 `scripts/` 下脚本批量执行**：不手动逐条查询
3. **四个脚本可并行执行**：acs / k8s / apm / log 脚本相互独立
4. **使用 `references/report-template.md` 生成报告**：将 JSON 输出渲染为可读报告

## 快速失败规则

- 单个巡检项查询失败返回 `status=error`，不阻断其他巡检项
- PromQL 查询返回空结果标记为 `no_problem_found`，不重试
- APM 域指标数据缺失标记为 `no_problem_found`，降级为空趋势
- Log 域 SLS SQL 执行失败标记为 `error`，记录错误信息
- CLI 超时（PromQL 60s / SLS 120s）自动标记为 error

## 参数说明

### acs / k8s 域

| 参数 | 必填 | 说明 |
|---|---|---|
| `--region` | 是 | 阿里云 region |
| `--project` | 是 | SLS project |
| `--metricstore` | 是 | SLS metricstore |
| `--time-range` | 是 | 时间范围，如 `last_6h` |
| `--cases` | 否 | 指定巡检项 case_id 列表 |
| `--list-cases` | 否 | 列出所有巡检项并退出 |

### apm 域

| 参数 | 必填 | 说明 |
|---|---|---|
| `--workspace` | 是 | UModel workspace |
| `--entity-domain` | 是 | 实体域，如 `apm` |
| `--entity-type` | 是 | 实体类型，如 `apm.service` |
| `--entity-id` | 是 | 实体 ID |
| `--time-range` | 是 | 时间范围 |
| `--cases` | 否 | 指定巡检项 case_id 列表 |
| `--list-cases` | 否 | 列出所有巡检项并退出 |

### log 域

| 参数 | 必填 | 说明 |
|---|---|---|
| `--region` | 是 | 阿里云 region |
| `--logstore-project` | 是 | SLS Project 名称 |
| `--logstore` | 是 | LogStore 名称 |
| `--log-filter` | 否 | 日志过滤条件 |
| `--time-range` | 是 | 时间范围 |
| `--cases` | 否 | 指定巡检项 case_id 列表 |
| `--list-cases` | 否 | 列出所有巡检项并退出 |

## JSON 输出结构

```json
{
  "total_cases": 15,
  "critical_cases": 1,
  "warning_cases": 3,
  "normal_cases": 10,
  "errors": 0,
  "no_problem_found": 1,
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
      "raw_query": "...",
      "error": ""
    }
  ]
}
```

## 并行执行示例

```bash
# 四个脚本并行执行
python3 infra-capacity-prediction.py --region cn-hangzhou --project my-project --metricstore my-ms --time-range last_6h &
python3 k8s-capacity-prediction.py --region cn-hangzhou --project my-project --metricstore my-ms --time-range last_6h &
python3 apm-risk-prediction.py --workspace my-ws --entity-domain apm --entity-type apm.service --entity-id svc-xxx --time-range last_6h &
python3 log-capacity-prediction.py --region cn-hangzhou --logstore-project my-log-project --logstore my-logstore --log-filter "namespace: default" --time-range last_6h &
wait
```
