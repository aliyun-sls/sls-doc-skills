#!/usr/bin/env python3
"""
rds-performance-inspection.py - RDS 性能巡检（6 项）

业务脚本：只声明 InspectionCase 配置，零计算逻辑。
所有计算由 rds_inspection_common.py 公共引擎承载。
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
            promql='sum by (instance_id) (increase(rds_slow_queries_total[5m]))',
            threshold=10.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="5 分钟内慢查询数量 > 10",
            entity_label="instance_id",
            name_label="instance_id",
        ),
        InspectionCase(
            case_id="rds_lock_waits",
            item="RDS 锁等待过多",
            severity=Severity.P2,
            promql='avg by (instance_id) (rds_lock_waits)',
            threshold=5.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="锁等待数 > 5",
            entity_label="instance_id",
            name_label="instance_id",
        ),
        InspectionCase(
            case_id="rds_buffer_hit_ratio_low",
            item="RDS 缓冲池命中率过低",
            severity=Severity.P3,
            promql='avg by (instance_id) (rds_buffer_pool_hit_ratio{unit="percent"})',
            threshold=95.0,
            duration=0,
            compare=CompareOp.LT,
            data_format="percent",
            description="缓冲池命中率 < 95%",
            entity_label="instance_id",
            name_label="instance_id",
        ),
        InspectionCase(
            case_id="rds_temp_tables_high",
            item="RDS 临时表占比过高",
            severity=Severity.P3,
            promql='avg by (instance_id) (rds_temp_tables_ratio{unit="percent"})',
            threshold=20.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="percent",
            description="临时表占比 > 20%",
            entity_label="instance_id",
            name_label="instance_id",
        ),
        InspectionCase(
            case_id="rds_qps_spike",
            item="RDS QPS 过高",
            severity=Severity.P3,
            promql='sum by (instance_id) (rate(rds_queries_total[3m]))',
            threshold=1000.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="QPS > 1000",
            entity_label="instance_id",
            name_label="instance_id",
        ),
        InspectionCase(
            case_id="rds_latency_high",
            item="RDS 响应延迟过高",
            severity=Severity.P2,
            promql='avg by (instance_id) (rds_response_latency_ms)',
            threshold=100.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="ms",
            description="响应延迟 > 100ms",
            entity_label="instance_id",
            name_label="instance_id",
        ),
    ]


def extract_key(labels: dict) -> str:
    """从 labels 中提取 entity_id"""
    return labels.get("instance_id", "unknown")


if __name__ == "__main__":
    cases = build_cases()
    cli_main(
        cases=cases,
        description="RDS 性能巡检（6 项）：慢查询、锁等待、缓冲池命中率、临时表占比、QPS、响应延迟",
        entity_type="RDS",
    )
