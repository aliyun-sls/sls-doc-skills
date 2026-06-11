# SLS SQL 模板库

## 策略 6：ARIMA 预测（arima_prediction / ts_predicate_arma）

### 模板

```sql
{filter} | SELECT ts_predicate_arma(t, cnt, {p}, {d}, {q}, {n}, {step})
FROM (
  SELECT time_series(__time__, '{interval}', '%Y-%m-%d %H:%i:%s', '0') as t,
         count(*) as cnt
  FROM log
  GROUP BY t
  ORDER BY t
)
WHERE cnt > 0
```

### 参数说明

| 参数 | 说明 | 默认值 |
|---|---|---|
| `{filter}` | 日志过滤条件 | `*` |
| `{p}` | ARIMA AR 阶数 | 1 |
| `{d}` | ARIMA 差分阶数 | 1 |
| `{q}` | ARIMA MA 阶数 | 1 |
| `{n}` | 预测步数 | 24 |
| `{step}` | 预测步长 | 1 |
| `{interval}` | 时间分桶间隔 | `5m` |

### 使用示例

```sql
-- 请求量 ARIMA 预测（5 分钟粒度，预测 24 步）
* | SELECT ts_predicate_arma(t, cnt, 1, 1, 1, 24, 1)
FROM (
  SELECT time_series(__time__, '5m', '%Y-%m-%d %H:%i:%s', '0') as t,
         count(*) as cnt
  FROM log
  GROUP BY t
  ORDER BY t
)
WHERE cnt > 0

-- 带过滤条件的 ARIMA 预测
resources.k8s.namespace.name: cms-demo | SELECT ts_predicate_arma(t, cnt, 1, 1, 1, 24, 1)
FROM (
  SELECT time_series(__time__, '5m', '%Y-%m-%d %H:%i:%s', '0') as t,
         count(*) as cnt
  FROM log
  GROUP BY t
  ORDER BY t
)
WHERE cnt > 0
```

### 返回格式

```json
[
  {"t": "2024-01-01 00:00:00", "y": 100, "y_predict": 102, "y_lower": 95, "y_upper": 109},
  {"t": "2024-01-01 00:05:00", "y": 105, "y_predict": 107, "y_lower": 99, "y_upper": 115}
]
```

### 注意事项

- `ts_predicate_arma` 返回包含历史拟合和未来预测的完整序列
- 预测值在 `y_predict` 列，实际值在 `y` 列
- 置信区间在 `y_lower` 和 `y_upper` 列
- 需要至少 30 个数据点才能获得可靠的 ARIMA 模型
- 预测步数不宜过大（建议 <= 48），否则精度下降

---

## 策略 7：分解与异常检测（decomposition_anomaly / ts_decompose）

### 模板

```sql
{filter} | SELECT ts_decompose(t, cnt)
FROM (
  SELECT time_series(__time__, '{interval}', '%Y-%m-%d %H:%i:%s', '0') as t,
         count(*) as cnt
  FROM log
  GROUP BY t
  ORDER BY t
)
WHERE cnt > 0
```

### 参数说明

| 参数 | 说明 | 默认值 |
|---|---|---|
| `{filter}` | 日志过滤条件 | `*` |
| `{interval}` | 时间分桶间隔 | `5m` |

### 使用示例

```sql
-- 日志量分解（发现周期性和趋势）
* | SELECT ts_decompose(t, cnt)
FROM (
  SELECT time_series(__time__, '5m', '%Y-%m-%d %H:%i:%s', '0') as t,
         count(*) as cnt
  FROM log
  GROUP BY t
  ORDER BY t
)
WHERE cnt > 0

-- 错误数分解（检测异常模式）
status >= 400 | SELECT ts_decompose(t, cnt)
FROM (
  SELECT time_series(__time__, '5m', '%Y-%m-%d %H:%i:%s', '0') as t,
         count(*) as cnt
  FROM log
  GROUP BY t
  ORDER BY t
)
WHERE cnt > 0
```

### 返回格式

```json
[
  {"t": "2024-01-01 00:00:00", "raw": 100, "trend": 95, "seasonal": 3, "residual": 2},
  {"t": "2024-01-01 00:05:00", "raw": 110, "trend": 96, "seasonal": 5, "residual": 9}
]
```

### 异常判定逻辑

1. 计算残差标准差（residual_std）
2. 残差绝对值 > 2 * residual_std → 异常点
3. 异常比例 > 0.8 → Warning
4. 异常比例 > 0.95 → Critical

### 注意事项

- `ts_decompose` 将时序分解为 trend（趋势）、seasonal（季节性）、residual（残差）
- 需要至少 2 个完整周期的数据才能检测季节性
- 残差标准差是异常检测的关键指标
- 适用于发现周期性模式和统计异常
