# 数据源序列构造模板

本文档定义了各数据源类型如何构造等间隔时间序列并调用 series_forecast / series_describe。

所有模板中的 `{{variable}}` 占位符由 Mission Profile 的 `context` 字段在 Step 1 中替换。

---

## 1. MetricStore prom-call 管道（APM 指标）

### 适用场景

APM MetricStore 中存储的原始指标（如 arms_app_requests_count、arms_app_requests_seconds 等）。

### 前置条件

- 已知 MetricStore 的 project 和 logstore 名称
- 已知 PromQL 查询表达式
- 数据粒度需保证 >= 200 点（5m x 24h = 289 点 OK）

### SPL 管道模板

#### series_forecast

```
.metricstore | prom-call promql_query_range('{{resolved_promql}}') | extend ret = series_forecast(__value__, {{forecast_step}})
```

#### series_describe

```
.metricstore | prom-call promql_query_range('{{resolved_promql}}') | extend desc = series_describe(__value__)
```

#### 同时获取 forecast + describe（推荐，减少一次查询）

```
.metricstore | prom-call promql_query_range('{{resolved_promql}}') | extend ret = series_forecast(__value__, {{forecast_step}}), desc = series_describe(__value__)
```

### CLI 命令

```bash
starops observe log_store query \
  --region {{region}} \
  --project {{project}} \
  --logstore {{store}} \
  --query ".metricstore | prom-call promql_query_range('{{resolved_promql}}') | extend ret = series_forecast(__value__, {{forecast_step}}), desc = series_describe(__value__)" \
  --time-range '{{time_range}}'
```

### 关键约束

- **必须用 `log_store query`**，不是 `metric_store query`（后者只接受 PromQL，拒绝 `|` 字符）
- **必须用 SPL 管道语法** `.metricstore | prom-call ...`，不是普通 SQL
- **不需要** `enable_remote_functions`（SPL 管道模式自动可用）
- **标签名**：APM 原始指标用 `service=` 不是 `serviceName=`
- **数据点要求**：>= 200 点，5m 粒度 x 24h = 289 点满足

### APM 常用 PromQL 模板

```promql
# 请求量（request_count）
sum(sum_over_time_lorc(arms_app_requests_count_ign_destid_endpoint_parent_ppid_prpc_rpc{callKind=~"http|rpc|custom_entry|server|consumer|schedule", service="{{service_name}}"}[5m]))

# 错误数（error_count）
sum(sum_over_time_lorc(arms_app_requests_error_count_ign_destid_endpoint_parent_ppid_prpc_rpc{callKind=~"http|rpc|custom_entry|server|consumer|schedule", service="{{service_name}}"}[5m]))

# 平均延迟（avg_latency）
sum(sum_over_time_lorc(arms_app_requests_seconds_ign_destid_endpoint_parent_ppid_prpc_rpc{callKind=~"http|rpc|custom_entry|server|consumer|schedule", service="{{service_name}}"}[5m]))
/
sum(sum_over_time_lorc(arms_app_requests_count_ign_destid_endpoint_parent_ppid_prpc_rpc{callKind=~"http|rpc|custom_entry|server|consumer|schedule", service="{{service_name}}"}[5m]))

# 错误率（error_rate）
sum(sum_over_time_lorc(arms_app_requests_error_count_ign_destid_endpoint_parent_ppid_prpc_rpc{callKind=~"http|rpc|custom_entry|server|consumer|schedule", service="{{service_name}}"}[5m]))
/
sum(sum_over_time_lorc(arms_app_requests_count_ign_destid_endpoint_parent_ppid_prpc_rpc{callKind=~"http|rpc|custom_entry|server|consumer|schedule", service="{{service_name}}"}[5m]))
```

---

## 2. Prometheus Query（K8s 指标）

### 适用场景

K8s 集群的 Prometheus 指标（container_cpu_usage_seconds_total、container_memory_working_set_bytes 等）。

### 前置条件

- 已知 Prometheus instance ID
- 已知 PromQL 查询表达式
- Prometheus 采集粒度通常 30s-60s，24h 数据量远超 200 点

### PromQL 模板

```promql
# Pod CPU 使用率
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="{{namespace}}", pod=~"{{pod_pattern}}", container!="", container!="POD"}[3m]))

# Pod 内存使用
sum by (pod) (container_memory_working_set_bytes{namespace="{{namespace}}", pod=~"{{pod_pattern}}", container!="", container!="POD"})

# Node CPU 使用率
1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))

# Node 内存可用率
1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)
```

### CLI 命令

#### 路径 A：通过 MetricStore + SPL 管道（推荐，可用 series_forecast）

```bash
starops observe log_store query \
  --region {{region}} \
  --project {{project}} \
  --logstore {{metricstore}} \
  --query ".metricstore | prom-call promql_query_range('{{resolved_promql}}') | extend ret = series_forecast(__value__, {{forecast_step}}), desc = series_describe(__value__)" \
  --time-range '{{time_range}}'
```

#### 路径 B：通过 Prometheus instance（仅取数，不可直接用 series_forecast）

```bash
starops observe metric_store query \
  --prometheus-instance-id {{prometheus_instance_id}} \
  --region {{region}} \
  --query '{{resolved_promql}}' \
  --time-range '{{time_range}}'
```

**注意**：路径 B 返回的是原始 Prometheus 查询结果，不能直接使用 series_forecast。
如需预测，先用路径 B 取数，再用 Python 脚本本地构造等间隔序列后调用。

---

## 3. CloudMonitor Entity（云产品指标）

### 适用场景

RDS / Redis / ECS 等云产品的 CloudMonitor 指标（AliyunRds_CpuUsage、AliyunKvstore_StandardMemoryUsage 等）。

### 前置条件

- 已知 **平台 entity_id**（UModel 中的 entity_id，如 RDS `6aeb06ca6bc759c680ffef2b6a76f8be`）
  - **重要**：`--entity-id` 必须使用平台 entity_id，不是云资源 ID（如 `rm-xxx`）
  - Profile 中 `object_ref.id` 应为平台 entity_id；如有 `object_ref.platform_entity_id` 则优先使用
- 已知 entity domain/type（如 acs / acs.rds.instance）
- 已知 metric_set_domain 和 metric_set_name
- 已知具体 metric 名称（从 signal_id 取）

### CLI 命令

```bash
starops observe metric_store query \
  -w {{workspace}} \
  --entity-domain {{entity_domain}} \
  --entity-type {{entity_type}} \
  --entity-id {{platform_entity_id}} \
  --metric-set-domain {{metric_set_domain}} \
  --metric-set-name {{metric_set_name}} \
  --query '{{signal_id}}' \
  --time-range '{{time_range}}' \
  --raw
```

### 常用 RDS 指标

| metric_name | data_format | 说明 |
|---|---|---|
| AliyunRds_CpuUsage | percent | CPU 使用率 |
| AliyunRds_MemoryUsage | percent | 内存使用率 |
| AliyunRds_DiskUsage | percent | 磁盘使用率 |
| AliyunRds_IOPSUsage | percent | IOPS 使用率 |
| AliyunRds_ConnectionUsage | percent | 连接数使用率 |
| AliyunRds_MySQL_QPS | reqps | MySQL QPS |
| AliyunRds_MySQL_TPS | reqps | MySQL TPS |

### 预测路径

CloudMonitor 指标通过 `metric_store query --raw` 取数，返回 JSON 格式：
```json
[{
  "__name__": "AliyunRds_CpuUsage",
  "__summary__": {"cur_statistics": {"mean_value": 0.19, "max_value": 0.25, ...}},
  "__ts__": "[1782811540000000000, ...]",
  "__value__": "[0.145, 0.163, ...]"
}]
```

runtime_engine.py 内置 `parse_cloudmonitor_raw()` 解析此格式：
- 从 `__summary__.cur_statistics` 提取当前统计量（mean/max/min/p50/p95）
- 从 `__value__` 构造等间隔序列
- 使用线性回归外推预测未来 30 步（因 CloudMonitor 不支持 series_forecast SPL 管道）
- 基于残差标准差计算 95% 置信区间

**注意**：CloudMonitor 的预测精度低于 MetricStore 的 series_forecast（线性回归 vs 时序模型），
对于波动较大的指标，置信度通常标记为 low。

---

## 4. SLS LogStore（日志衍生时序）

### 适用场景

从 SLS LogStore 中聚合出的时序数据（如日志写入量、错误数趋势等）。

### 前置条件

- 已知 LogStore 的 project 和 logstore 名称
- 已知 SLS SQL 或 SPL 查询

### SLS SQL 模板

```sql
-- 日志写入量趋势（按 5 分钟聚合）
* | SELECT date_trunc('minute', __time__ - __time__ % 300) as t, count(*) as cnt FROM log GROUP BY t ORDER BY t

-- 错误日志数趋势
* and (level: ERROR OR status >= 500) | SELECT date_trunc('minute', __time__ - __time__ % 300) as t, count(*) as cnt FROM log GROUP BY t ORDER BY t
```

### CLI 命令

```bash
starops observe log_store query \
  --region {{region}} \
  --project {{project}} \
  --logstore {{store}} \
  --query '{{resolved_query}}' \
  --time-range '{{time_range}}'
```

### 预测路径

LogStore 查询返回的是 SQL 结果（t, cnt 列），不是 SPL 管道。
需要：
1. 取到 (timestamp, value) 数据对
2. 用 Python 脚本构造等间隔序列
3. 如需 series_forecast，通过 MetricStore SPL 管道包装执行

---

## 返回值结构速查

### series_forecast 返回值（ret）

8 元素数组：

| 索引 | 类型 | 含义 |
|:----:|------|------|
| 0 | array[N+M] | 完整时间戳序列（纳秒），N=历史点，M=预测步数 |
| 1 | array[N+M] | 完整值序列（历史值 + null 填充预测位） |
| 2 | array[N+M] | **预测值数组**（前 N 个为拟合值，后 M 个为外推预测） |
| 3 | array[N+M] | **上界数组** |
| 4 | array[N+M] | **下界数组** |
| 5 | int | 输入数据点数 N |
| 6 | int | 预测步数 M |
| 7 | null | 保留 |

### series_describe 返回值（desc）

2 元素数组，desc[0] 为 JSON 字符串，解析后：

| 字段 | 类型 | 含义 |
|------|------|------|
| max / min / mean / sum / std | float | 基础统计 |
| p5 / p25 / p50 / p75 / p95 | float | 分位数 |
| actual_point_count | int | 实际数据点 |
| missing_point_count | int | 缺失点 |
| time_granularity | int | 时间粒度（纳秒） |
| segments[] | array | 分段形状（STABLE_PLATEAU / STEP_UP / SPIKE_RECOVERY / CURVED_PEAK 等） |
| transitions[] | array | 转换点（含 confidence） |
