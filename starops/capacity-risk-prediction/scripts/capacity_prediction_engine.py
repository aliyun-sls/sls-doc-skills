#!/usr/bin/env python3
"""
capacity_prediction_engine.py - 执行引擎

承载所有巡检项的执行逻辑：PromQL 查询、APM 查询、策略评估、批量执行、CLI 入口。
业务脚本通过 capacity_prediction_common.py 导入 cli_main（re-export）。
"""

import json
import sys
import argparse
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from capacity_prediction_common import (
    PredictionCase, PredictionResult, BatchPredictionOutput,
    Severity, Status, RiskLevel, Strategy,
    run_promql, run_metric_set_query,
    extract_labels, extract_value, extract_timeseries,
    parse_results, group_by_key,
    extract_apm_summary, extract_apm_entity_id,
    linear_regression, calculate_days_to_threshold,
    evaluate_trend, evaluate_baseline, evaluate_slow_growth, evaluate_threshold,
)


def _run_promql_case(case: PredictionCase, region: str, project: str,
                     metricstore: str, time_range: str) -> Dict[str, Any]:
    """执行 PromQL 域巡检项（acs/k8s）"""
    result = PredictionResult(
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
        raw_query=case.promql_current,
    )

    # 查询当前值
    if case.promql_current:
        success, data, error = run_promql(region, project, metricstore,
                                           case.promql_current, time_range)
        if not success:
            result.status = Status.ERROR.value
            result.error = error
            return asdict(result)

        rows = parse_results(data)
        if not rows:
            result.status = Status.NO_PROBLEM_FOUND.value
            return asdict(result)

        # 提取第一个实体的值
        first_row = rows[0]
        labels = extract_labels(first_row)
        result.entity_id = labels.get(case.entity_label, "unknown")
        result.entity_name = labels.get(case.name_label, result.entity_id)
        result.current_value = extract_value(first_row)

        if result.current_value is None:
            result.status = Status.NO_PROBLEM_FOUND.value
            return asdict(result)

    # 根据策略执行不同评估
    if case.strategy == Strategy.TREND_PREDICTION:
        return _evaluate_trend_promql(case, result, region, project, metricstore, time_range)
    elif case.strategy == Strategy.BASELINE_DEVIATION:
        return _evaluate_baseline_promql(case, result, region, project, metricstore, time_range)
    elif case.strategy == Strategy.SLOW_GROWTH:
        return _evaluate_slow_growth_promql(case, result, region, project, metricstore, time_range)
    elif case.strategy == Strategy.THRESHOLD_BREACH:
        return _evaluate_threshold_promql(case, result)
    else:
        result.status = Status.ERROR.value
        result.error = f"Unknown strategy: {case.strategy}"
        return asdict(result)


def _evaluate_trend_promql(case: PredictionCase, result: PredictionResult,
                            region: str, project: str, metricstore: str,
                            time_range: str) -> Dict[str, Any]:
    """趋势预测策略（PromQL）"""
    deriv = 0.0
    predicted = None

    if case.promql_deriv:
        success, data, error = run_promql(region, project, metricstore,
                                           case.promql_deriv, time_range)
        if success:
            rows = parse_results(data)
            if rows:
                deriv = extract_value(rows[0]) or 0.0
                result.deriv_value = deriv

    if case.promql_predict:
        success, data, error = run_promql(region, project, metricstore,
                                           case.promql_predict, time_range)
        if success:
            rows = parse_results(data)
            if rows:
                predicted = extract_value(rows[0])
                if predicted is not None:
                    result.predicted_value = predicted

    # 评估
    predicted_val = predicted if predicted is not None else (result.current_value or 0)
    risk_level, days = evaluate_trend(result.current_value or 0, deriv, predicted_val,
                                       case.warning_threshold, case.critical_threshold)
    result.risk_level = risk_level
    result.days_to_warning = days
    result.status = Status.FIND_PROBLEM.value if risk_level != RiskLevel.NORMAL.value else Status.PASS.value
    return asdict(result)


def _evaluate_baseline_promql(case: PredictionCase, result: PredictionResult,
                               region: str, project: str, metricstore: str,
                               time_range: str) -> Dict[str, Any]:
    """基线偏离策略（PromQL）"""
    offset_1d = None
    avg_7d = None

    if case.promql_offset_1d:
        success, data, error = run_promql(region, project, metricstore,
                                           case.promql_offset_1d, time_range)
        if success:
            rows = parse_results(data)
            if rows:
                offset_1d = extract_value(rows[0])
                if offset_1d is not None:
                    result.baseline_value = offset_1d

    if case.promql_avg_7d:
        success, data, error = run_promql(region, project, metricstore,
                                           case.promql_avg_7d, time_range)
        if success:
            rows = parse_results(data)
            if rows:
                avg_7d = extract_value(rows[0])
                if avg_7d is not None:
                    result.avg_7d_value = avg_7d

    # 评估
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
    return asdict(result)


def _evaluate_slow_growth_promql(case: PredictionCase, result: PredictionResult,
                                  region: str, project: str, metricstore: str,
                                  time_range: str) -> Dict[str, Any]:
    """缓慢增长策略（PromQL）"""
    deriv = 0.0
    predicted_7d = None
    avg_7d = None

    if case.promql_deriv:
        success, data, error = run_promql(region, project, metricstore,
                                           case.promql_deriv, time_range)
        if success:
            rows = parse_results(data)
            if rows:
                deriv = extract_value(rows[0]) or 0.0
                result.deriv_value = deriv

    if case.promql_predict_7d:
        success, data, error = run_promql(region, project, metricstore,
                                           case.promql_predict_7d, time_range)
        if success:
            rows = parse_results(data)
            if rows:
                predicted_7d = extract_value(rows[0])
                if predicted_7d is not None:
                    result.predicted_7d_value = predicted_7d

    if case.promql_avg_7d:
        success, data, error = run_promql(region, project, metricstore,
                                           case.promql_avg_7d, time_range)
        if success:
            rows = parse_results(data)
            if rows:
                avg_7d = extract_value(rows[0])
                if avg_7d is not None:
                    result.avg_7d_value = avg_7d

    # 评估
    current = result.current_value or 0
    pred_7d = predicted_7d if predicted_7d is not None else current
    avg_7d_val = avg_7d if avg_7d is not None else current
    risk_level, days = evaluate_slow_growth(
        current, pred_7d, avg_7d_val,
        case.warning_threshold, case.critical_threshold,
        deriv
    )
    result.risk_level = risk_level
    result.days_to_warning = days
    result.status = Status.FIND_PROBLEM.value if risk_level != RiskLevel.NORMAL.value else Status.PASS.value
    return asdict(result)


def _evaluate_threshold_promql(case: PredictionCase, result: PredictionResult) -> Dict[str, Any]:
    """阈值突破策略（PromQL）"""
    current = result.current_value or 0
    risk_level, exceed = evaluate_threshold(current,
                                             case.warning_threshold,
                                             case.critical_threshold)
    result.risk_level = risk_level
    result.exceed_percent = exceed
    result.status = Status.FIND_PROBLEM.value if risk_level != RiskLevel.NORMAL.value else Status.PASS.value
    return asdict(result)


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
        return asdict(result)

    # 解析 APM metric_set query 结果
    summary = extract_apm_summary(data)
    if not summary:
        result.status = Status.NO_PROBLEM_FOUND.value
        return asdict(result)

    # 提取 entity_id
    eid, ename = extract_apm_entity_id(data)
    result.entity_id = eid or entity_id
    result.entity_name = ename or entity_id

    # 根据策略评估
    if case.strategy == Strategy.THRESHOLD_BREACH:
        return _evaluate_apm_threshold(case, result, summary)
    elif case.strategy == Strategy.BASELINE_DEVIATION:
        return _evaluate_apm_baseline(case, result, summary)
    else:
        return _evaluate_apm_trend(case, result, summary)


def _evaluate_apm_threshold(case: PredictionCase, result: PredictionResult,
                             summary: Dict[str, Dict[str, Optional[float]]]) -> Dict[str, Any]:
    """APM 阈值突破策略"""
    # 从 summary 中提取当前值（mean_value）
    current = None
    for metric_name, stats in summary.items():
        mean_val = stats.get("mean")
        if mean_val is not None:
            current = mean_val
            break

    if current is None:
        result.status = Status.NO_PROBLEM_FOUND.value
        return asdict(result)

    result.current_value = current
    risk_level, exceed = evaluate_threshold(current,
                                             case.warning_threshold,
                                             case.critical_threshold)
    result.risk_level = risk_level
    result.exceed_percent = exceed
    result.status = Status.FIND_PROBLEM.value if risk_level != RiskLevel.NORMAL.value else Status.PASS.value
    return asdict(result)


def _evaluate_apm_baseline(case: PredictionCase, result: PredictionResult,
                            summary: Dict[str, Dict[str, Optional[float]]]) -> Dict[str, Any]:
    """APM 基线偏离策略（使用 mean/max 差值作为简单趋势指标）"""
    current = None
    baseline = None
    for metric_name, stats in summary.items():
        mean_val = stats.get("mean")
        max_val = stats.get("max")
        if mean_val is not None:
            current = mean_val
            # 使用 mean 作为基线近似（无 offset 数据时）
            baseline = mean_val
            break

    if current is None:
        result.status = Status.NO_PROBLEM_FOUND.value
        return asdict(result)

    result.current_value = current
    result.baseline_value = baseline

    # APM 域无 offset 数据，使用 max/mean 比值作为偏离指标
    max_val = None
    for metric_name, stats in summary.items():
        max_val = stats.get("max")
        if max_val is not None:
            break

    if max_val is not None and baseline and baseline > 0:
        ratio = max_val / baseline
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

    return asdict(result)


def _evaluate_apm_trend(case: PredictionCase, result: PredictionResult,
                         summary: Dict[str, Dict[str, Optional[float]]]) -> Dict[str, Any]:
    """APM 趋势预测策略（使用 max-mean 差值作为简单趋势指标）"""
    current = None
    for metric_name, stats in summary.items():
        mean_val = stats.get("mean")
        if mean_val is not None:
            current = mean_val
            break

    if current is None:
        result.status = Status.NO_PROBLEM_FOUND.value
        return asdict(result)

    result.current_value = current

    # 使用 max - mean 差值作为简单趋势指标
    max_val = None
    for metric_name, stats in summary.items():
        max_val = stats.get("max")
        if max_val is not None:
            break

    if max_val is not None and current is not None:
        spread = max_val - current
        # 如果 max 显著高于 mean，说明有上升趋势
        if spread > 0 and max_val > current:
            result.deriv_value = spread / 6.0  # 近似每小时变化量
            result.predicted_value = current + spread
            result.days_to_warning = calculate_days_to_threshold(
                current, result.deriv_value, case.warning_threshold
            )

    # 评估
    deriv = result.deriv_value or 0.0
    predicted = result.predicted_value or current
    risk_level, days = evaluate_trend(current, deriv, predicted,
                                       case.warning_threshold, case.critical_threshold)
    result.risk_level = risk_level
    result.days_to_warning = days
    result.status = Status.FIND_PROBLEM.value if risk_level != RiskLevel.NORMAL.value else Status.PASS.value
    return asdict(result)


# ──────────────────────────────────────────────
# 批量执行
# ──────────────────────────────────────────────

def run_case(case: PredictionCase, region: str = "", project: str = "",
             metricstore: str = "", time_range: str = "",
             workspace: str = "", entity_domain: str = "",
             entity_type: str = "", entity_id: str = "") -> Dict[str, Any]:
    """
    执行单个巡检项

    根据 case 类型自动路由到 PromQL 域或 APM 域。
    """
    # 初始化结果
    result = PredictionResult(
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
        raw_query=case.promql_current or case.metric_names,
    )

    # 判断域类型
    is_apm = bool(case.metric_set_domain)

    if is_apm:
        return _run_apm_case(case, result, workspace, entity_domain,
                             entity_type, entity_id, time_range)
    else:
        return _run_promql_case(case, region, project, metricstore, time_range)


def run_all_cases(cases: List[PredictionCase], region: str = "", project: str = "",
                  metricstore: str = "", time_range: str = "",
                  workspace: str = "", entity_domain: str = "",
                  entity_type: str = "", entity_id: str = "",
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
        )
        results.append(r)

    critical = sum(1 for r in results if r.get("risk_level") == RiskLevel.CRITICAL.value)
    warning = sum(1 for r in results if r.get("risk_level") == RiskLevel.WARNING.value)
    normal = sum(1 for r in results if r.get("risk_level") == RiskLevel.NORMAL.value)
    errors = sum(1 for r in results if r["status"] == Status.ERROR.value)
    no_problem = sum(1 for r in results if r["status"] == Status.NO_PROBLEM_FOUND.value)

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

def build_arg_parser(description: str) -> argparse.ArgumentParser:
    """构建通用 CLI 参数解析器"""
    parser = argparse.ArgumentParser(description=description)
    # PromQL 参数（acs/k8s 域）
    parser.add_argument("--region", default="", help="阿里云 region")
    parser.add_argument("--project", default="", help="SLS project")
    parser.add_argument("--metricstore", default="", help="SLS metricstore")
    # APM 参数
    parser.add_argument("--workspace", default="", help="UModel workspace")
    parser.add_argument("--entity-domain", default="", help="实体域，如 apm")
    parser.add_argument("--entity-type", default="", help="实体类型，如 apm.service")
    parser.add_argument("--entity-id", default="", help="实体 ID")
    # 通用参数
    parser.add_argument("--time-range", default="", help="时间范围，如 last_6h")
    parser.add_argument("--cases", nargs="+", default=None, help="指定巡检项 case_id 列表")
    parser.add_argument("--list-cases", action="store_true", help="列出所有巡检项并退出")
    return parser


def cli_main(cases: List[PredictionCase], description: str) -> None:
    """通用 CLI 入口"""
    parser = build_arg_parser(description)
    args = parser.parse_args()

    # --list-cases
    if args.list_cases:
        print(f"{'case_id':<30} {'severity':<10} {'strategy':<25} {'item':<40} {'description'}")
        print("-" * 150)
        for c in cases:
            print(f"{c.case_id:<30} {c.severity.value:<10} {c.strategy.value:<25} {c.item:<40} {c.description}")
        print(f"\nTotal: {len(cases)} cases")
        sys.exit(0)

    # 判断是 PromQL 域还是 APM 域
    is_apm = any(c.metric_set_domain for c in cases)

    if is_apm:
        if not args.workspace or not args.entity_domain or not args.entity_type or not args.entity_id or not args.time_range:
            parser.error("--workspace, --entity-domain, --entity-type, --entity-id, and --time-range are required for APM cases")
    else:
        if not args.region or not args.project or not args.metricstore or not args.time_range:
            parser.error("--region, --project, --metricstore, and --time-range are required for PromQL cases")

    output = run_all_cases(
        cases=cases,
        region=args.region,
        project=args.project,
        metricstore=args.metricstore,
        time_range=args.time_range,
        workspace=args.workspace,
        entity_domain=args.entity_domain,
        entity_type=args.entity_type,
        entity_id=args.entity_id,
        case_filter=args.cases,
    )
    print(json.dumps(output, indent=2, ensure_ascii=False))
