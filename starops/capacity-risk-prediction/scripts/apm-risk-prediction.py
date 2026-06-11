#!/usr/bin/env python3
"""
apm-risk-prediction.py - APM 业务服务风险预测（3 项）

业务脚本：只声明 PredictionCase 配置，零计算逻辑。
所有计算由 capacity_prediction_common.py + capacity_prediction_engine.py 承载。

APM 域特殊实现：
- 使用 starops observe metric_set query 获取指标摘要数据
- 从 __summary__.cur_statistics 提取 mean_value / max_value
- 脚本内用线性回归计算趋势

覆盖：服务错误率 / 服务延迟 / 服务 QPS 突增
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from capacity_prediction_common import (
    PredictionCase, Severity, Strategy,
)
from capacity_prediction_engine import cli_main


def build_cases(time_range: str = "") -> list:
    """
    声明 3 个 APM 业务服务巡检项（数据驱动，零计算逻辑）

    新增巡检项 = 新增一个 PredictionCase 数据项，不需要写新的计算代码。
    """
    return [
        PredictionCase(
            case_id="service_error_rate",
            item="服务错误率阈值突破",
            severity=Severity.P1,
            strategy=Strategy.THRESHOLD_BREACH,
            warning_threshold=5.0,
            critical_threshold=10.0,
            description="服务错误率超过 Warning(5%) 或 Critical(10%) 阈值",
            metric_set_domain="apm",
            metric_set_name="apm.metric.apm.service",
            metric_names="error_rate",
            entity_label="service_id",
            name_label="service_name",
            data_format="percent",
        ),
        PredictionCase(
            case_id="service_latency",
            item="服务延迟阈值突破 + 趋势",
            severity=Severity.P1,
            strategy=Strategy.THRESHOLD_BREACH,
            warning_threshold=200.0,
            critical_threshold=500.0,
            description="服务平均延迟超过 Warning(200ms) 或 Critical(500ms) 阈值",
            metric_set_domain="apm",
            metric_set_name="apm.metric.apm.service",
            metric_names="avg_request_latency_seconds",
            entity_label="service_id",
            name_label="service_name",
            data_format="ms",
        ),
        PredictionCase(
            case_id="service_qps_spike",
            item="服务 QPS 基线偏离",
            severity=Severity.P2,
            strategy=Strategy.BASELINE_DEVIATION,
            warning_threshold=2.0,
            critical_threshold=3.0,
            description="服务 QPS 日环比偏离超过 2 倍",
            metric_set_domain="apm",
            metric_set_name="apm.metric.apm.service",
            metric_names="request_count",
            entity_label="service_id",
            name_label="service_name",
            data_format="raw",
        ),
    ]


if __name__ == "__main__":
    cases = build_cases()
    cli_main(
        cases=cases,
        description="APM 业务服务风险预测（3 项）：服务错误率、服务延迟、服务 QPS 突增",
        domain="apm",
    )
