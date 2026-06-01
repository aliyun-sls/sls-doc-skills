#!/usr/bin/env python3
"""
rds-security-inspection.py - RDS 安全巡检（6 项）

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
    声明 6 个安全巡检项（数据驱动，零计算逻辑）
    """
    return [
        InspectionCase(
            case_id="rds_ssl_disabled",
            item="RDS SSL 未启用",
            severity=Severity.P2,
            promql='rds_ssl_enabled == 0',
            threshold=0.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="SSL 未启用（rds_ssl_enabled == 0）",
            entity_label="instance_id",
            name_label="instance_id",
        ),
        InspectionCase(
            case_id="rds_public_access",
            item="RDS 公网访问开启",
            severity=Severity.P1,
            promql='rds_public_access_enabled == 1',
            threshold=0.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="公网访问已开启（安全风险）",
            entity_label="instance_id",
            name_label="instance_id",
        ),
        InspectionCase(
            case_id="rds_backup_failed",
            item="RDS 备份失败",
            severity=Severity.P1,
            promql='rds_backup_status{status="failed"}',
            threshold=0.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="最近备份任务失败",
            entity_label="instance_id",
            name_label="instance_id",
        ),
        InspectionCase(
            case_id="rds_backup_retention_low",
            item="RDS 备份保留天数不足",
            severity=Severity.P3,
            promql='rds_backup_retention_days',
            threshold=7.0,
            duration=0,
            compare=CompareOp.LT,
            data_format="raw",
            description="备份保留天数 < 7 天",
            entity_label="instance_id",
            name_label="instance_id",
        ),
        InspectionCase(
            case_id="rds_audit_log_disabled",
            item="RDS 审计日志未启用",
            severity=Severity.P2,
            promql='rds_audit_log_enabled == 0',
            threshold=0.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="审计日志未启用",
            entity_label="instance_id",
            name_label="instance_id",
        ),
        InspectionCase(
            case_id="rds_high_privilege_accounts",
            item="RDS 存在高权限账号",
            severity=Severity.P2,
            promql='rds_high_privilege_accounts > 0',
            threshold=0.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="存在高权限数据库账号（非只读/低权限）",
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
        description="RDS 安全巡检（6 项）：SSL、公网访问、备份失败、备份保留天数、审计日志、高权限账号",
        entity_type="RDS",
    )
