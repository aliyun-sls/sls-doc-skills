# 长周期趋势检测项清单

本文件描述当前 `rds-trend-inspection.py` 已实现的回看型趋势检测。它只根据历史窗口内的样本计算增长率和数据完整性，不输出未来到达阈值时间，不承担容量预测。

## 巡检项列表

| case_id | severity | 描述 | 窗口 | 输出字段 |
|---------|----------|------|------|----------|
| rds_disk_trend | P2 | 磁盘使用率周增长率异常 | 7d | trend_direction, growth_rate, start_value, end_value, data_points, completeness |
| rds_iops_trend | P2 | IOPS 使用率周增长率异常 | 7d | trend_direction, growth_rate, start_value, end_value, data_points, completeness |
| rds_cpu_trend | P3 | CPU 使用率周增长率异常 | 7d | trend_direction, growth_rate, start_value, end_value, data_points, completeness |
| rds_memory_trend | P3 | 内存使用率周增长率异常 | 7d | trend_direction, growth_rate, start_value, end_value, data_points, completeness |
| rds_connections_trend | P3 | 连接数使用率周增长率异常 | 7d | trend_direction, growth_rate, start_value, end_value, data_points, completeness |
| rds_slow_sql_trend | P3 | 慢查询数量周增长率异常 | 7d | trend_direction, growth_rate, start_value, end_value, data_points, completeness |

## 趋势判断方式

六个趋势项使用同一类判断：

1. 查询历史窗口内的时序样本。
2. 按实例聚合起始值、结束值和样本数。
3. 计算 `growth_rate = (end_value - start_value) / start_value * 100`。
4. 当 `growth_rate > 10%` 时标记为 `find_problem`。
5. 样本不足或数据源不可用时返回结构化 `error`，不静默返回 `pass`。

当前实现不输出未来到阈值时间、日均增长预测、SQL digest 变化归因等字段。这些内容属于旧 replay prompt 的未落地目标，不能作为当前 Skill 的已发布能力描述。

## 输出字段说明

- `trend_direction`：`increasing` / `stable` / `decreasing`
- `growth_rate`：窗口内增长率百分比
- `start_value`：窗口起始值
- `end_value`：窗口结束值
- `data_points`：参与判断的数据点数量
- `completeness`：样本完整性，通常为 `high` / `medium` / `low`

## 数据完整性要求

趋势检测依赖连续历史样本。数据不足时：

- `status=error`
- `error` 字段说明具体原因
- 不构造未来预测结论

## investigation_hints 示例

趋势检测只提示下一步调查方向，不代替证据判断。脚本实际输出的 hints 为中文自然语言提示，以下为各趋势项的调查方向示意：

- `rds_disk_trend`：检查空间构成、关联写入 QPS
- `rds_iops_trend`：检查高频 IO 的 SQL、慢日志 digest
- `rds_cpu_trend`：检查高 CPU 的 SQL、最近发布变更
- `rds_memory_trend`：检查缓冲池配置、连接增长
- `rds_connections_trend`：检查连接来源、连接池配置
- `rds_slow_sql_trend`：检查慢 SQL digest、新增 SQL 模式
