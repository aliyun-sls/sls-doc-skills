#!/usr/bin/env python3
"""
rds-core-inspection.py - RDS 核心指标巡检（7 项）

业务脚本：只声明 InspectionCase 配置，零计算逻辑。
所有计算由 rds_inspection_common.py 公共引擎承载。
"""

import sys
import os

# 确保能导入同目录下的公共模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rds_inspection_common import (
    InspectionCase, Severity, CompareOp, cli_main
)


def build_cases(time_range: str = "") -> list:
    """
    声明 7 个核心指标巡检项（数据驱动，零计算逻辑）

    新增巡检项 = 新增一个 InspectionCase 数据项，不需要写新的计算代码。
    """
    return [
        InspectionCase(
            case_id="rds_cpu_high",
            item="RDS CPU 使用率过高",
            severity=Severity.P1,
            promql='avg by (instance_id) (rate(rds_cpu_usage_total[3m])) / 100 * 100',
            threshold=80.0,
            duration=300,
            compare=CompareOp.GT,
            data_format="percent",
            description="CPU 使用率 > 80%，持续 5 分钟",
            entity_label="instance_id",
            name_label="instance_id",
        ),
        InspectionCase(
            case_id="rds_memory_high",
            item="RDS 内存使用率过高",
            severity=Severity.P1,
            promql='avg by (instance_id) (rds_memory_usage{unit="percent"})',
            threshold=85.0,
            duration=300,
            compare=CompareOp.GT,
            data_format="percent",
            description="内存使用率 > 85%，持续 5 分钟",
            entity_label="instance_id",
            name_label="instance_id",
        ),
        InspectionCase(
            case_id="rds_disk_high",
            item="RDS 磁盘使用率过高",
            severity=Severity.P2,
            promql='avg by (instance_id) (rds_disk_usage{unit="percent"})',
            threshold=80.0,
            duration=600,
            compare=CompareOp.GT,
            data_format="percent",
            description="磁盘使用率 > 80%，持续 10 分钟",
            entity_label="instance_id",
            name_label="instance_id",
        ),
        InspectionCase(
            case_id="rds_iops_high",
            item="RDS IOPS 使用率过高",
            severity=Severity.P2,
            promql='avg by (instance_id) (rate(rds_iops_total[3m])) / avg by (instance_id) (rds_iops_max) * 100',
            threshold=80.0,
            duration=300,
            compare=CompareOp.GT,
            data_format="percent",
            description="IOPS 使用率 > 80%，持续 5 分钟",
            entity_label="instance_id",
            name_label="instance_id",
        ),
        InspectionCase(
            case_id="rds_connections_high",
            item="RDS 连接数过高",
            severity=Severity.P2,
            promql='avg by (instance_id) (rds_active_connections) / avg by (instance_id) (rds_max_connections) * 100',
            threshold=80.0,
            duration=300,
            compare=CompareOp.GT,
            data_format="percent",
            description="连接数 > 80% 最大连接数，持续 5 分钟",
            entity_label="instance_id",
            name_label="instance_id",
        ),
        InspectionCase(
            case_id="rds_instance_down",
            item="RDS 实例状态异常",
            severity=Severity.P1,
            promql='rds_instance_status{status!="running"}',
            threshold=0.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="实例状态非 running",
            entity_label="instance_id",
            name_label="instance_id",
        ),
        InspectionCase(
            case_id="rds_replication_lag",
            item="RDS 复制延迟过高",
            severity=Severity.P2,
            promql='avg by (instance_id) (rds_replication_lag_seconds)',
            threshold=10.0,
            duration=300,
            compare=CompareOp.GT,
            data_format="s",
            description="主从复制延迟 > 10s，持续 5 分钟",
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
        description="RDS 核心指标巡检（7 项）：CPU、内存、磁盘、IOPS、连接数、实例状态、复制延迟",
        entity_type="RDS",
    )
