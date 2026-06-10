# acs 基础资源巡检项清单

## 巡检项总览

| case_id | 指标 | 策略 | Warning | Critical | 级别 |
|---|---|---|---|---|---|
| ecs_cpu_trend | AliyunEcs_CPUUtilization | 趋势预测 | 85% | 95% | P1 |
| ecs_disk_trend | AliyunEcs_diskusage_utilization | 缓慢增长 | 80% | 90% | P1 |
| ecs_memory_trend | AliyunEcs_memory_usedutilization | 趋势预测 | 85% | 95% | P2 |
| rds_cpu_trend | AliyunRds_CpuUsage | 趋势预测 | 70% | 85% | P1 |
| rds_conn_trend | AliyunRds_ConnectionUsage | 趋势预测 | 70% | 85% | P2 |
| redis_memory_trend | AliyunKvstore_StandardMemoryUsage | 缓慢增长 | 75% | 90% | P1 |

## 详细说明

### ecs_cpu_trend — ECS CPU 趋势预测

- **指标**：`AliyunEcs_CPUUtilization`
- **策略**：趋势预测（trend_prediction）
- **阈值**：Warning 85% / Critical 95%
- **PromQL**：
  - 当前值：`avg by (instance_id) (AliyunEcs_CPUUtilization)`
  - 变化率：`avg by (instance_id) (deriv(AliyunEcs_CPUUtilization[6h]))`
  - 预测值：`avg by (instance_id) (predict_linear(AliyunEcs_CPUUtilization[6h], 86400))`
- **修复建议**：
  - 升级 ECS 规格或增加实例数
  - 优化应用代码降低 CPU 消耗
  - 检查是否存在异常进程

### ecs_disk_trend — ECS 磁盘缓慢增长

- **指标**：`AliyunEcs_diskusage_utilization`
- **策略**：缓慢增长（slow_growth）
- **阈值**：Warning 80% / Critical 90%
- **PromQL**：
  - 7 天预测：`avg by (instance_id) (predict_linear(AliyunEcs_diskusage_utilization[6h], 604800))`
  - 7 天均值：`avg by (instance_id) (avg_over_time(AliyunEcs_diskusage_utilization[7d]))`
- **修复建议**：
  - 清理日志文件和临时文件
  - 扩容磁盘或挂载新数据盘
  - 配置日志轮转和自动清理

### ecs_memory_trend — ECS 内存趋势预测

- **指标**：`AliyunEcs_memory_usedutilization`
- **策略**：趋势预测（trend_prediction）
- **阈值**：Warning 85% / Critical 95%
- **修复建议**：
  - 升级内存规格
  - 排查内存泄漏
  - 优化 JVM 堆内存配置

### rds_cpu_trend — RDS CPU 趋势预测

- **指标**：`AliyunRds_CpuUsage`
- **策略**：趋势预测（trend_prediction）
- **阈值**：Warning 70% / Critical 85%
- **修复建议**：
  - 升级 RDS 规格
  - 优化慢查询 SQL
  - 增加只读实例分担读压力

### rds_conn_trend — RDS 连接数趋势预测

- **指标**：`AliyunRds_ConnectionUsage`
- **策略**：趋势预测（trend_prediction）
- **阈值**：Warning 70% / Critical 85%
- **修复建议**：
  - 升级 RDS 规格（连接数上限与规格相关）
  - 优化连接池配置
  - 排查连接泄漏

### redis_memory_trend — Redis 内存缓慢增长

- **指标**：`AliyunKvstore_StandardMemoryUsage`
- **策略**：缓慢增长（slow_growth）
- **阈值**：Warning 75% / Critical 90%
- **PromQL**：
  - 7 天预测：`avg by (instance_id) (predict_linear(AliyunKvstore_StandardMemoryUsage[6h], 604800))`
- **修复建议**：
  - 清理过期 Key（配置 TTL）
  - 升级 Redis 规格
  - 检查是否存在大 Key
