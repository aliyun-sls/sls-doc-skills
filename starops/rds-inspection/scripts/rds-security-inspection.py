#!/usr/bin/env python3
"""
rds-security-inspection.py - RDS 安全巡检（6 项）

业务脚本：只声明 InspectionCase 配置，零计算逻辑。
所有计算由 rds_inspection_common.py 公共引擎承载。

CloudMonitor 指标名映射：
- SSLEnabled: SSL 启用状态 (0=未启用, 1=已启用)
- PublicAccessEnabled: 公网访问状态 (0=未启用, 1=已启用)
- BackupStatus: 备份状态 (0=成功, 1=失败)
- BackupRetentionDays: 备份保留天数
- AuditLogEnabled: 审计日志启用状态 (0=未启用, 1=已启用)
- HighPrivilegeAccounts: 高权限账号数量
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
            promql='SSLEnabled == 0',
            cloudmonitor_metric="SSLEnabled",
            threshold=0.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="SSL 未启用（SSLEnabled == 0）",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查应用连接字符串是否使用 SSL/TLS 加密",
                "检查是否因性能考虑而禁用了 SSL",
                "评估数据传输的安全合规要求",
                "启用 SSL/TLS 并更新应用连接配置",
            ],
        ),
        InspectionCase(
            case_id="rds_public_access",
            item="RDS 公网访问开启",
            severity=Severity.P1,
            promql='PublicAccessEnabled == 1',
            cloudmonitor_metric="PublicAccessEnabled",
            threshold=0.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="公网访问已开启（安全风险）",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查是否确实需要公网访问（如外部应用对接）",
                "检查白名单配置是否限制了来源 IP",
                "评估是否可改为 VPC 内网连接",
                "关闭公网访问并使用 VPN 或专线访问",
            ],
        ),
        InspectionCase(
            case_id="rds_backup_failed",
            item="RDS 备份失败",
            severity=Severity.P1,
            promql='BackupStatus{status="failed"}',
            cloudmonitor_metric="BackupStatus",
            threshold=0.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="最近备份任务失败",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查备份任务日志，定位失败原因",
                "检查存储空间是否充足",
                "检查是否存在锁表或长事务阻塞备份",
                "重新执行备份并验证备份可恢复性",
            ],
        ),
        InspectionCase(
            case_id="rds_backup_retention_low",
            item="RDS 备份保留天数不足",
            severity=Severity.P3,
            promql='BackupRetentionDays',
            cloudmonitor_metric="BackupRetentionDays",
            threshold=7.0,
            duration=0,
            compare=CompareOp.LT,
            data_format="raw",
            description="备份保留天数 < 7 天",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查备份保留策略配置",
                "评估数据恢复的时间窗口需求",
                "检查是否配置了跨区域备份",
                "增加备份保留天数至 ≥7 天",
            ],
        ),
        InspectionCase(
            case_id="rds_audit_log_disabled",
            item="RDS 审计日志未启用",
            severity=Severity.P2,
            promql='AuditLogEnabled == 0',
            cloudmonitor_metric="AuditLogEnabled",
            threshold=0.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="审计日志未启用",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查是否因性能或成本考虑而未启用审计日志",
                "评估安全合规要求（如等保、SOX 等）",
                "检查审计日志存储配置与保留策略",
                "启用 SQL 审计日志并配置日志分析",
            ],
        ),
        InspectionCase(
            case_id="rds_high_privilege_accounts",
            item="RDS 存在高权限账号",
            severity=Severity.P2,
            promql='HighPrivilegeAccounts > 0',
            cloudmonitor_metric="HighPrivilegeAccounts",
            threshold=0.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="存在高权限数据库账号（非只读/低权限）",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "审查高权限账号列表，确认是否为必要账号",
                "检查是否遵循最小权限原则",
                "检查是否存在共享账号或默认账号未修改",
                "禁用或删除不必要的高权限账号，创建细粒度权限账号",
            ],
        ),
    ]


if __name__ == "__main__":
    cases = build_cases()
    cli_main(
        cases=cases,
        description="RDS 安全巡检（6 项）：SSL、公网访问、备份失败、备份保留天数、审计日志、高权限账号",
        entity_type="RDS",
    )
