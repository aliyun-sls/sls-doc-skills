#!/usr/bin/env python3
"""
k8s-capacity-prediction.py - k8s 集群资源容量风险预测（3 项）

业务脚本：只声明 PredictionCase 配置，零计算逻辑。
所有计算由 capacity_prediction_common.py 公共引擎承载。

覆盖：Node CPU / Node 内存 / Pod 内存
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from capacity_prediction_common import (
    PredictionCase, Severity, Strategy, cli_main
)


def build_cases(time_range: str = "") -> list:
    """
    声明 3 个 k8s 集群资源巡检项（数据驱动，零计算逻辑）

    新增巡检项 = 新增一个 PredictionCase 数据项，不需要写新的计算代码。
    """
    return [
        PredictionCase(
            case_id="node_cpu_trend",
            item="Node CPU 趋势预测 + 基线偏离",
            severity=Severity.P1,
            strategy=Strategy.TREND_PREDICTION,
            warning_threshold=70.0,
            critical_threshold=85.0,
            description="Node CPU 使用率趋势预测，结合基线偏离检测",
            promql_current='100 - (avg by (node) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
            promql_deriv='avg by (node) (deriv((100 - (avg by (node) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100))[6h]))',
            promql_predict='avg by (node) (predict_linear((100 - (avg by (node) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100))[6h], 86400))',
            promql_offset_1d='100 - (avg by (node) (rate(node_cpu_seconds_total{mode="idle"}[5m]) offset 1d) * 100)',
            entity_label="node",
            name_label="node",
            data_format="percent",
        ),
        PredictionCase(
            case_id="node_memory_trend",
            item="Node 内存趋势预测",
            severity=Severity.P1,
            strategy=Strategy.TREND_PREDICTION,
            warning_threshold=80.0,
            critical_threshold=90.0,
            description="Node 内存使用率趋势预测（基于可用内存百分比）",
            promql_current='(1 - avg by (node) (node_memory_MemAvailable_bytes) / avg by (node) (node_memory_MemTotal_bytes)) * 100',
            promql_deriv='avg by (node) (deriv((1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)[6h])) * 100',
            promql_predict='avg by (node) (predict_linear((1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)[6h], 86400)) * 100',
            entity_label="node",
            name_label="node",
            data_format="percent",
        ),
        PredictionCase(
            case_id="pod_memory_trend",
            item="Pod 内存缓慢增长",
            severity=Severity.P2,
            strategy=Strategy.SLOW_GROWTH,
            warning_threshold=80.0,
            critical_threshold=95.0,
            description="Pod 内存使用率缓慢增长，7 天预测超阈值",
            promql_current='avg by (namespace, pod) (container_memory_working_set_bytes{container!="",container!="POD"}) / avg by (namespace, pod) (kube_pod_container_resource_limits_memory_bytes{container!="",container!="POD"}) * 100',
            promql_deriv='avg by (namespace, pod) (deriv((container_memory_working_set_bytes{container!="",container!="POD"} / kube_pod_container_resource_limits_memory_bytes{container!="",container!="POD"} * 100)[6h]))',
            promql_predict_7d='avg by (namespace, pod) (predict_linear((container_memory_working_set_bytes{container!="",container!="POD"} / kube_pod_container_resource_limits_memory_bytes{container!="",container!="POD"} * 100)[6h], 604800))',
            promql_avg_7d='avg by (namespace, pod) (avg_over_time((container_memory_working_set_bytes{container!="",container!="POD"} / kube_pod_container_resource_limits_memory_bytes{container!="",container!="POD"} * 100)[7d]))',
            entity_label="pod",
            name_label="pod",
            data_format="percent",
        ),
    ]


if __name__ == "__main__":
    cases = build_cases()
    cli_main(
        cases=cases,
        description="k8s 集群资源容量风险预测（3 项）：Node CPU、Node 内存、Pod 内存",
    )
