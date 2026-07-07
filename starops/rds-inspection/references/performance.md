# RDS 性能巡检项清单

## 巡检项清单

| # | case_id | severity | 巡检项 | 阈值 | 持续时间 | PromQL | 修复建议 |
|---|---|---|---|---|---|---|---|
| 1 | rds_slow_queries | P2 | 慢查询过多 | > 10 / 5min | 瞬时 | `sum by (instance_id) (increase(rds_slow_queries_total[5m]))` | 1. 分析慢查询日志 2. 优化执行计划 3. 添加缺失索引 |
| 2 | rds_lock_waits | P2 | 锁等待过多 | > 5 | 瞬时 | `avg by (instance_id) (rds_lock_waits)` | 1. 检查长事务 2. 优化事务隔离级别 3. 减少锁竞争 |
| 3 | rds_buffer_hit_ratio_low | P3 | 缓冲池命中率过低 | < 95% | 瞬时 | `avg by (instance_id) (rds_buffer_pool_hit_ratio{unit="percent"})` | 1. 增加 innodb_buffer_pool_size 2. 优化热数据访问模式 3. 考虑升配内存 |
| 4 | rds_temp_tables_high | P3 | 临时表占比过高 | > 20% | 瞬时 | `avg by (instance_id) (rds_temp_tables_ratio{unit="percent"})` | 1. 优化 GROUP BY / ORDER BY 查询 2. 添加合适索引 3. 避免隐式临时表 |
| 5 | rds_qps_spike | P3 | QPS 过高 | > 1000 | 瞬时 | `sum by (instance_id) (rate(rds_queries_total[3m]))` | 1. 检查突发流量来源 2. 启用查询缓存 3. 考虑读写分离 |
| 6 | rds_latency_high | P2 | 响应延迟过高 | > 100ms | 瞬时 | `avg by (instance_id) (rds_response_latency_ms)` | 1. 检查慢查询 2. 优化索引 3. 检查网络延迟与连接池 |

## 修复建议详细说明

### rds_slow_queries — 慢查询过多

**问题描述**：5 分钟内慢查询数量超过 10 条，表明存在性能不佳的 SQL 语句。

**排查步骤**：
1. 查看慢查询日志，定位 Top N 耗时 SQL
2. 使用 `EXPLAIN` 分析执行计划，检查是否存在全表扫描
3. 检查是否缺少必要的索引
4. 检查是否存在锁等待导致的查询阻塞

**修复建议**：
1. 为高频查询添加合适的索引
2. 优化查询逻辑（如避免 `SELECT *`、减少子查询嵌套）
3. 对大表查询添加分页或限制条件
4. 考虑使用查询缓存或应用层缓存

### rds_lock_waits — 锁等待过多

**问题描述**：当前锁等待数量超过 5，表明存在锁竞争问题。

**排查步骤**：
1. 使用 `SHOW ENGINE INNODB STATUS` 查看锁等待详情
2. 检查是否存在长事务持有锁未释放
3. 检查事务隔离级别是否过高

**修复建议**：
1. 优化长事务，缩短事务持有时间
2. 降低事务隔离级别（如从 `SERIALIZABLE` 降到 `REPEATABLE READ`）
3. 减少单次事务操作的数据量
4. 考虑使用乐观锁替代悲观锁

### rds_buffer_hit_ratio_low — 缓冲池命中率过低

**问题描述**：缓冲池命中率低于 95%，表明大量数据读取需要访问磁盘。

**排查步骤**：
1. 检查 `innodb_buffer_pool_size` 配置是否合理
2. 检查是否存在大量全表扫描导致缓冲池污染
3. 检查热数据访问模式是否合理

**修复建议**：
1. 增加 `innodb_buffer_pool_size`（建议设置为物理内存的 60-70%）
2. 优化全表扫描查询，添加合适的索引
3. 考虑使用 `innodb_buffer_pool_dump/load` 保持热数据
4. 如内存不足，考虑升配实例规格

### rds_temp_tables_high — 临时表占比过高

**问题描述**：临时表占比超过 20%，表明大量查询需要创建临时表。

**排查步骤**：
1. 检查是否存在大量 `GROUP BY`、`ORDER BY`、`DISTINCT` 操作
2. 检查是否存在隐式临时表（如排序操作超出内存限制）
3. 检查 `tmp_table_size` 和 `max_heap_table_size` 配置

**修复建议**：
1. 优化 `GROUP BY` / `ORDER BY` 查询，添加合适的索引
2. 避免在查询中使用大结果集排序
3. 增加 `tmp_table_size` 和 `max_heap_table_size` 参数
4. 考虑将复杂的临时表操作拆分为多步查询

### rds_qps_spike — QPS 过高

**问题描述**：QPS 超过 1000，可能存在突发流量或查询效率低下。

**排查步骤**：
1. 检查是否存在突发流量来源（如爬虫、批量任务）
2. 检查是否存在低效查询导致 QPS 虚高
3. 检查是否未使用缓存导致所有请求直达数据库

**修复建议**：
1. 定位突发流量来源并限流
2. 启用查询缓存或应用层缓存（如 Redis）
3. 考虑使用读写分离分散读负载
4. 优化低效查询，减少数据库访问次数

### rds_latency_high — 响应延迟过高

**问题描述**：平均响应延迟超过 100ms，影响应用用户体验。

**排查步骤**：
1. 检查是否存在慢查询，关联巡检项 `rds_slow_queries`
2. 检查是否存在锁等待，关联巡检项 `rds_lock_waits`
3. 检查网络延迟是否正常
4. 检查连接池配置是否合理

**修复建议**：
1. 优化慢查询，添加合适的索引
2. 减少锁等待时间
3. 检查应用与数据库之间的网络状况
4. 优化连接池配置（如最大连接数、超时时间）
