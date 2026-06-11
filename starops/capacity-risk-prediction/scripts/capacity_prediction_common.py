#!/usr/bin/env python3
"""
capacity_prediction_common.py - 容量风险预测公共引擎

架构模式：数据驱动声明 + 公共引擎
- 业务脚本只声明 PredictionCase 配置（零计算逻辑）
- 本模块承载所有计算：查询、解析、评估、格式化、聚合
- 7 种评估策略：趋势预测、基线偏离、缓慢增长、阈值突破、
  短期波动(holt_winters)、ARIMA 预测(ts_predicate_arma)、
  分解与异常检测(ts_decompose + ts_anomaly_filter)
- 所有数值计算函数为纯函数，同输入同输出

数据源支持：
- acs/k8s 域：starops sls promql query（SLS PromQL 格式）
- apm 域：starops observe metric_set query（APM 预聚合指标）
- log 域：starops sls query（SLS SQL + 时序函数）
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────

class Severity(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class Status(str, Enum):
    PASS = "pass"
    FIND_PROBLEM = "find_problem"
    NO_PROBLEM_FOUND = "no_problem_found"
    ERROR = "error"


class RiskLevel(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    NORMAL = "normal"


class Strategy(str, Enum):
    TREND_PREDICTION = "trend_prediction"
    BASELINE_DEVIATION = "baseline_deviation"
    SLOW_GROWTH = "slow_growth"
    THRESHOLD_BREACH = "threshold_breach"
    SHORT_TERM_FLUCTUATION = "short_term_fluctuation"
    ARIMA_PREDICTION = "arima_prediction"
    DECOMPOSITION_ANOMALY = "decomposition_anomaly"


@dataclass
class PredictionCase:
    """单个巡检项声明（数据驱动，零计算逻辑）"""
    case_id: str
    item: str
    severity: Severity
    strategy: Strategy
    warning_threshold: float
    critical_threshold: float
    description: str = ""
    # PromQL 查询模板（acs/k8s 域使用）
    promql_current: str = ""
    promql_deriv: str = ""
    promql_predict: str = ""
    promql_offset_1d: str = ""
    promql_avg_7d: str = ""
    promql_predict_7d: str = ""
    promql_holt_winters: str = ""
    # APM 域使用（metric_set query）
    metric_set_domain: str = ""
    metric_set_name: str = ""
    metric_names: str = ""
    # Log 域使用（SLS SQL query）
    log_query: str = ""
    log_filter: str = ""
    # 标签提取
    entity_label: str = "instance_id"
    name_label: str = "instance_id"
    # 预测窗口（秒）
    predict_window: int = 86400
    # 数据格式
    data_format: str = "percent"
    # ARIMA 参数（log 域）
    arima_p: int = 1
    arima_d: int = 1
    arima_q: int = 1
    arima_n: int = 24
    arima_step: int = 1
    # 分解参数（log 域）
    decompose_period: int = 24


@dataclass
class PredictionResult:
    """单个巡检项结果"""
    case_id: str
    item: str
    severity: str
    strategy: str
    status: str
    risk_level: Optional[str]
    time_range: str
    entity_id: str
    entity_name: str
    current_value: Optional[float]
    warning_threshold: float
    critical_threshold: float
    deriv_value: Optional[float]
    predicted_value: Optional[float]
    days_to_warning: Optional[float]
    baseline_value: Optional[float]
    deviation_ratio: Optional[float]
    deviation_direction: Optional[str]
    predicted_7d_value: Optional[float]
    avg_7d_value: Optional[float]
    exceed_percent: Optional[float]
    holt_winters_value: Optional[float]
    spike_ratio: Optional[float]
    arima_predicted_value: Optional[float]
    arima_confidence: Optional[float]
    anomaly_score: Optional[float]
    anomaly_count: Optional[int]
    total_points: Optional[int]
    anomaly_ratio: Optional[float]
    trend_value: Optional[float]
    seasonal_value: Optional[float]
    residual_std: Optional[float]
    raw_query: str
    error: str = ""


@dataclass
class BatchPredictionOutput:
    """批量预测输出"""
    total_cases: int
    critical_cases: int
    warning_cases: int
    normal_cases: int
    errors: int
    no_problem_found: int
    has_critical: bool
    has_warning: bool
    results: List[Dict[str, Any]]


# ──────────────────────────────────────────────
# CLI 查询封装
# ──────────────────────────────────────────────

def run_promql(region: str, project: str, metricstore: str, query: str,
               time_range: str) -> Tuple[bool, Any, str]:
    """
    通过 starops sls promql query 调用 PromQL

    Returns:
        (success, parsed_json_or_None, error_message)
    """
    cmd = [
        "starops", "sls", "promql", "query",
        "--region", region,
        "-p", project,
        "-m", metricstore,
        "-q", query,
        "--time-range", time_range,
        "-o", "json",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            return False, None, f"CLI error (rc={result.returncode}): {result.stderr.strip()}"
        try:
            data = json.loads(result.stdout)
            return True, data, ""
        except json.JSONDecodeError as e:
            return False, None, f"JSON parse error: {str(e)}"
    except subprocess.TimeoutExpired:
        return False, None, "CLI timeout (60s)"
    except Exception as e:
        return False, None, f"CLI exception: {str(e)}"


def run_metric_set_query(workspace: str, entity_domain: str, entity_type: str,
                         entity_id: str, metric_set_domain: str, metric_set_name: str,
                         metric_names: str, time_range: str) -> Tuple[bool, Any, str]:
    """
    通过 starops observe metric_set query 获取 APM 指标摘要数据

    Returns:
        (success, parsed_json_or_None, error_message)
    """
    cmd = [
        "starops", "observe", "metric_set", "query",
        "-w", workspace,
        "--entity-domain", entity_domain,
        "--entity-type", entity_type,
        "--entity-id", entity_id,
        "--metric-set-domain", metric_set_domain,
        "--metric-set-name", metric_set_name,
        "--metric-names", metric_names,
        "--time-range", time_range,
        "-o", "json",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            return False, None, f"CLI error (rc={result.returncode}): {result.stderr.strip()}"
        try:
            data = json.loads(result.stdout)
            return True, data, ""
        except json.JSONDecodeError as e:
            return False, None, f"JSON parse error: {str(e)}"
    except subprocess.TimeoutExpired:
        return False, None, "CLI timeout (60s)"
    except Exception as e:
        return False, None, f"CLI exception: {str(e)}"


def run_sls_query(region: str, project: str, logstore: str, query: str,
                  time_range: str, limit: int = 100) -> Tuple[bool, Any, str]:
    """
    通过 starops sls query 执行 SLS SQL 查询

    Returns:
        (success, parsed_json_or_None, error_message)
    """
    cmd = [
        "starops", "sls", "query",
        "--region", region,
        "-p", project,
        "-l", logstore,
        "-q", query,
        "--time-range", time_range,
        "--lines", str(limit),
        "-o", "json",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            return False, None, f"CLI error (rc={result.returncode}): {result.stderr.strip()}"
        try:
            data = json.loads(result.stdout)
            return True, data, ""
        except json.JSONDecodeError as e:
            return False, None, f"JSON parse error: {str(e)}"
    except subprocess.TimeoutExpired:
        return False, None, "CLI timeout (120s)"
    except Exception as e:
        return False, None, f"CLI exception: {str(e)}"


# ──────────────────────────────────────────────
# 解析工具
# ──────────────────────────────────────────────

def extract_labels(row: Dict[str, Any]) -> Dict[str, str]:
    """从行数据中提取 labels（支持 SLS 和 Prometheus 格式）"""
    labels_str = row.get("labels")
    if isinstance(labels_str, str):
        try:
            return json.loads(labels_str)
        except (json.JSONDecodeError, TypeError):
            return {}
    if isinstance(labels_str, dict):
        return labels_str
    metric = row.get("metric")
    if isinstance(metric, dict):
        return metric
    return {}


def extract_value(row: Dict[str, Any]) -> Optional[float]:
    """从行数据中提取数值（支持 SLS 和 Prometheus 格式）"""
    val_field = row.get("value")
    if isinstance(val_field, str):
        try:
            return float(val_field)
        except (ValueError, TypeError):
            return None
    if isinstance(val_field, (list, tuple)) and len(val_field) >= 2:
        try:
            return float(val_field[1])
        except (ValueError, TypeError):
            return None
    values = row.get("values", [])
    if values:
        try:
            last = values[-1]
            if isinstance(last, (list, tuple)) and len(last) >= 2:
                return float(last[1])
        except (ValueError, TypeError, IndexError):
            pass
    return None


def extract_timeseries(row: Dict[str, Any]) -> Tuple[List[float], List[float]]:
    """从行数据中提取时间序列 (timestamps, values)"""
    timestamps = []
    values = []
    values_list = row.get("values", [])
    if not values_list:
        val_field = row.get("value")
        if isinstance(val_field, (list, tuple)) and len(val_field) >= 2:
            try:
                timestamps.append(float(val_field[0]))
                values.append(float(val_field[1]))
            except (ValueError, TypeError):
                pass
        return timestamps, values
    for item in values_list:
        try:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                timestamps.append(float(item[0]))
                values.append(float(item[1]))
        except (ValueError, TypeError):
            continue
    return timestamps, values


def parse_results(data: Any) -> List[Dict[str, Any]]:
    """解析查询返回结果为统一行列表"""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # SLS log query 格式：{"logs": [...], "meta": {...}}
        if "logs" in data and isinstance(data["logs"], list):
            return data["logs"]
        if "results" in data and isinstance(data["results"], list):
            return data["results"]
        if "data" in data:
            inner = data["data"]
            if isinstance(inner, list):
                return inner
            if isinstance(inner, dict):
                return inner.get("result", [])
        if "result" in data:
            return data["result"]
    return []


def group_by_key(rows: List[Dict[str, Any]], key: str) -> Dict[str, List[Dict[str, Any]]]:
    """按指定 key 分组"""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        labels = extract_labels(row)
        k = labels.get(key, "unknown")
        groups.setdefault(k, []).append(row)
    return groups


# ──────────────────────────────────────────────
# APM metric_set query 结果解析
# ──────────────────────────────────────────────

def extract_apm_summary(data: Any) -> Dict[str, Dict[str, Optional[float]]]:
    """从 APM metric_set query 结果中提取摘要数据"""
    result = {}
    if not isinstance(data, list):
        return result
    for row in data:
        metric_name = row.get("metric_name", "")
        summary = row.get("__summary__", {})
        cur_stats = summary.get("cur_statistics", {})
        if metric_name and cur_stats:
            result[metric_name] = {
                "mean": cur_stats.get("mean_value"),
                "max": cur_stats.get("max_value"),
                "min": cur_stats.get("min_value"),
            }
    return result


def extract_apm_entity_id(data: Any) -> Tuple[str, str]:
    """从 APM metric_set query 结果中提取 entity_id 和 entity_name"""
    if isinstance(data, list) and data:
        labels = data[0].get("labels", {})
        if isinstance(labels, str):
            try:
                labels = json.loads(labels)
            except (json.JSONDecodeError, TypeError):
                labels = {}
        entity_id = labels.get("service_id", labels.get("service", ""))
        entity_name = labels.get("service_name", labels.get("service", entity_id))
        return entity_id, entity_name
    return "", ""


# ──────────────────────────────────────────────
# SLS 时序函数结果解析
# ──────────────────────────────────────────────

def parse_sls_ts_json(row: Dict[str, Any], col_name: str) -> List[Dict[str, Any]]:
    """
    解析 SLS 时序函数返回的 JSON 列

    SLS ts_predicate_arma / ts_decompose 等函数返回的列值是 JSON 字符串。
    返回解析后的列表，失败返回空列表。
    """
    raw = row.get(col_name, "")
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return []


def extract_arima_predictions(ts_data: List[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float]]:
    """
    从 ts_predicate_arma 结果中提取最后一个预测值和置信度

    返回 (predicted_value, confidence)
    """
    if not ts_data:
        return None, None
    last = ts_data[-1]
    try:
        pred = float(last.get("y_predict", last.get("predict", 0)))
        # 置信度用 1 - abs(残差/预测值) 近似
        actual = float(last.get("y", last.get("actual", pred)))
        if pred > 0:
            confidence = max(0.0, 1.0 - abs(actual - pred) / pred)
        else:
            confidence = 1.0 if actual == 0 else 0.0
        return pred, confidence
    except (ValueError, TypeError, KeyError):
        return None, None


def extract_decompose_stats(ts_data: List[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    从 ts_decompose 结果中提取趋势、季节、残差标准差

    支持两种格式：
    1. SLS logs 数组格式：每行含 src/trend/season/residual 字段（字符串值）
    2. JSON 列格式：每行含 raw/trend/seasonal/residual 字段

    返回 (avg_trend, avg_seasonal, residual_std)
    """
    if not ts_data:
        return None, None, None
    trends = []
    seasonals = []
    residuals = []
    for point in ts_data:
        try:
            # SLS 格式：src/trend/season/residual
            t = float(point.get("trend", 0))
            s = float(point.get("season", point.get("seasonal", 0)))
            raw = float(point.get("src", point.get("raw", point.get("y", 0))))
            r = raw - t - s
            trends.append(t)
            seasonals.append(s)
            residuals.append(r)
        except (ValueError, TypeError):
            continue
    if not residuals:
        return None, None, None
    avg_trend = sum(trends) / len(trends) if trends else 0.0
    avg_seasonal = sum(seasonals) / len(seasonals) if seasonals else 0.0
    mean_r = sum(residuals) / len(residuals)
    var_r = sum((r - mean_r) ** 2 for r in residuals) / len(residuals)
    residual_std = var_r ** 0.5
    return avg_trend, avg_seasonal, residual_std


def count_anomalies(ts_data: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    从时序分解结果中统计异常点数

    支持两种格式：
    1. SLS logs 数组格式：基于残差 > 2*std 检测异常
    2. 带 anomaly/is_anomaly 标记的格式

    返回 (anomaly_count, total_points)
    """
    if not ts_data:
        return 0, 0
    total = len(ts_data)

    # 先检查是否有显式 anomaly 标记
    has_explicit_anomaly = False
    explicit_count = 0
    for point in ts_data:
        is_anomaly = point.get("anomaly", point.get("is_anomaly", None))
        if is_anomaly is not None:
            has_explicit_anomaly = True
            if isinstance(is_anomaly, str):
                is_anomaly = is_anomaly.lower() in ("true", "1", "yes")
            if is_anomaly:
                explicit_count += 1
    if has_explicit_anomaly:
        return explicit_count, total

    # 无显式标记：基于残差 > 2*std 检测异常（SLS ts_decompose 格式）
    residuals = []
    for point in ts_data:
        try:
            t = float(point.get("trend", 0))
            s = float(point.get("season", point.get("seasonal", 0)))
            raw = float(point.get("src", point.get("raw", point.get("y", 0))))
            r = raw - t - s
            residuals.append(r)
        except (ValueError, TypeError):
            continue
    if len(residuals) < 2:
        return 0, total
    mean_r = sum(residuals) / len(residuals)
    var_r = sum((r - mean_r) ** 2 for r in residuals) / len(residuals)
    std_r = var_r ** 0.5
    if std_r == 0:
        return 0, total
    anomaly_count = sum(1 for r in residuals if abs(r) > 2 * std_r)
    return anomaly_count, total


# ──────────────────────────────────────────────
# 确定性计算：纯函数
# ──────────────────────────────────────────────

def linear_regression(timestamps: List[float], values: List[float]) -> Tuple[float, float]:
    """线性回归计算斜率和截距（纯函数）"""
    n = len(timestamps)
    if n < 2:
        return 0.0, values[0] if values else 0.0
    sum_x = sum(timestamps)
    sum_y = sum(values)
    sum_xy = sum(x * y for x, y in zip(timestamps, values))
    sum_x2 = sum(x * x for x in timestamps)
    denom = n * sum_x2 - sum_x * sum_x
    if denom == 0:
        return 0.0, sum_y / n
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept


def calculate_days_to_threshold(current: float, deriv_per_hour: float,
                                 threshold: float) -> Optional[float]:
    """计算到达阈值剩余天数（纯函数）"""
    if deriv_per_hour <= 0:
        return None
    if current >= threshold:
        return 0.0
    remaining = threshold - current
    hours_to_threshold = remaining / deriv_per_hour
    return hours_to_threshold / 24.0


def evaluate_trend(current: float, deriv_value: float, predicted_value: float,
                   warning_threshold: float, critical_threshold: float) -> Tuple[str, Optional[float]]:
    """趋势预测策略评估（纯函数）"""
    if current >= critical_threshold:
        return RiskLevel.CRITICAL.value, 0.0
    if current >= warning_threshold:
        days = calculate_days_to_threshold(current, deriv_value / 6.0, warning_threshold)
        return RiskLevel.WARNING.value, days
    if deriv_value > 0 and predicted_value >= warning_threshold:
        days = calculate_days_to_threshold(current, deriv_value / 6.0, warning_threshold)
        if days is not None and days <= 7:
            return RiskLevel.WARNING.value, days
        return RiskLevel.NORMAL.value, days
    return RiskLevel.NORMAL.value, None


def evaluate_baseline(current: float, offset_1d: float, avg_7d: float) -> Tuple[str, float, str]:
    """基线偏离策略评估（纯函数）"""
    if offset_1d <= 0:
        return RiskLevel.NORMAL.value, 1.0, "stable"
    deviation_ratio = current / offset_1d
    if deviation_ratio > 2.0:
        return RiskLevel.WARNING.value, deviation_ratio, "spike"
    elif deviation_ratio < 0.5:
        return RiskLevel.WARNING.value, deviation_ratio, "drop"
    else:
        return RiskLevel.NORMAL.value, deviation_ratio, "stable"


def evaluate_slow_growth(current: float, predicted_7d: float, avg_7d: float,
                          warning_threshold: float, critical_threshold: float,
                          deriv_value: float) -> Tuple[str, Optional[float]]:
    """缓慢增长策略评估（纯函数）"""
    if current >= critical_threshold:
        return RiskLevel.CRITICAL.value, 0.0
    if current >= warning_threshold:
        days = calculate_days_to_threshold(current, deriv_value / 6.0, warning_threshold)
        return RiskLevel.WARNING.value, days
    if predicted_7d >= warning_threshold:
        days = calculate_days_to_threshold(current, deriv_value / 6.0, warning_threshold)
        if days is not None and days <= 30:
            return RiskLevel.WARNING.value, days
    return RiskLevel.NORMAL.value, None


def evaluate_threshold(current: float, warning_threshold: float,
                        critical_threshold: float) -> Tuple[str, Optional[float]]:
    """阈值突破策略评估（纯函数）"""
    if current >= critical_threshold:
        exceed = ((current - critical_threshold) / critical_threshold) * 100 if critical_threshold > 0 else 0.0
        return RiskLevel.CRITICAL.value, exceed
    if current >= warning_threshold:
        exceed = ((current - warning_threshold) / warning_threshold) * 100 if warning_threshold > 0 else 0.0
        return RiskLevel.WARNING.value, exceed
    return RiskLevel.NORMAL.value, None


def evaluate_holt_winters(current: float, hw_value: float,
                           warning_threshold: float, critical_threshold: float) -> Tuple[str, Optional[float]]:
    """短期波动策略评估（纯函数）- holt_winters 预测值 vs 当前值"""
    if current <= 0:
        return RiskLevel.NORMAL.value, None
    spike_ratio = hw_value / current if current > 0 else 1.0
    if hw_value >= critical_threshold:
        return RiskLevel.CRITICAL.value, spike_ratio
    if hw_value >= warning_threshold:
        return RiskLevel.WARNING.value, spike_ratio
    if spike_ratio > 2.0:
        return RiskLevel.WARNING.value, spike_ratio
    return RiskLevel.NORMAL.value, spike_ratio


def evaluate_arima(current: float, predicted: float, confidence: float,
                    warning_threshold: float, critical_threshold: float) -> Tuple[str, Optional[float]]:
    """ARIMA 预测策略评估（纯函数）"""
    if current <= 0:
        return RiskLevel.NORMAL.value, None
    ratio = predicted / current if current > 0 else 1.0
    if ratio >= critical_threshold:
        return RiskLevel.CRITICAL.value, ratio
    if ratio >= warning_threshold:
        return RiskLevel.WARNING.value, ratio
    return RiskLevel.NORMAL.value, ratio


def evaluate_decomposition_anomaly(residual_std: float, anomaly_count: int,
                                    total_points: int, anomaly_std_threshold: float,
                                    anomaly_ratio_warning: float,
                                    anomaly_ratio_critical: float) -> Tuple[str, Optional[float], Optional[float]]:
    """分解与异常检测策略评估（纯函数）"""
    anomaly_ratio = anomaly_count / total_points if total_points > 0 else 0.0
    if anomaly_ratio >= anomaly_ratio_critical or residual_std >= anomaly_std_threshold * 2:
        return RiskLevel.CRITICAL.value, anomaly_ratio, residual_std
    if anomaly_ratio >= anomaly_ratio_warning or residual_std >= anomaly_std_threshold:
        return RiskLevel.WARNING.value, anomaly_ratio, residual_std
    return RiskLevel.NORMAL.value, anomaly_ratio, residual_std


# ──────────────────────────────────────────────
# CLI 入口工具
# ──────────────────────────────────────────────

def build_base_arg_parser(description: str) -> argparse.ArgumentParser:
    """构建基础 CLI 参数解析器"""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--time-range", default="", help="时间范围，如 last_6h")
    parser.add_argument("--cases", nargs="+", default=None, help="指定巡检项 case_id 列表")
    parser.add_argument("--list-cases", action="store_true", help="列出所有巡检项并退出")
    return parser


def add_promql_args(parser: argparse.ArgumentParser) -> None:
    """添加 PromQL 域参数"""
    parser.add_argument("--region", default="", help="阿里云 region")
    parser.add_argument("--project", default="", help="SLS project")
    parser.add_argument("--metricstore", default="", help="SLS metricstore")


def add_apm_args(parser: argparse.ArgumentParser) -> None:
    """添加 APM 域参数"""
    parser.add_argument("--workspace", default="", help="UModel workspace")
    parser.add_argument("--entity-domain", default="", help="实体域，如 apm")
    parser.add_argument("--entity-type", default="", help="实体类型，如 apm.service")
    parser.add_argument("--entity-id", default="", help="实体 ID")


def add_log_args(parser: argparse.ArgumentParser) -> None:
    """添加 Log 域参数"""
    parser.add_argument("--region", default="", help="阿里云 region")
    parser.add_argument("--logstore-project", default="", help="SLS Project for logstore")
    parser.add_argument("--logstore", default="", help="LogStore 名称")
    parser.add_argument("--log-filter", default="", help="日志过滤条件")


def print_cases(cases: List[PredictionCase]) -> None:
    """打印巡检项列表"""
    print(f"{'case_id':<30} {'severity':<10} {'strategy':<28} {'item':<40} {'description'}")
    print("-" * 160)
    for c in cases:
        print(f"{c.case_id:<30} {c.severity.value:<10} {c.strategy.value:<28} {c.item:<40} {c.description}")
    print(f"\nTotal: {len(cases)} cases")
