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

## investigation_hints 详细说明

### rds_cpu_high — CPU 使用率过高

**排查方向**：
- 检查是否存在慢查询或全表扫描，通过 `SHOW PROCESSLIST` 查看当前活跃查询
- 检查是否存在锁等待导致的 CPU 空转，关联巡检项 `rds_lock_waits`
- 检查是否存在突发流量，关联巡检项 `rds_qps_spike`
- 检查缓冲池命中率是否过低导致频繁磁盘 IO 间接影响 CPU，关联巡检项 `rds_buffer_hit_ratio_low`

**关联指标**：
- `rds_slow_queries`：慢查询数量
- `rds_lock_waits`：锁等待数量
- `rds_qps_spike`：QPS 突增
- `rds_buffer_hit_ratio_low`：缓冲池命中率

**建议操作**：
1. 分析慢查询日志，优化执行计划
2. 检查是否存在缺失索引
3. 考虑启用读写分离分散读负载
4. 如持续高位，考虑升配 CPU 规格

### rds_memory_high — 内存使用率过高

**排查方向**：
- 检查缓冲池配置是否过大，关联巡检项 `rds_buffer_hit_ratio_low`
- 检查是否存在内存泄漏的查询（如大量临时表），关联巡检项 `rds_temp_tables_high`
- 检查连接数是否异常增长，关联巡检项 `rds_connections_high`

**关联指标**：
- `rds_buffer_hit_ratio_low`：缓冲池命中率
- `rds_temp_tables_high`：临时表占比
- `rds_connections_high`：连接数

**建议操作**：
1. 调整 `innodb_buffer_pool_size` 参数
2. 优化内存密集型查询（如大结果集、排序操作）
3. 检查应用是否存在连接泄漏
4. 如持续高位，考虑升配内存规格

### rds_disk_high — 磁盘使用率过高

**排查方向**：
- 检查是否存在大量 binlog 或 slow log 未清理
- 检查是否存在大表或历史数据未归档
- 检查临时表空间是否异常增长，关联巡检项 `rds_temp_tables_high`

**关联指标**：
- `rds_temp_tables_high`：临时表占比
- `rds_backup_retention_low`：备份保留天数（影响备份空间）

**建议操作**：
1. 清理过期的 binlog 和慢查询日志
2. 归档或删除历史数据
3. 优化产生大量临时表的查询
4. 如持续高位，考虑扩容磁盘

### rds_iops_high — IOPS 使用率过高

**排查方向**：
- 检查是否存在高频读写 SQL（如批量插入、全表扫描）
- 检查缓冲池命中率是否过低导致频繁磁盘读取，关联巡检项 `rds_buffer_hit_ratio_low`
- 检查是否存在大量临时表写入，关联巡检项 `rds_temp_tables_high`

**关联指标**：
- `rds_buffer_hit_ratio_low`：缓冲池命中率
- `rds_temp_tables_high`：临时表占比
- `rds_slow_queries`：慢查询数量

**建议操作**：
1. 优化高频读写 SQL，减少不必要的磁盘 IO
2. 增加缓冲池大小以提高缓存命中率
3. 考虑引入应用层缓存（如 Redis）减少数据库 IO
4. 如持续高位，考虑升配 IOPS 规格

### rds_connections_high — 连接数过高

**排查方向**：
- 检查应用是否存在连接泄漏（连接未正确释放）
- 检查是否存在突发流量导致连接数激增，关联巡检项 `rds_qps_spike`
- 检查是否未使用连接池导致连接数过多

**关联指标**：
- `rds_qps_spike`：QPS 突增
- `rds_cpu_high`：CPU 使用率（连接数过多可能影响 CPU）

**建议操作**：
1. 检查应用连接池配置，确保连接正确释放
2. 启用或优化连接池（如 HikariCP、Druid）
3. 调整 RDS 最大连接数参数
4. 如持续高位，考虑升配实例规格

### rds_instance_down — 实例状态异常

**排查方向**：
- 检查阿里云控制台实例事件，确认是否为计划内维护或故障
- 检查是否存在资源耗尽（CPU/内存/磁盘/IOPS），关联其他核心巡检项
- 检查是否存在主备切换事件

**关联指标**：
- 所有核心指标（CPU、内存、磁盘、IOPS、连接数）
- `rds_replication_lag`：复制延迟（主备切换可能导致）

**建议操作**：
1. 登录阿里云控制台查看实例状态与事件详情
2. 如为故障，联系阿里云技术支持
3. 如为主备切换，确认应用连接是否自动恢复
4. 检查监控告警是否正常触发

### rds_replication_lag — 复制延迟过高

**排查方向**：
- 检查主实例负载是否过高（CPU/IOPS/连接数），关联核心巡检项
- 检查是否存在大事务导致复制延迟
- 检查主备实例之间的网络延迟

**关联指标**：
- `rds_cpu_high`：主实例 CPU 使用率
- `rds_iops_high`：主实例 IOPS 使用率
- `rds_slow_queries`：慢查询数量（大事务可能导致）

**建议操作**：
1. 降低主实例负载（优化慢查询、减少并发）
2. 优化大事务，拆分为小批量操作
3. 检查主备实例之间的网络状况
4. 如持续高位，考虑升配备实例规格
