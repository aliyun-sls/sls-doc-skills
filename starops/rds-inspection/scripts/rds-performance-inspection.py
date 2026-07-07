#!/usr/bin/env python3
"""
rds-performance-inspection.py - RDS 性能巡检（6 项）

业务脚本：只声明 InspectionCase 配置，零计算逻辑。
所有计算由 rds_inspection_common.py 公共引擎承载。

CloudMonitor 指标名映射：
- MySQL_SlowQueries: 慢查询数量
- MySQL_LockWaits: 锁等待数量
- MySQL_BufferPoolHitRate: 缓冲池命中率 (%)
- MySQL_TempTables: 临时表数量
- MySQL_QPS: 每秒查询数
- MySQL_ResponseTime: 响应时间 (ms)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rds_inspection_common import (
    InspectionCase, Severity, CompareOp, cli_main
)


def build_cases(time_range: str = "") -> list:
    """
    声明 6 个性能巡检项（数据驱动，零计算逻辑）
    """
    return [
        InspectionCase(
            case_id="rds_slow_queries",
            item="RDS 慢查询过多",
            severity=Severity.P2,
            promql='sum by (instance_id) (increase(MySQL_SlowQueries[5m]))',
            cloudmonitor_metric="MySQL_SlowQueries",
            threshold=10.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="5 分钟内慢查询数量 > 10",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "分析慢查询日志，定位 Top SQL",
                "检查是否缺少索引导致全表扫描",
                "检查是否存在锁等待导致的查询阻塞",
                "考虑优化执行计划或添加缺失索引",
            ],
        ),
        InspectionCase(
            case_id="rds_lock_waits",
            item="RDS 锁等待过多",
            severity=Severity.P2,
            promql='avg by (instance_id) (MySQL_LockWaits)',
            cloudmonitor_metric="MySQL_LockWaits",
            threshold=5.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="锁等待数 > 5",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查是否存在长事务未提交",
                "检查事务隔离级别是否过高（如 Serializable）",
                "检查是否存在热点行更新竞争",
                "考虑优化事务粒度或减少锁竞争",
            ],
        ),
        InspectionCase(
            case_id="rds_buffer_hit_ratio_low",
            item="RDS 缓冲池命中率过低",
            severity=Severity.P3,
            promql='avg by (instance_id) (MySQL_BufferPoolHitRate)',
            cloudmonitor_metric="MySQL_BufferPoolHitRate",
            threshold=95.0,
            duration=0,
            compare=CompareOp.LT,
            data_format="percent",
            description="缓冲池命中率 < 95%",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查 innodb_buffer_pool_size 配置是否合理（建议物理内存的 60-70%）",
                "检查是否存在大量冷数据访问模式",
                "检查是否有全表扫描导致缓冲池污染",
                "考虑升配内存以增大缓冲池",
            ],
        ),
        InspectionCase(
            case_id="rds_temp_tables_high",
            item="RDS 临时表占比过高",
            severity=Severity.P3,
            promql='avg by (instance_id) (MySQL_TempTables)',
            cloudmonitor_metric="MySQL_TempTables",
            threshold=20.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="临时表数量 > 20",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查是否存在大量 GROUP BY / ORDER BY 未命中索引",
                "检查是否存在 DISTINCT / UNION 导致的隐式临时表",
                "检查 join 查询是否缺少合适的索引",
                "考虑优化查询逻辑或添加合适索引",
            ],
        ),
        InspectionCase(
            case_id="rds_qps_spike",
            item="RDS QPS 过高",
            severity=Severity.P3,
            promql='sum by (instance_id) (MySQL_QPS)',
            cloudmonitor_metric="MySQL_QPS",
            threshold=1000.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="QPS > 1000",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查是否存在突发流量（如爬虫、缓存失效、批量任务）",
                "检查应用端是否缺少查询缓存",
                "检查是否存在 N+1 查询问题",
                "考虑启用读写分离或增加只读实例",
            ],
        ),
        InspectionCase(
            case_id="rds_latency_high",
            item="RDS 响应延迟过高",
            severity=Severity.P2,
            promql='avg by (instance_id) (MySQL_ResponseTime)',
            cloudmonitor_metric="MySQL_ResponseTime",
            threshold=100.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="ms",
            description="响应延迟 > 100ms",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查慢查询日志，定位高延迟 SQL",
                "检查索引是否缺失或失效",
                "检查网络延迟（应用与 RDS 是否同地域）",
                "检查连接池配置是否合理",
            ],
        ),
    ]


if __name__ == "__main__":
    cases = build_cases()
    cli_main(
        cases=cases,
        description="RDS 性能巡检（6 项）：慢查询、锁等待、缓冲池命中率、临时表、QPS、响应延迟",
        entity_type="RDS",
    )
