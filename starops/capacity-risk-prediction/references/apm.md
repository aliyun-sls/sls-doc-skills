# APM 业务服务巡检项清单

## 巡检项总览

| case_id | 指标 | 策略 | Warning | Critical | 级别 |
|---|---|---|---|---|---|
| service_error_rate | error_rate | 阈值突破 | 5% | 10% | P1 |
| service_latency | avg_request_latency_seconds | 阈值突破 + 趋势 | 200ms | 500ms | P1 |
| service_qps_spike | request_count | 基线偏离 | 日环比 > 2x | 日环比 > 3x | P2 |

## APM 域特殊实现

APM 域与 acs/k8s 域的关键区别：

1. **不使用 PromQL 函数**：APM 预聚合指标不支持 `deriv()` / `predict_linear()` 等 PromQL 函数
2. **使用 `starops observe metric_set query`**：获取指标摘要数据（mean/max/min）
3. **从 `__summary__.cur_statistics` 提取**：mean_value / max_value 用于趋势和阈值判断
4. **错误率使用预计算指标**：直接使用 `error_rate` 指标，不用 error_count/request_count 手动计算

## 详细说明

### service_error_rate — 服务错误率阈值突破

- **指标**：`error_rate`（预计算百分比指标）
- **策略**：阈值突破（threshold_breach）
- **阈值**：Warning 5% / Critical 10%
- **数据来源**：`starops observe metric_set query`
  - metric_set_domain: `apm`
  - metric_set_name: `apm.metric.apm.service`
  - metric_names: `error_rate`
- **修复建议**：
  - 检查错误日志定位根因
  - 检查下游依赖服务健康状态
  - 检查最近变更（发布/配置变更）
  - 必要时回滚发布

### service_latency — 服务延迟阈值突破 + 趋势

- **指标**：`avg_request_latency_seconds`（转换为毫秒）
- **策略**：阈值突破（threshold_breach）+ 趋势预测
- **阈值**：Warning 200ms / Critical 500ms
- **数据来源**：`starops observe metric_set query`
  - metric_set_domain: `apm`
  - metric_set_name: `apm.metric.apm.service`
  - metric_names: `avg_request_latency_seconds`
- **修复建议**：
  - 分析慢 Trace 定位瓶颈 Span
  - 检查数据库慢查询
  - 检查下游服务延迟
  - 优化代码热点（Profile 分析）
  - 考虑增加缓存

### service_qps_spike — 服务 QPS 基线偏离

- **指标**：`request_count`
- **策略**：基线偏离（baseline_deviation）
- **阈值**：日环比 > 2x Warning / > 3x Critical
- **数据来源**：`starops observe metric_set query`
  - metric_set_domain: `apm`
  - metric_set_name: `apm.metric.apm.service`
  - metric_names: `request_count`
- **修复建议**：
  - 确认是否为正常流量增长（营销活动/新功能上线）
  - 检查是否存在异常重试或循环调用
  - 评估当前容量是否足够
  - 必要时触发限流保护

## 注意事项

- APM 指标摘要通过 `metric_set query` 获取，非 PromQL
- 使用 `__summary__.cur_statistics` 中的 mean_value / max_value
- 错误率直接使用预计算的 `error_rate` 指标，避免手动计算产生荒谬值
- 延迟指标需注意单位转换（秒 → 毫秒）
