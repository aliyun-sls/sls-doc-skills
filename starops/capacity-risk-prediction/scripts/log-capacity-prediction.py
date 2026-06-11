#!/usr/bin/env python3
"""
log-capacity-prediction.py - 日志衍生时序容量风险预测（3 项）

业务脚本：只声明 PredictionCase 配置，零计算逻辑。
所有计算由 capacity_prediction_common.py + capacity_prediction_engine.py 承载。

Log 域特殊实现：
- 使用 starops sls query 执行 SLS SQL（ts_predicate_arma / ts_decompose）
- 从 LogStore 构造时序数据（time_series + count(*)）
- ARIMA 预测：ts_predicate_arma(t, cnt, p, d, q, n, step)
- 分解与异常检测：ts_decompose + ts_anomaly_filter

所有环境参数通过 CLI 传入，不写死任何具体值。

覆盖：日志请求量 ARIMA 预测 / 日志错误率异常检测 / 日志量趋势分解
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
    声明 3 个日志衍生时序巡检项（数据驱动，零计算逻辑）

    新增巡检项 = 新增一个 PredictionCase 数据项，不需要写新的计算代码。

    log_query 中使用 {filter} 占位符，运行时由引擎替换为 --log-filter 参数值。
    """
    return [
        PredictionCase(
            case_id="log_request_volume",
            item="日志请求量 ARIMA 预测",
            severity=Severity.P1,
            strategy=Strategy.ARIMA_PREDICTION,
            warning_threshold=2.0,
            critical_threshold=3.0,
            description="从 LogStore 构造请求量时序，ts_predicate_arma 预测未来值，预测值超当前 2 倍 Warning / 3 倍 Critical",
            log_query='{filter} | SELECT ts_predicate_arma(t, cnt, 2, 1, 2, 24, 1) FROM (SELECT time_series(__time__, \'5m\', \'%Y-%m-%d %H:%i:%s\', \'0\') as t, count(*) as cnt FROM log GROUP BY t ORDER BY t) WHERE cnt > 0',
            entity_label="logstore",
            name_label="logstore",
            data_format="raw",
            arima_p=2,
            arima_d=1,
            arima_q=2,
            arima_n=24,
            arima_step=1,
        ),
        PredictionCase(
            case_id="log_error_rate",
            item="日志错误率异常检测",
            severity=Severity.P1,
            strategy=Strategy.DECOMPOSITION_ANOMALY,
            warning_threshold=0.8,
            critical_threshold=0.95,
            description="从 LogStore 构造错误数时序（HTTP 4xx/5xx），ts_decompose 分解并检测异常",
            log_query='{filter} | SELECT ts_decompose(t, cnt) FROM (SELECT time_series(__time__, \'5m\', \'%Y-%m-%d %H:%i:%s\', \'0\') as t, sum(case when content LIKE \'%" 4%\' or content LIKE \'%" 5%\' then 1 else 0 end) as cnt FROM log GROUP BY t ORDER BY t) WHERE cnt > 0',
            entity_label="logstore",
            name_label="logstore",
            data_format="raw",
            decompose_period=24,
        ),
        PredictionCase(
            case_id="log_volume_trend",
            item="日志量趋势分解",
            severity=Severity.P2,
            strategy=Strategy.DECOMPOSITION_ANOMALY,
            warning_threshold=2.0,
            critical_threshold=3.0,
            description="从 LogStore 构造日志量时序，ts_decompose 发现周期性和残差异常",
            log_query='{filter} | SELECT ts_decompose(t, cnt) FROM (SELECT time_series(__time__, \'5m\', \'%Y-%m-%d %H:%i:%s\', \'0\') as t, count(*) as cnt FROM log GROUP BY t ORDER BY t) WHERE cnt > 0',
            entity_label="logstore",
            name_label="logstore",
            data_format="raw",
            decompose_period=24,
        ),
    ]


if __name__ == "__main__":
    cases = build_cases()
    cli_main(
        cases=cases,
        description="日志衍生时序容量风险预测（3 项）：请求量 ARIMA 预测、错误率异常检测、日志量趋势分解",
        domain="log",
    )
