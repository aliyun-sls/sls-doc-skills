# RDS 核心指标巡检项清单

## 巡检项清单

| # | case_id | severity | 巡检项 | 阈值 | 持续时间 | PromQL | 修复建议 |
|---|---|---|---|---|---|---|---|
| 1 | rds_cpu_high | P1 | CPU 使用率过高 | > 80% | 5 分钟 | `avg by (instance_id) (rate(rds_cpu_usage_total[3m])) / 100 * 100` | 1. 检查慢查询与锁等待 2. 考虑升配或读写分离 3. 优化高 CPU 消耗 SQL |
| 2 | rds_memory_high | P1 | 内存使用率过高 | > 85% | 5 分钟 | `avg by (instance_id) (rds_memory_usage{unit="percent"})` | 1. 检查缓冲池命中率 2. 优化内存密集型查询 3. 考虑升配内存 |
| 3 | rds_disk_high | P2 | 磁盘使用率过高 | > 80% | 10 分钟 | `avg by (instance_id) (rds_disk_usage{unit="percent"})` | 1. 清理无用数据与日志 2. 归档历史数据 3. 扩容磁盘 |
| 4 | rds_iops_high | P2 | IOPS 使用率过高 | > 80% | 5 分钟 | `avg by (instance_id) (rate(rds_iops_total[3m])) / avg by (instance_id) (rds_iops_max) * 100` | 1. 优化高频读写 SQL 2. 增加缓存层 3. 升配 IOPS |
| 5 | rds_connections_high | P2 | 连接数过高 | > 80% | 5 分钟 | `avg by (instance_id) (rds_active_connections) / avg by (instance_id) (rds_max_connections) * 100` | 1. 检查连接泄漏 2. 启用连接池 3. 增加最大连接数 |
| 6 | rds_instance_down | P1 | 实例状态异常 | 状态 != running | 瞬时 | `rds_instance_status{status!="running"}` | 1. 检查实例状态与事件 2. 联系阿里云支持 3. 切换备实例 |
| 7 | rds_replication_lag | P2 | 复制延迟过高 | > 10s | 5 分钟 | `avg by (instance_id) (rds_replication_lag_seconds)` | 1. 检查主实例负载 2. 优化大事务 3. 检查网络延迟 |
