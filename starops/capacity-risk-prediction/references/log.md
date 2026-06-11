# Log 日志衍生时序巡检项清单

## 巡检项总览

| case_id | 数据源 | 策略 | Warning | Critical | 级别 |
|---|---|---|---|---|---|
| log_request_volume | LogStore 请求量时序 | ARIMA 预测 | 预测值超当前 2x | 超 3x | P1 |
| log_error_rate | LogStore 错误数时序 | 分解与异常检测 | 异常概率 > 0.8 | > 0.95 | P1 |
| log_volume_trend | LogStore 日志量时序 | 分解与异常检测 | 残差超 2 倍标准差 | — | P2 |

## Log 域特殊实现

Log 域与 acs/k8s/apm 域的关键区别：

1. **使用 `starops sls query`**：执行 SLS SQL 查询，而非 PromQL 或 metric_set query
2. **时序函数**：使用 SLS 内置时序函数（ts_predicate_arma / ts_decompose）在服务端完成计算
3. **构造时序**：通过 `time_series(__time__, interval, format, '0')` + `count(*)` 从日志构造时序
4. **参数全部通过 CLI 传入**：`--logstore-project` / `--logstore` / `--log-filter` / `--region`

## 详细说明

### log_request_volume — 日志请求量 ARIMA 预测

- **数据源**：LogStore 中的请求量时序
- **策略**：ARIMA 预测（arima_prediction）
- **SLS SQL**：`ts_predicate_arma(t, cnt, 1, 1, 1, 24, 1)`
- **阈值**：预测值/当前值 > 2 Warning / > 3 Critical
- **构造方式**：
  ```sql
  {filter} | SELECT ts_predicate_arma(t, cnt, 1, 1, 1, 24, 1)
  FROM (SELECT time_series(__time__, '5m', '%Y-%m-%d %H:%i:%s', '0') as t,
               count(*) as cnt FROM log GROUP BY t ORDER BY t)
  WHERE cnt > 0
  ```
- **修复建议**：
  - 评估流量增长是否为正常业务增长
  - 检查是否存在异常重试或循环调用
  - 提前规划扩容（增加实例/节点）
  - 配置限流保护

### log_error_rate — 日志错误率异常检测

- **数据源**：LogStore 中的错误数时序（status >= 400 或 level=ERROR）
- **策略**：分解与异常检测（decomposition_anomaly）
- **SLS SQL**：`ts_decompose(t, cnt)`
- **阈值**：异常比例 > 0.8 Warning / > 0.95 Critical
- **构造方式**：
  ```sql
  {filter} AND (status >= 400 OR level: ERROR) | SELECT ts_decompose(t, cnt)
  FROM (SELECT time_series(__time__, '5m', '%Y-%m-%d %H:%i:%s', '0') as t,
               count(*) as cnt FROM log GROUP BY t ORDER BY t)
  WHERE cnt > 0
  ```
- **修复建议**：
  - 检查错误日志内容定位根因
  - 检查下游依赖服务健康状态
  - 检查最近变更（发布/配置变更）
  - 必要时回滚发布

### log_volume_trend — 日志量趋势分解

- **数据源**：LogStore 中的日志量时序
- **策略**：分解与异常检测（decomposition_anomaly）
- **SLS SQL**：`ts_decompose(t, cnt)`
- **阈值**：残差绝对值超 2 倍标准差 Warning
- **构造方式**：
  ```sql
  {filter} | SELECT ts_decompose(t, cnt)
  FROM (SELECT time_series(__time__, '5m', '%Y-%m-%d %H:%i:%s', '0') as t,
               count(*) as cnt FROM log GROUP BY t ORDER BY t)
  WHERE cnt > 0
  ```
- **修复建议**：
  - 分析日志量突增原因（是否新增日志级别/模块）
  - 检查是否存在日志风暴（循环打印/异常重试）
  - 评估 LogStore 容量是否足够
  - 配置日志采样或过滤

## 参数说明

| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| `--region` | 是 | 阿里云 region | `cn-hangzhou` |
| `--logstore-project` | 是 | SLS Project 名称 | `my-log-project` |
| `--logstore` | 是 | LogStore 名称 | `my-logstore` |
| `--log-filter` | 否 | 日志过滤条件 | `resources.k8s.namespace.name: cms-demo` |
| `--time-range` | 是 | 时间范围 | `last_6h` |

## 注意事项

- `{filter}` 占位符在运行时替换为 `--log-filter` 参数值，未传入时默认 `*`
- `time_series` 函数的分桶间隔（5m）可根据时间范围调整
- ARIMA 预测需要至少 30 个数据点（5m 粒度 = 至少 2.5 小时数据）
- ts_decompose 需要至少 2 个完整周期才能检测季节性
- 日志过滤条件使用 SLS 查询语法（非 SQL），如 `level: ERROR` 或 `status >= 400`
