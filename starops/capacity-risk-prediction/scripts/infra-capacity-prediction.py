#!/usr/bin/env python3
"""
infra-capacity-prediction.py - acs 基础资源容量风险预测（6 项）

业务脚本：只声明 PredictionCase 配置，零计算逻辑。
所有计算由 capacity_prediction_common.py 公共引擎承载。

覆盖：ECS CPU / 磁盘 / 内存、RDS CPU / 连接数、Redis 内存
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from capacity_prediction_common import (
    PredictionCase, Severity, Strategy, cli_main
)


def build_cases(time_range: str = "") -> list:
    """
    声明 6 个 acs 基础资源巡检项（数据驱动，零计算逻辑）

    新增巡检项 = 新增一个 PredictionCase 数据项，不需要写新的计算代码。
    """
    return [
        # ── ECS ──────────────────────────────────────────
        PredictionCase(
            case_id="ecs_cpu_trend",
            item="ECS CPU 趋势预测",
            severity=Severity.P1,
            strategy=Strategy.TREND_PREDICTION,
            warning_threshold=85.0,
            critical_threshold=95.0,
            description="ECS CPU 使用率趋势预测，deriv > 0 且 predict_linear 超阈值",
            promql_current='avg by (instance_id) (AliyunEcs_CPUUtilization)',
            promql_deriv='avg by (instance_id) (deriv(AliyunEcs_CPUUtilization[6h]))',
            promql_predict='avg by (instance_id) (predict_linear(AliyunEcs_CPUUtilization[6h], 86400))',
            entity_label="instance_id",
            name_label="instance_id",
            data_format="percent",
        ),
        PredictionCase(
            case_id="ecs_disk_trend",
            item="ECS 磁盘缓慢增长",
            severity=Severity.P1,
            strategy=Strategy.SLOW_GROWTH,
            warning_threshold=80.0,
            critical_threshold=90.0,
            description="ECS 磁盘使用率缓慢增长，7 天预测超阈值",
            promql_current='avg by (instance_id) (AliyunEcs_diskusage_utilization)',
            promql_deriv='avg by (instance_id) (deriv(AliyunEcs_diskusage_utilization[6h]))',
            promql_predict_7d='avg by (instance_id) (predict_linear(AliyunEcs_diskusage_utilization[6h], 604800))',
            promql_avg_7d='avg by (instance_id) (avg_over_time(AliyunEcs_diskusage_utilization[7d]))',
            entity_label="instance_id",
            name_label="instance_id",
            data_format="percent",
        ),
        PredictionCase(
            case_id="ecs_memory_trend",
            item="ECS 内存趋势预测",
            severity=Severity.P2,
            strategy=Strategy.TREND_PREDICTION,
            warning_threshold=85.0,
            critical_threshold=95.0,
            description="ECS 内存使用率趋势预测",
            promql_current='avg by (instance_id) (AliyunEcs_memory_usedutilization)',
            promql_deriv='avg by (instance_id) (deriv(AliyunEcs_memory_usedutilization[6h]))',
            promql_predict='avg by (instance_id) (predict_linear(AliyunEcs_memory_usedutilization[6h], 86400))',
            entity_label="instance_id",
            name_label="instance_id",
            data_format="percent",
        ),
        # ── RDS ──────────────────────────────────────────
        PredictionCase(
            case_id="rds_cpu_trend",
            item="RDS CPU 趋势预测",
            severity=Severity.P1,
            strategy=Strategy.TREND_PREDICTION,
            warning_threshold=70.0,
            critical_threshold=85.0,
            description="RDS CPU 使用率趋势预测",
            promql_current='avg by (instance_id) (AliyunRds_CpuUsage)',
            promql_deriv='avg by (instance_id) (deriv(AliyunRds_CpuUsage[6h]))',
            promql_predict='avg by (instance_id) (predict_linear(AliyunRds_CpuUsage[6h], 86400))',
            entity_label="instance_id",
            name_label="instance_id",
            data_format="percent",
        ),
        PredictionCase(
            case_id="rds_conn_trend",
            item="RDS 连接数趋势预测",
            severity=Severity.P2,
            strategy=Strategy.TREND_PREDICTION,
            warning_threshold=70.0,
            critical_threshold=85.0,
            description="RDS 连接数使用率趋势预测",
            promql_current='avg by (instance_id) (AliyunRds_ConnectionUsage)',
            promql_deriv='avg by (instance_id) (deriv(AliyunRds_ConnectionUsage[6h]))',
            promql_predict='avg by (instance_id) (predict_linear(AliyunRds_ConnectionUsage[6h], 86400))',
            entity_label="instance_id",
            name_label="instance_id",
            data_format="percent",
        ),
        # ── Redis ────────────────────────────────────────
        PredictionCase(
            case_id="redis_memory_trend",
            item="Redis 内存缓慢增长",
            severity=Severity.P1,
            strategy=Strategy.SLOW_GROWTH,
            warning_threshold=75.0,
            critical_threshold=90.0,
            description="Redis 内存使用率缓慢增长，7 天预测超阈值",
            promql_current='avg by (instance_id) (AliyunKvstore_StandardMemoryUsage)',
            promql_deriv='avg by (instance_id) (deriv(AliyunKvstore_StandardMemoryUsage[6h]))',
            promql_predict_7d='avg by (instance_id) (predict_linear(AliyunKvstore_StandardMemoryUsage[6h], 604800))',
            promql_avg_7d='avg by (instance_id) (avg_over_time(AliyunKvstore_StandardMemoryUsage[7d]))',
            entity_label="instance_id",
            name_label="instance_id",
            data_format="percent",
        ),
    ]


if __name__ == "__main__":
    cases = build_cases()
    cli_main(
        cases=cases,
        description="acs 基础资源容量风险预测（6 项）：ECS CPU/磁盘/内存、RDS CPU/连接数、Redis 内存",
    )
