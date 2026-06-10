# PromQL 模板库

## 策略 1：趋势预测（trend_prediction）

### 模板

```promql
# 当前值
avg by ({group_by}) ({metric})

# 变化率（每小时）
avg by ({group_by}) (deriv({metric}[6h]))

# 预测值（N 秒后）
avg by ({group_by}) (predict_linear({metric}[6h], {predict_window}))
```

### 参数说明

| 参数 | 说明 | 示例 |
|---|---|---|
| `metric` | 指标名称 | `AliyunEcs_CPUUtilization` |
| `group_by` | 分组标签 | `instance_id` |
| `predict_window` | 预测窗口（秒） | `86400`（1 天） |

### 使用示例

```promql
# ECS CPU 当前值
avg by (instance_id) (AliyunEcs_CPUUtilization)

# ECS CPU 变化率
avg by (instance_id) (deriv(AliyunEcs_CPUUtilization[6h]))

# ECS CPU 1 天预测
avg by (instance_id) (predict_linear(AliyunEcs_CPUUtilization[6h], 86400))
```

### 注意事项

- `deriv()` 返回每秒变化量，脚本内转换为每小时
- `predict_linear()` 基于最近 6h 数据线性外推
- 预测窗口不宜过大（建议 <= 7 天），否则精度下降

---

## 策略 2：基线偏离（baseline_deviation）

### 模板

```promql
# 当前值
avg by ({group_by}) ({metric})

# 昨日同期
avg by ({group_by}) ({metric} offset 1d)

# 7 天均值
avg by ({group_by}) (avg_over_time({metric}[7d]))
```

### 参数说明

| 参数 | 说明 | 示例 |
|---|---|---|
| `metric` | 指标名称 | `node_cpu_seconds_total` |
| `group_by` | 分组标签 | `node` |

### 使用示例

```promql
# Node CPU 当前值
100 - (avg by (node) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Node CPU 昨日同期
100 - (avg by (node) (rate(node_cpu_seconds_total{mode="idle"}[5m]) offset 1d) * 100)
```

### 注意事项

- `offset 1d` 表示 1 天前的数据
- 偏离倍数 = 当前值 / 基线值
- 偏离 > 2x 或 < 0.5x 触发 Warning

---

## 策略 3：缓慢增长（slow_growth）

### 模板

```promql
# 当前值
avg by ({group_by}) ({metric})

# 变化率
avg by ({group_by}) (deriv({metric}[6h]))

# 7 天预测
avg by ({group_by}) (predict_linear({metric}[6h], 604800))

# 7 天均值
avg by ({group_by}) (avg_over_time({metric}[7d]))
```

### 参数说明

| 参数 | 说明 | 示例 |
|---|---|---|
| `metric` | 指标名称 | `AliyunEcs_diskusage_utilization` |
| `604800` | 7 天秒数 | 固定值 |

### 使用示例

```promql
# ECS 磁盘 7 天预测
avg by (instance_id) (predict_linear(AliyunEcs_diskusage_utilization[6h], 604800))

# ECS 磁盘 7 天均值
avg by (instance_id) (avg_over_time(AliyunEcs_diskusage_utilization[7d]))
```

### 注意事项

- 缓慢增长 = deriv > 0 但短期不超阈值
- 7 天预测超阈值触发 Warning
- 适用于磁盘、内存等持续增长型指标

---

## 策略 4：阈值突破（threshold_breach）

### 模板

```promql
# 当前值（直接比较阈值）
avg by ({group_by}) ({metric})
```

### 参数说明

| 参数 | 说明 | 示例 |
|---|---|---|
| `metric` | 指标名称 | `error_rate` |
| `warning_threshold` | Warning 阈值 | `5.0` |
| `critical_threshold` | Critical 阈值 | `10.0` |

### 使用示例

```promql
# 服务错误率（APM 预计算指标）
error_rate

# 服务延迟（毫秒）
avg_request_latency_seconds * 1000
```

### 注意事项

- 当前值 > critical → Critical 风险
- 当前值 > warning → Warning 风险
- 超标幅度 = (当前值 - 阈值) / 阈值 * 100%
- APM 域使用 `metric_set query` 获取预聚合指标，不使用 PromQL 函数
