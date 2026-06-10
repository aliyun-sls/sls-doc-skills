# k8s 集群资源巡检项清单

## 巡检项总览

| case_id | 指标 | 策略 | Warning | Critical | 级别 |
|---|---|---|---|---|---|
| node_cpu_trend | node_cpu_seconds_total | 趋势预测 + 基线偏离 | 70% | 85% | P1 |
| node_memory_trend | node_memory_MemAvailable_bytes | 趋势预测 | 80% | 90% | P1 |
| pod_memory_trend | container_memory_working_set_bytes | 缓慢增长 | 80% | 95% | P2 |

## 详细说明

### node_cpu_trend — Node CPU 趋势预测 + 基线偏离

- **指标**：`node_cpu_seconds_total`（通过 idle mode 计算使用率）
- **策略**：趋势预测（trend_prediction）+ 基线偏离检测
- **阈值**：Warning 70% / Critical 85%
- **PromQL**：
  - 当前值：`100 - (avg by (node) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)`
  - 变化率：`avg by (node) (deriv(...[6h]))`
  - 预测值：`avg by (node) (predict_linear(...[6h], 86400))`
  - 昨日同期：`... offset 1d`
- **修复建议**：
  - 增加 Node 节点（扩容节点池）
  - 优化 Pod 资源请求和限制
  - 检查是否存在 CPU 密集型 Pod
  - 配置 HPA 自动扩缩容

### node_memory_trend — Node 内存趋势预测

- **指标**：`node_memory_MemAvailable_bytes` / `node_memory_MemTotal_bytes`
- **策略**：趋势预测（trend_prediction）
- **阈值**：Warning 80% / Critical 90%（使用率百分比）
- **PromQL**：
  - 当前值：`(1 - avg by (node) (node_memory_MemAvailable_bytes) / avg by (node) (node_memory_MemTotal_bytes)) * 100`
  - 变化率：`avg by (node) (deriv(...[6h])) * 100`
  - 预测值：`avg by (node) (predict_linear(...[6h], 86400)) * 100`
- **修复建议**：
  - 增加 Node 内存或添加新节点
  - 检查 Pod 内存限制是否合理
  - 排查内存泄漏的 Pod
  - 配置 VPA 垂直自动扩缩容

### pod_memory_trend — Pod 内存缓慢增长

- **指标**：`container_memory_working_set_bytes` / `kube_pod_container_resource_limits_memory_bytes`
- **策略**：缓慢增长（slow_growth）
- **阈值**：Warning 80% / Critical 95%（使用率百分比）
- **PromQL**：
  - 当前值：`avg by (namespace, pod) (container_memory_working_set_bytes{container!="",container!="POD"}) / avg by (namespace, pod) (kube_pod_container_resource_limits_memory_bytes{container!="",container!="POD"}) * 100`
  - 7 天预测：`predict_linear(...[6h], 604800)`
  - 7 天均值：`avg_over_time(...[7d])`
- **修复建议**：
  - 增加 Pod 内存 limit
  - 排查应用内存泄漏
  - 优化 JVM 堆内存配置（-Xmx）
  - 考虑使用 Sidecar 分担内存压力

## 注意事项

- cAdvisor 指标需排除 `container=""` 和 `container="POD"` 避免重复计数
- 内存使用量使用 `working_set_bytes`（排除可回收缓存）
- Node 级别指标按 `node` 标签分组
- Pod 级别指标按 `namespace, pod` 标签分组
