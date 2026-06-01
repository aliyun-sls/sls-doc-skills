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
