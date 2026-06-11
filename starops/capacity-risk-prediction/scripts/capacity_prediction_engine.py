#!/usr/bin/env python3
"""
capacity_prediction_engine.py - 执行引擎

承载所有巡检项的执行逻辑：PromQL 查询、APM 查询、Log 查询、策略评估、批量执行、CLI 入口。
业务脚本通过 capacity_prediction_common.py 导入 cli_main（re-export）。

支持 4 个域：acs / k8s（PromQL）、apm（metric_set query）、log（SLS SQL）
支持 7 种策略：趋势预测、基线偏离、缓慢增长、阈值突破、
  短期波动(holt_winters)、ARIMA 预测、分解与异常检测
"""

import json
import sys
import argparse
from typing import Any, Dict, List, Optional, Tuple

from capacity_prediction_common import (
    PredictionCase, PredictionResult, BatchPredictionOutput,
    Severity, Status, RiskLevel, Strategy,
    run_promql, run_metric_set_query, run_sls_query,
    extract_labels, extract_value, extract_timeseries,
    parse_results, group_by_key,
    extract_apm_summary, extract_apm_entity_id,
    parse_sls_ts_json, extract_arima_predictions,
    extract_decompose_stats, count_anomalies,
    linear_regression, calculate_days_to_threshold,
    evaluate_trend, evaluate_baseline, evaluate_slow_growth, evaluate_threshold,
    evaluate_holt_winters, evaluate_arima, evaluate_decomposition_anomaly,
    build_base_arg_parser, add_promql_args, add_apm_args, add_log_args,
    print_cases,
)


def _make_result(case: PredictionCase, time_range: str) -> PredictionResult:
    """创建初始结果对象"""
    return PredictionResult(
        case_id=case.case_id,
        item=case.item,
        severity=case.severity.value,
        strategy=case.strategy.value,
        status=Status.NO_PROBLEM_FOUND.value,
        risk_level=None,
        time_range=time_range,
        entity_id="",
        entity_name="",
        current_value=None,
        warning_threshold=case.warning_threshold,
        critical_threshold=case.critical_threshold,
        deriv_value=None,
        predicted_value=None,
        days_to_warning=None,
        baseline_value=None,
        deviation_ratio=None,
        deviation_direction=None,
        predicted_7d_value=None,
        avg_7d_value=None,
        exceed_percent=None,
        holt_winters_value=None,
        spike_ratio=None,
        arima_predicted_value=None,
        arima_confidence=None,
        anomaly_score=None,
        anomaly_count=None,
        total_points=None,
        anomaly_ratio=None,
        trend_value=None,
        seasonal_value=None,
        residual_std=None,
        raw_query=case.promql_current or case.log_query or case.metric_names,
    )


# ──────────────────────────────────────────────
# PromQL 域（acs/k8s）执行逻辑
# ──────────────────────────────────────────────

def _run_promql_case(case: PredictionCase, region: str, project: str,
                     metricstore: str, time_range: str) -> Dict[str, Any]:
    """执行 PromQL 域巡检项（acs/k8s）"""
    result = _make_result(case, time_range)

    # 查询当前值
    if case.promql_current:
        success, data, error = run_promql(region, project, metricstore,
                                           case.promql_current, time_range)
        if not success:
            result.status = Status.ERROR.value
            result.error = error
            return _to_dict(result)
        rows = parse_results(data)
        if not rows:
            result.status = Status.NO_PROBLEM_FOUND.value
            return _to_dict(result)
        first_row = rows[0]
        labels = extract_labels(first_row)
        result.entity_id = labels.get(case.entity_label, "unknown")
        result.entity_name = labels.get(case.name_label, result.entity_id)
        result.current_value = extract_value(first_row)
        if result.current_value is None:
            result.status = Status.NO_PROBLEM_FOUND.value
            return _to_dict(result)

    # 根据策略路由
    strategy = case.strategy
    if strategy == Strategy.TREND_PREDICTION:
        return _eval_trend_promql(case, result, region, project, metricstore, time_range)
    elif strategy == Strategy.BASELINE_DEVIATION:
        return _eval_baseline_promql(case, result, region, project, metricstore, time_range)
    elif strategy == Strategy.SLOW_GROWTH:
        return _eval_slow_growth_promql(case, result, region, project, metricstore, time_range)
    elif strategy == Strategy.THRESHOLD_BREACH:
        return _eval_threshold(result)
    elif strategy == Strategy.SHORT_TERM_FLUCTUATION:
        return _eval_holt_winters_promql(case, result, region, project, metricstore, time_range)
    else:
        result.status = Status.ERROR.value
        result.error = f"Unsupported PromQL strategy: {strategy.value}"
        return _to_dict(result)


def _query_promql_value(region: str, project: str, metricstore: str,
                         query: str, time_range: str) -> Optional[float]:
    """查询 PromQL 并返回第一个值"""
    if not query:
        return None
    success, data, error = run_promql(region, project, metricstore, query, time_range)
    if not success:
        return None
    rows = parse_results(data)
    if not rows:
        return None
    return extract_value(rows[0])


def _eval_trend_promql(case: PredictionCase, result: PredictionResult,
                        region: str, project: str, metricstore: str,
                        time_range: str) -> Dict[str, Any]:
    """趋势预测策略（PromQL）"""
    deriv = _query_promql_value(region, project, metricstore, case.promql_deriv, time_range) or 0.0
    result.deriv_value = deriv
    predicted = _query_promql_value(region, project, metricstore, case.promql_predict, time_range)
    if predicted is not None:
        result.predicted_value = predicted
    predicted_val = predicted if predicted is not None else (result.current_value or 0)
    risk_level, days = evaluate_trend(
        result.current_value or 0, deriv, predicted_val,
        case.warning_threshold, case.critical_threshold
    )
    result.risk_level = risk_level
    result.days_to_warning = days
    result.status = Status.FIND_PROBLEM.value if risk_level != RiskLevel.NORMAL.value else Status.PASS.value
    return _to_dict(result)


def _eval_baseline_promql(case: PredictionCase, result: PredictionResult,
                           region: str, project: str, metricstore: str,
                           time_range: str) -> Dict[str, Any]:
    """基线偏离策略（PromQL）"""
    offset_1d = _query_promql_value(region, project, metricstore, case.promql_offset_1d, time_range)
    avg_7d = _query_promql_value(region, project, metricstore, case.promql_avg_7d, time_range)
    if offset_1d is not None:
        result.baseline_value = offset_1d
    if avg_7d is not None:
        result.avg_7d_value = avg_7d
    current = result.current_value or 0
    risk_level, ratio, direction = evaluate_baseline(
        current,
        offset_1d if offset_1d is not None else current,
        avg_7d if avg_7d is not None else current
    )
    result.risk_level = risk_level
    result.deviation_ratio = ratio
    result.deviation_direction = direction
    result.status = Status.FIND_PROBLEM.value if risk_level != RiskLevel.NORMAL.value else Status.PASS.value
    return _to_dict(result)


def _eval_slow_growth_promql(case: PredictionCase, result: PredictionResult,
                              region: str, project: str, metricstore: str,
                              time_range: str) -> Dict[str, Any]:
    """缓慢增长策略（PromQL）"""
    deriv = _query_promql_value(region, project, metricstore, case.promql_deriv, time_range) or 0.0
    result.deriv_value = deriv
    predicted_7d = _query_promql_value(region, project, metricstore, case.promql_predict_7d, time_range)
    avg_7d = _query_promql_value(region, project, metricstore, case.promql_avg_7d, time_range)
    if predicted_7d is not None:
        result.predicted_7d_value = predicted_7d
    if avg_7d is not None:
        result.avg_7d_value = avg_7d
    current = result.current_value or 0
    pred_7d = predicted_7d if predicted_7d is not None else current
    avg_7d_val = avg_7d if avg_7d is not None else current
    risk_level, days = evaluate_slow_growth(
        current, pred_7d, avg_7d_val,
        case.warning_threshold, case.critical_threshold, deriv
    )
    result.risk_level = risk_level
    result.days_to_warning = days
    result.status = Status.FIND_PROBLEM.value if risk_level != RiskLevel.NORMAL.value else Status.PASS.value
    return _to_dict(result)


def _eval_holt_winters_promql(case: PredictionCase, result: PredictionResult,
                               region: str, project: str, metricstore: str,
                               time_range: str) -> Dict[str, Any]:
    """短期波动策略（PromQL holt_winters）"""
    hw_val = _query_promql_value(region, project, metricstore, case.promql_holt_winters, time_range)
    if hw_val is not None:
        result.holt_winters_value = hw_val
    current = result.current_value or 0
    hw_value = hw_val if hw_val is not None else current
    risk_level, spike_ratio = evaluate_holt_winters(
        current, hw_value, case.warning_threshold, case.critical_threshold
    )
    result.risk_level = risk_level
    result.spike_ratio = spike_ratio
    result.status = Status.FIND_PROBLEM.value if risk_level != RiskLevel.NORMAL.value else Status.PASS.value
    return _to_dict(result)


def _eval_threshold(result: PredictionResult) -> Dict[str, Any]:
    """阈值突破策略"""
    current = result.current_value or 0
    risk_level, exceed = evaluate_threshold(
        current, result.warning_threshold, result.critical_threshold
    )
    result.risk_level = risk_level
    result.exceed_percent = exceed
    result.status = Status.FIND_PROBLEM.value if risk_level != RiskLevel.NORMAL.value else Status.PASS.value
    return _to_dict(result)


# ──────────────────────────────────────────────
# APM 域执行逻辑
# ──────────────────────────────────────────────

def _run_apm_case(case: PredictionCase, result: PredictionResult,
                   workspace: str, entity_domain: str, entity_type: str,
                   entity_id: str, time_range: str) -> Dict[str, Any]:
    """执行 APM 域巡检项"""
    success, data, error = run_metric_set_query(
        workspace, entity_domain, entity_type, entity_id,
        case.metric_set_domain, case.metric_set_name,
        case.metric_names, time_range
    )
    if not success:
        result.status = Status.ERROR.value
        result.error = error
        return _to_dict(result)
    summary = extract_apm_summary(data)
    if not summary:
        result.status = Status.NO_PROBLEM_FOUND.value
        return _to_dict(result)
    eid, ename = extract_apm_entity_id(data)
    result.entity_id = eid or entity_id
    result.entity_name = ename or entity_id

    # 提取当前值
    current = None
    max_val = None
    for metric_name, stats in summary.items():
        if stats.get("mean") is not None:
            current = stats["mean"]
        if stats.get("max") is not None:
            max_val = stats["max"]
        break
    if current is None:
        result.status = Status.NO_PROBLEM_FOUND.value
        return _to_dict(result)
    result.current_value = current

    strategy = case.strategy
    if strategy == Strategy.THRESHOLD_BREACH:
        return _eval_threshold(result)
    elif strategy == Strategy.BASELINE_DEVIATION:
        return _eval_apm_baseline(case, result, current, max_val)
    else:
        return _eval_apm_trend(case, result, current, max_val)


def _eval_apm_baseline(case: PredictionCase, result: PredictionResult,
                        current: float, max_val: Optional[float]) -> Dict[str, Any]:
    """APM 基线偏离策略"""
    result.baseline_value = current
    if max_val is not None and current > 0:
        ratio = max_val / current
        result.deviation_ratio = ratio
        if ratio > 2.0:
            result.risk_level = RiskLevel.WARNING.value
            result.deviation_direction = "spike"
            result.status = Status.FIND_PROBLEM.value
        else:
            result.risk_level = RiskLevel.NORMAL.value
            result.deviation_direction = "stable"
            result.status = Status.PASS.value
    else:
        result.risk_level = RiskLevel.NORMAL.value
        result.deviation_ratio = 1.0
        result.deviation_direction = "stable"
        result.status = Status.PASS.value
    return _to_dict(result)


def _eval_apm_trend(case: PredictionCase, result: PredictionResult,
                     current: float, max_val: Optional[float]) -> Dict[str, Any]:
    """APM 趋势预测策略"""
    if max_val is not None and max_val > current:
        spread = max_val - current
        result.deriv_value = spread / 6.0
        result.predicted_value = current + spread
        result.days_to_warning = calculate_days_to_threshold(
            current, result.deriv_value, case.warning_threshold
        )
    deriv = result.deriv_value or 0.0
    predicted = result.predicted_value or current
    risk_level, days = evaluate_trend(
        current, deriv, predicted, case.warning_threshold, case.critical_threshold
    )
    result.risk_level = risk_level
    result.days_to_warning = days
    result.status = Status.FIND_PROBLEM.value if risk_level != RiskLevel.NORMAL.value else Status.PASS.value
    return _to_dict(result)


# ──────────────────────────────────────────────
# Log 域执行逻辑
# ──────────────────────────────────────────────

def _build_log_query(template: str, log_filter: str) -> str:
    """构建日志查询：将 log_filter 插入模板的 {filter} 占位符"""
    search_part = log_filter if log_filter else "*"
    return template.replace("{filter}", search_part)


def _run_log_case(case: PredictionCase, region: str, logstore_project: str,
                   logstore: str, log_filter: str, time_range: str) -> Dict[str, Any]:
    """执行 Log 域巡检项"""
    result = _make_result(case, time_range)
    result.entity_id = logstore
    result.entity_name = logstore

    query = _build_log_query(case.log_query, log_filter)
    result.raw_query = query

    success, data, error = run_sls_query(region, logstore_project, logstore, query, time_range)
    if not success:
        result.status = Status.ERROR.value
        result.error = error
        return _to_dict(result)

    rows = parse_results(data)
    if not rows:
        result.status = Status.NO_PROBLEM_FOUND.value
        return _to_dict(result)

    strategy = case.strategy
    if strategy == Strategy.ARIMA_PREDICTION:
        return _eval_arima_log(case, result, rows)
    elif strategy == Strategy.DECOMPOSITION_ANOMALY:
        return _eval_decomposition_log(case, result, rows)
    else:
        result.status = Status.ERROR.value
        result.error = f"Unsupported log strategy: {strategy.value}"
        return _to_dict(result)


def _eval_arima_log(case: PredictionCase, result: PredictionResult,
                     rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """ARIMA 预测策略（Log 域 ts_predicate_arma）

    SLS ts_predicate_arma 返回 logs 数组，每行一个数据点，含 unixtime/src/predict/upper/lower 字段。
    rows 已经是 parse_results() 解析后的数据点列表。
    """
    ts_data = rows

    if not ts_data:
        result.status = Status.NO_PROBLEM_FOUND.value
        result.error = "No ARIMA prediction data found"
        return _to_dict(result)

    # 提取预测值：取最后一个有 predict 字段的行
    predicted = None
    confidence = None
    for point in reversed(ts_data):
        try:
            pred_val = float(point.get("predict", point.get("y_predict", 0)))
            if pred_val > 0:
                predicted = pred_val
                # 计算置信度：1 - abs(actual - predict) / predict
                actual_val = float(point.get("src", point.get("y", point.get("actual", pred_val))))
                if pred_val > 0:
                    confidence = max(0.0, 1.0 - abs(actual_val - pred_val) / pred_val)
                else:
                    confidence = 1.0 if actual_val == 0 else 0.0
                break
        except (ValueError, TypeError):
            continue

    if predicted is None:
        result.status = Status.NO_PROBLEM_FOUND.value
        return _to_dict(result)

    result.arima_predicted_value = predicted
    result.arima_confidence = confidence

    # 提取当前值（最后一个实际值，SLS 格式用 src 字段）
    current = None
    for point in reversed(ts_data):
        try:
            y = float(point.get("src", point.get("y", point.get("actual", 0))))
            if y > 0:
                current = y
                break
        except (ValueError, TypeError):
            continue
    if current is not None:
        result.current_value = current

    current_val = current or 1.0
    risk_level, ratio = evaluate_arima(
        current_val, predicted, confidence or 1.0,
        case.warning_threshold, case.critical_threshold
    )
    result.risk_level = risk_level
    result.deviation_ratio = ratio
    result.status = Status.FIND_PROBLEM.value if risk_level != RiskLevel.NORMAL.value else Status.PASS.value
    return _to_dict(result)


def _eval_decomposition_log(case: PredictionCase, result: PredictionResult,
                              rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """分解与异常检测策略（Log 域 ts_decompose）

    SLS ts_decompose 返回 logs 数组，每行一个数据点，含 unixtime/src/trend/season/residual 字段。
    rows 已经是 parse_results() 解析后的数据点列表。
    """
    # rows 直接就是数据点数组（SLS logs 格式）
    ts_data = rows

    if not ts_data:
        result.status = Status.NO_PROBLEM_FOUND.value
        result.error = "No decomposition data found"
        return _to_dict(result)

    avg_trend, avg_seasonal, residual_std = extract_decompose_stats(ts_data)
    anomaly_count, total_points = count_anomalies(ts_data)

    if residual_std is not None:
        result.residual_std = residual_std
    if avg_trend is not None:
        result.trend_value = avg_trend
    if avg_seasonal is not None:
        result.seasonal_value = avg_seasonal
    result.anomaly_count = anomaly_count
    result.total_points = total_points

    # 评估：基于异常比例和残差标准差
    # 默认阈值：异常比例 > 0.8 warning, > 0.95 critical
    anomaly_std_threshold = residual_std if residual_std else 1.0
    risk_level, anomaly_ratio, res_std = evaluate_decomposition_anomaly(
        residual_std or 0.0, anomaly_count, total_points,
        anomaly_std_threshold,
        0.8,  # warning ratio
        0.95  # critical ratio
    )
    result.risk_level = risk_level
    result.anomaly_ratio = anomaly_ratio
    result.anomaly_score = res_std

    # 提取当前值（第一个实际值，SLS 格式用 src 字段）
    for point in ts_data:
        try:
            raw = float(point.get("src", point.get("raw", point.get("y", 0))))
            if raw > 0:
                result.current_value = raw
                break
        except (ValueError, TypeError):
            continue

    result.status = Status.FIND_PROBLEM.value if risk_level != RiskLevel.NORMAL.value else Status.PASS.value
    return _to_dict(result)


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def _to_dict(result: PredictionResult) -> Dict[str, Any]:
    """将 PredictionResult 转为 dict"""
    from dataclasses import asdict
    return asdict(result)


# ──────────────────────────────────────────────
# 批量执行
# ──────────────────────────────────────────────

def run_case(case: PredictionCase, region: str = "", project: str = "",
             metricstore: str = "", time_range: str = "",
             workspace: str = "", entity_domain: str = "",
             entity_type: str = "", entity_id: str = "",
             logstore_project: str = "", logstore: str = "",
             log_filter: str = "") -> Dict[str, Any]:
    """执行单个巡检项（自动路由到对应域）"""
    result = _make_result(case, time_range)

    # 判断域类型
    is_log = bool(case.log_query)
    is_apm = bool(case.metric_set_domain)

    if is_log:
        return _run_log_case(case, region or "", logstore_project, logstore,
                             log_filter, time_range)
    elif is_apm:
        return _run_apm_case(case, result, workspace, entity_domain,
                             entity_type, entity_id, time_range)
    else:
        return _run_promql_case(case, region, project, metricstore, time_range)


def run_all_cases(cases: List[PredictionCase], region: str = "", project: str = "",
                  metricstore: str = "", time_range: str = "",
                  workspace: str = "", entity_domain: str = "",
                  entity_type: str = "", entity_id: str = "",
                  logstore_project: str = "", logstore: str = "",
                  log_filter: str = "",
                  case_filter: Optional[List[str]] = None) -> Dict[str, Any]:
    """批量执行所有巡检项"""
    filtered_cases = cases
    if case_filter:
        filtered_cases = [c for c in cases if c.case_id in case_filter]

    results = []
    for case in filtered_cases:
        r = run_case(
            case=case,
            region=region,
            project=project,
            metricstore=metricstore,
            time_range=time_range,
            workspace=workspace,
            entity_domain=entity_domain,
            entity_type=entity_type,
            entity_id=entity_id,
            logstore_project=logstore_project,
            logstore=logstore,
            log_filter=log_filter,
        )
        results.append(r)

    critical = sum(1 for r in results if r.get("risk_level") == RiskLevel.CRITICAL.value)
    warning = sum(1 for r in results if r.get("risk_level") == RiskLevel.WARNING.value)
    normal = sum(1 for r in results if r.get("risk_level") == RiskLevel.NORMAL.value)
    errors = sum(1 for r in results if r["status"] == Status.ERROR.value)
    no_problem = sum(1 for r in results if r["status"] == Status.NO_PROBLEM_FOUND.value)

    from dataclasses import asdict
    output = BatchPredictionOutput(
        total_cases=len(results),
        critical_cases=critical,
        warning_cases=warning,
        normal_cases=normal,
        errors=errors,
        no_problem_found=no_problem,
        has_critical=(critical > 0),
        has_warning=(warning > 0),
        results=results,
    )
    return asdict(output)


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

def cli_main(cases: List[PredictionCase], description: str,
             domain: str = "promql") -> None:
    """
    通用 CLI 入口

    domain: "promql" | "apm" | "log"
    """
    parser = build_base_arg_parser(description)

    if domain == "promql":
        add_promql_args(parser)
    elif domain == "apm":
        add_apm_args(parser)
    elif domain == "log":
        add_log_args(parser)

    args = parser.parse_args()

    # --list-cases
    if args.list_cases:
        print_cases(cases)
        sys.exit(0)

    # 校验必填参数
    if domain == "promql":
        if not args.region or not args.project or not args.metricstore or not args.time_range:
            parser.error("--region, --project, --metricstore, and --time-range are required")
    elif domain == "apm":
        if not args.workspace or not args.entity_domain or not args.entity_type or not args.entity_id or not args.time_range:
            parser.error("--workspace, --entity-domain, --entity-type, --entity-id, and --time-range are required")
    elif domain == "log":
        if not args.region or not args.logstore_project or not args.logstore or not args.time_range:
            parser.error("--region, --logstore-project, --logstore, and --time-range are required")

    output = run_all_cases(
        cases=cases,
        region=getattr(args, "region", ""),
        project=getattr(args, "project", ""),
        metricstore=getattr(args, "metricstore", ""),
        time_range=args.time_range,
        workspace=getattr(args, "workspace", ""),
        entity_domain=getattr(args, "entity_domain", ""),
        entity_type=getattr(args, "entity_type", ""),
        entity_id=getattr(args, "entity_id", ""),
        logstore_project=getattr(args, "logstore_project", ""),
        logstore=getattr(args, "logstore", ""),
        log_filter=getattr(args, "log_filter", ""),
        case_filter=args.cases,
    )
    print(json.dumps(output, indent=2, ensure_ascii=False))
