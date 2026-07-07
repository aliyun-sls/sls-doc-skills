#!/usr/bin/env python3
"""
rds-logs-inspection.py - RDS 关联日志巡检（2 项）

业务脚本：只声明 InspectionCase 配置，零计算逻辑。
所有计算由 rds_inspection_common.py 公共引擎承载。

数据来源：关联的审计 / 错误日志 Logstore
必须传入 --audit-logstore 参数。

日志查询使用 SLS SQL 语法，通过公共引擎的 run_log_query 执行。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rds_inspection_common import (
    InspectionCase, Severity, CompareOp, cli_main
)


def build_cases(time_range: str = "") -> list:
    """
    声明 2 个关联日志巡检项（数据驱动，零计算逻辑）

    日志查询使用 SLS SQL 语法，通过公共引擎的 run_log_query 执行。
    """
    return [
        InspectionCase(
            case_id="rds_slow_sql_high",
            item="RDS 慢 SQL 数量过高",
            severity=Severity.P2,
            log_query='* and "execute_time" and "execute_time" > "1s" | select count(*) as cnt',
            log_project="",
            logstore="",
            threshold=10.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="5 分钟内慢 SQL 数量 > 10（来源：审计日志，关键字 execute_time > 1s）",
            entity_label="instance_id",
            name_label="instance_id",
            log_source="审计日志",
            investigation_hints=[
                "分析慢 SQL 执行计划，定位性能瓶颈",
                "检查是否缺少索引导致全表扫描",
                "检查是否存在锁等待导致的查询阻塞",
                "考虑优化查询逻辑或添加缺失索引",
                "评估是否需要 SQL 限流或降级策略",
            ],
        ),
        InspectionCase(
            case_id="rds_error_log_high",
            item="RDS ERROR 级别日志过多",
            severity=Severity.P2,
            log_query='"ERROR" | select count(*) as cnt',
            log_project="",
            logstore="",
            threshold=10.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="5 分钟内 ERROR 级别日志 > 10（来源：错误日志，level=ERROR）",
            entity_label="instance_id",
            name_label="instance_id",
            log_source="错误日志",
            investigation_hints=[
                "查看 ERROR 日志详情，定位错误类型（连接超时、权限、语法等）",
                "检查是否存在批量错误（如连接池耗尽、磁盘满等）",
                "检查应用端是否存在异常调用模式",
                "修复应用或配置问题",
                "评估是否需要告警联动",
            ],
        ),
    ]


if __name__ == "__main__":
    cases = build_cases()
    cli_main(
        cases=cases,
        description="RDS 关联日志巡检（2 项）：慢 SQL、ERROR 日志（需 --audit-logstore）",
        entity_type="RDS",
    )
