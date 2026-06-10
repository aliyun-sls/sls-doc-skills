#!/usr/bin/env python3
"""
capacity_prediction_common.py - 容量风险预测公共引擎

架构模式：数据驱动声明 + 公共引擎
- 业务脚本只声明 PredictionCase 配置（零计算逻辑）
- 本模块承载所有计算：查询、解析、评估、格式化、聚合
- 4 种评估策略：趋势预测、基线偏离、缓慢增长、阈值突破
- 所有数值计算函数为纯函数，同输入同输出

数据源支持：
- acs/k8s 域：starops sls promql query（SLS PromQL 格式）
- apm 域：starops observe metric_set query（APM 预聚合指标）
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
    # APM 域使用（metric_set query）
    metric_set_domain: str = ""
    metric_set_name: str = ""
    metric_names: str = ""
    # 标签提取
    entity_label: str = "instance_id"
    name_label: str = "instance_id"
    # 预测窗口（秒）
    predict_window: int = 86400  # 默认 1 天
    # 数据格式
    data_format: str = "percent"  # percent / bytes / ms / raw


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
            cmd,
            capture_output=True,
            text=True,
            timeout=60
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

    APM 域使用 metric_set query 而非 entity metric-data，
    因为后者对 APM 服务可能返回 null。

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
            cmd,
            capture_output=True,
            text=True,
            timeout=60
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


# ──────────────────────────────────────────────
# 解析工具（支持 SLS 格式 + Prometheus 标准格式）
# ──────────────────────────────────────────────

def extract_labels(row: Dict[str, Any]) -> Dict[str, str]:
    """
    从行数据中提取 labels

    支持两种格式：
    - SLS 格式：labels 是 JSON 字符串 '{"key": "value"}'
    - Prometheus 格式：metric 是 dict {"key": "value"}
    """
    # SLS 格式：labels 字段是 JSON 字符串
    labels_str = row.get("labels")
    if isinstance(labels_str, str):
        try:
            return json.loads(labels_str)
        except (json.JSONDecodeError, TypeError):
            return {}
    if isinstance(labels_str, dict):
        return labels_str

    # Prometheus 格式：metric 字段
    metric = row.get("metric")
    if isinstance(metric, dict):
        return metric

    return {}


def extract_value(row: Dict[str, Any]) -> Optional[float]:
    """
    从行数据中提取数值

    支持两种格式：
    - SLS 格式：value 是字符串 "98.329"
    - Prometheus 格式：value 是 [timestamp, value] 列表
    """
    val_field = row.get("value")

    # SLS 格式：value 是字符串
    if isinstance(val_field, str):
        try:
            return float(val_field)
        except (ValueError, TypeError):
            return None

    # Prometheus 格式：value 是 [ts, val] 列表
    if isinstance(val_field, (list, tuple)) and len(val_field) >= 2:
        try:
            return float(val_field[1])
        except (ValueError, TypeError):
            return None

    # 尝试从 values 列表中取最后一个
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
    """
    从行数据中提取时间序列 (timestamps, values)

    支持 Prometheus matrix 格式：values = [[ts, val], ...]
    """
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
    """
    解析查询返回结果为统一行列表

    支持格式：
    1. SLS PromQL 格式：
       {"meta": {...}, "results": [{"labels": "{...}", "time": "...", "value": "98.3"}], "type": "vector"}
    2. Prometheus 标准格式：
       {"status": "success", "data": {"resultType": "vector", "result": [...]}}
    3. APM metric_set query 格式：
       [{"metric_name": "...", "__summary__": {...}, "labels": {...}}]
    4. 直接返回列表
    """
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        # SLS PromQL 格式：results 字段
        if "results" in data and isinstance(data["results"], list):
            return data["results"]

        # Prometheus 标准格式：data.result
        if "data" in data:
            inner = data["data"]
            if isinstance(inner, list):
                return inner
            if isinstance(inner, dict):
                return inner.get("result", [])

        # 直接 result 字段
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
    """
    从 APM metric_set query 结果中提取摘要数据

    APM metric_set query 返回格式：
    [
      {
        "metric_name": "error_rate",
        "__summary__": {
          "cur_statistics": {
            "mean_value": 3.72,
            "max_value": 10.0,
            "min_value": 0.5
          }
        },
        "labels": {"service": "xxx"}
      }
    ]

    返回：{metric_name: {"mean": float, "max": float, "min": float}}
    """
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
    """
    从 APM metric_set query 结果中提取 entity_id 和 entity_name

    返回：(entity_id, entity_name)
    """
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
# 确定性计算：纯函数
# ──────────────────────────────────────────────

def linear_regression(timestamps: List[float], values: List[float]) -> Tuple[float, float]:
    """
    线性回归计算斜率和截距

    纯函数，同输入同输出。
    返回 (slope, intercept)
    """
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
    """
    计算到达阈值剩余天数

    纯函数，同输入同输出。
    deriv_per_hour: 每小时变化量
    返回剩余天数，无趋势或已超阈值时返回 None
    """
    if deriv_per_hour <= 0:
        return None
    if current >= threshold:
        return 0.0
    remaining = threshold - current
    hours_to_threshold = remaining / deriv_per_hour
    return hours_to_threshold / 24.0


def evaluate_trend(current: float, deriv_value: float, predicted_value: float,
                   warning_threshold: float, critical_threshold: float) -> Tuple[str, Optional[float]]:
    """
    趋势预测策略评估

    纯函数，同输入同输出。
    返回 (risk_level, days_to_warning)
    """
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
    """
    基线偏离策略评估

    纯函数，同输入同输出。
    返回 (risk_level, deviation_ratio, deviation_direction)
    """
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
    """
    缓慢增长策略评估

    纯函数，同输入同输出。
    返回 (risk_level, days_to_warning)
    """
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
    """
    阈值突破策略评估

    纯函数，同输入同输出。
    返回 (risk_level, exceed_percent)
    """
    if current >= critical_threshold:
        exceed = ((current - critical_threshold) / critical_threshold) * 100
        return RiskLevel.CRITICAL.value, exceed
    if current >= warning_threshold:
        exceed = ((current - warning_threshold) / warning_threshold) * 100
        return RiskLevel.WARNING.value, exceed
    return RiskLevel.NORMAL.value, None


# ──────────────────────────────────────────────
# PromQL 域（acs/k8s）执行逻辑
# ──────────────────────────────────────────────



# Re-export from engine for backward compatibility
# Business scripts import cli_main from here
def _lazy_import_engine():
    from capacity_prediction_engine import cli_main as _cli_main, run_case, run_all_cases, build_arg_parser
    return _cli_main, run_case, run_all_cases, build_arg_parser

def cli_main(cases, description=""):
    _cli_main, _, _, _ = _lazy_import_engine()
    return _cli_main(cases, description)

