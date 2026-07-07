#!/usr/bin/env python3
"""
rds_inspection_common.py - RDS 巡检公共引擎（增强版）

架构模式：数据驱动声明 + 公共引擎
- 业务脚本只声明 InspectionCase 配置（零计算逻辑）
- 本模块承载所有计算：查询、解析、评估、格式化、聚合、采样、拓扑查询
- 4 类确定性计算：单位换算、聚合计算、阈值+持续时间、输出标准化
- 所有数值计算函数为纯函数，同输入同输出

增强字段：
- investigation_hints: 巡检项级别的调查提示
- raw_samples/topology/investigation_hints/trend/confidence/evidence_sources/umodel_context: 异常资源级别的增强信息
- 数据源策略：优先 SLS PromQL，失败时回退到 CloudMonitor
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


class CompareOp(str, Enum):
    GT = "gt"       # value > threshold
    LT = "lt"       # value < threshold
    GTE = "gte"     # value >= threshold
    LTE = "lte"     # value <= threshold
    EQ = "eq"       # value == threshold


@dataclass
class InspectionCase:
    """单个巡检项声明（数据驱动，零计算逻辑）"""
    case_id: str
    item: str
    severity: Severity
    promql: str = ""
    log_query: str = ""
    log_project: str = ""
    logstore: str = ""
    threshold: float = 0.0
    duration: int = 0          # 持续秒数，0 表示瞬时判断
    compare: CompareOp = CompareOp.GT
    data_format: str = "raw"   # raw / percent / bytes / ms / s
    description: str = ""
    # 用于从 labels 中提取 entity_id 的 key
    entity_label: str = "instance_id"
    # 用于从 labels 中提取 entity_name 的 key
    name_label: str = "instance_id"
    # 日志脚本专用
    log_source: str = ""       # 日志来源描述
    # CloudMonitor 指标名（用于回退）
    cloudmonitor_metric: str = ""
    # 调查提示（巡检项级别）
    investigation_hints: List[str] = field(default_factory=list)


@dataclass
class AbnormalResource:
    """异常资源详情（增强版）"""
    entity_id: str
    entity_name: str
    metric_value: Any
    threshold: Any
    raw_samples: list = field(default_factory=list)
    topology: dict = field(default_factory=lambda: {"upstream": [], "downstream": []})
    investigation_hints: List[str] = field(default_factory=list)
    trend: dict = field(default_factory=dict)
    confidence: str = "low"
    evidence_sources: List[str] = field(default_factory=list)
    umodel_context: dict = field(default_factory=dict)


@dataclass
class InspectionResult:
    """单个巡检项结果"""
    case_id: str
    item: str
    severity: str
    status: str
    duration_seconds: int
    time_range: str
    total_entities: int
    abnormal_count: int
    abnormal_resources: List[Dict[str, Any]]
    raw_query: str
    data_source: str = ""
    error: str = ""


@dataclass
class BatchInspectionOutput:
    """批量巡检输出"""
    total_cases: int
    passed: int
    find_problem_cases: int
    errors: int
    no_problem_found: int
    has_find_problem: bool
    results: List[Dict[str, Any]]


# ──────────────────────────────────────────────
# 确定性计算：单位换算（纯函数）
# ──────────────────────────────────────────────

def format_bytes(value: float) -> str:
    """字节单位换算，同输入同输出"""
    if value < 0:
        return f"{value:.2f} B"
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if abs(value) < 1024.0:
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} EB"


def format_percent(value: float) -> str:
    """百分比格式化，同输入同输出"""
    return f"{value:.2f}%"


def format_ms(value: float) -> str:
    """毫秒格式化"""
    return f"{value:.2f}ms"


def format_s(value: float) -> str:
    """秒格式化"""
    return f"{value:.2f}s"


def format_value(value: float, data_format: str) -> str:
    """根据 data_format 格式化数值"""
    if data_format == "percent":
        return format_percent(value)
    elif data_format == "bytes":
        return format_bytes(value)
    elif data_format == "ms":
        return format_ms(value)
    elif data_format == "s":
        return format_s(value)
    return f"{value:.2f}"


# ──────────────────────────────────────────────
# CLI 查询封装
# ──────────────────────────────────────────────

def run_promql(region: str, project: str, metricstore: str, query: str,
               time_range: str, range_flag: bool = True) -> Tuple[bool, Any, str]:
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


def run_cloudmonitor(region: str, namespace: str, metric_name: str,
                     time_range: str, instance_id: str = "") -> Tuple[bool, Any, str]:
    """
    通过 starops observe acm_basic metric data 调用 CloudMonitor 指标

    Returns:
        (success, parsed_json_or_None, error_message)
    """
    cmd = [
        "starops", "observe", "acm_basic", "metric", "data",
        "--region", region,
        "--namespace", namespace,
        "--metric-name", metric_name,
        "--time-range", time_range,
        "-o", "json",
    ]
    if instance_id:
        cmd.extend(["--instance-id", instance_id])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            return False, None, f"CloudMonitor CLI error (rc={result.returncode}): {result.stderr.strip()}"
        try:
            data = json.loads(result.stdout)
            return True, data, ""
        except json.JSONDecodeError as e:
            return False, None, f"CloudMonitor JSON parse error: {str(e)}"
    except subprocess.TimeoutExpired:
        return False, None, "CloudMonitor CLI timeout (60s)"
    except Exception as e:
        return False, None, f"CloudMonitor CLI exception: {str(e)}"


def run_log_query(region: str, project: str, logstore: str, query: str,
                  time_range: str, limit: int = 100) -> Tuple[bool, Any, str]:
    """
    通过 starops sls query 调用日志查询

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


def query_topology(entity_type: str, entity_id: str, depth: int = 1,
                   direction: str = "both") -> Dict[str, Any]:
    """
    通过 starops umodel topology 查询上下游实体

    Returns:
        {"upstream": [...], "downstream": [...]} 或 {"upstream": [], "downstream": [], "error": "..."}
    """
    cmd = [
        "starops", "umodel", "topology",
        "--entity-type", entity_type,
        "--entity-id", entity_id,
        "--depth", str(depth),
        "--direction", direction,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            return {
                "upstream": [],
                "downstream": [],
                "error": f"topology CLI error (rc={result.returncode}): {result.stderr.strip()}"
            }
        try:
            data = json.loads(result.stdout)
            upstream = data.get("upstream", data.get("upstream_entities", []))
            downstream = data.get("downstream", data.get("downstream_entities", []))
            return {"upstream": upstream, "downstream": downstream}
        except json.JSONDecodeError:
            return {
                "upstream": [],
                "downstream": [],
                "error": "topology JSON parse failed"
            }
    except subprocess.TimeoutExpired:
        return {"upstream": [], "downstream": [], "error": "topology CLI timeout (30s)"}
    except FileNotFoundError:
        return {"upstream": [], "downstream": [], "error": "starops CLI not found"}
    except Exception as e:
        return {"upstream": [], "downstream": [], "error": f"topology exception: {str(e)}"}


def query_trend(region: str, project: str, metricstore: str, query: str,
                time_range: str) -> Tuple[bool, List[Dict[str, Any]], str]:
    """
    查询趋势数据（返回时间序列）

    Returns:
        (success, series_list, error_message)
    """
    success, data, error = run_promql(region, project, metricstore, query, time_range, range_flag=True)
    if not success:
        return False, [], error

    rows = parse_results(data)
    return True, rows, ""


# ──────────────────────────────────────────────
# 解析工具
# ──────────────────────────────────────────────

def parse_labels(label_str: str) -> Dict[str, str]:
    """
    解析 Prometheus labels 字符串为字典
    输入示例: {instance_id="rm-xxx",region="cn-hangzhou"}
    """
    labels = {}
    if not label_str or label_str == "{}":
        return labels
    inner = label_str.strip("{}")
    for part in inner.split(","):
        part = part.strip()
        if "=" in part:
            key, val = part.split("=", 1)
            labels[key.strip()] = val.strip().strip('"')
    return labels


def parse_results(data: Any) -> List[Dict[str, Any]]:
    """
    解析 PromQL 返回结果为统一行列表

    支持格式：
    - {"status": "success", "data": {"resultType": "vector", "result": [...]}}
    - {"status": "success", "data": {"resultType": "matrix", "result": [...]}}
    - 直接返回列表
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
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
        metric = row.get("metric", {})
        k = metric.get(key, "unknown")
        groups.setdefault(k, []).append(row)
    return groups


def extract_raw_samples(series: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
    """
    从时间序列结果中抽取最近 N 条原始样本

    输入 series 格式:
    {"metric": {...}, "values": [[ts1, val1], [ts2, val2], ...]}
    或 {"metric": {...}, "value": [ts, val]} (instant)

    返回: [{"ts": ..., "value": ...}, ...]
    """
    samples = []
    values = series.get("values", [])
    if not values:
        val = series.get("value")
        if val and len(val) >= 2:
            return [{"ts": val[0], "value": val[1]}]
        return []

    sorted_values = sorted(values, key=lambda x: float(x[0]))
    for ts, val in sorted_values[-limit:]:
        samples.append({"ts": ts, "value": val})
    return samples


# ──────────────────────────────────────────────
# 评估逻辑
# ──────────────────────────────────────────────

def calc_sustained_seconds(series: Dict[str, Any], threshold: float,
                            compare: CompareOp) -> int:
    """
    计算满足阈值条件的持续秒数

    从时间序列 values 中计算连续满足条件的最大持续时间。
    纯函数，无时间依赖。
    """
    values = series.get("values", [])
    if not values:
        return 0

    sorted_values = sorted(values, key=lambda x: float(x[0]))
    max_sustained = 0
    current_sustained = 0
    prev_ts = None

    for ts_str, val_str in sorted_values:
        ts = float(ts_str)
        val = float(val_str)

        condition_met = False
        if compare == CompareOp.GT:
            condition_met = val > threshold
        elif compare == CompareOp.LT:
            condition_met = val < threshold
        elif compare == CompareOp.GTE:
            condition_met = val >= threshold
        elif compare == CompareOp.LTE:
            condition_met = val <= threshold
        elif compare == CompareOp.EQ:
            condition_met = val == threshold

        if condition_met:
            if prev_ts is not None:
                current_sustained += (ts - prev_ts)
            else:
                current_sustained = 0
            max_sustained = max(max_sustained, current_sustained)
        else:
            current_sustained = 0

        prev_ts = ts

    return int(max_sustained)


def compare_value(value: float, threshold: float, compare: CompareOp) -> bool:
    """纯函数：比较值与阈值"""
    if compare == CompareOp.GT:
        return value > threshold
    elif compare == CompareOp.LT:
        return value < threshold
    elif compare == CompareOp.GTE:
        return value >= threshold
    elif compare == CompareOp.LTE:
        return value <= threshold
    elif compare == CompareOp.EQ:
        return value == threshold
    return False


def calc_confidence(value: float, threshold: float, compare: CompareOp,
                    duration: int, sustained_seconds: int) -> str:
    """
    计算置信度标签，基于偏离度、持续时间、数据完整性

    纯函数，同输入同输出。
    """
    # 偏离度：值与阈值的相对差距
    if threshold == 0:
        deviation_ratio = 1.0 if value != 0 else 0.0
    else:
        deviation_ratio = abs(value - threshold) / abs(threshold)

    # 偏离度得分（0-0.5）
    deviation_score = min(0.5, deviation_ratio * 0.5)

    # 持续时间得分（0-0.3）
    if duration == 0:
        duration_score = 0.3  # 瞬时判断给满分
    else:
        duration_ratio = sustained_seconds / duration if duration > 0 else 0
        duration_score = min(0.3, duration_ratio * 0.3)

    # 数据完整性得分（固定 0.2，假设数据完整）
    completeness_score = 0.2

    confidence = deviation_score + duration_score + completeness_score
    score = round(min(1.0, max(0.0, confidence)), 2)
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def build_investigation_hints(case: InspectionCase, value: float) -> List[str]:
    """
    构建调查提示（基于巡检项定义和当前值）

    纯函数，同输入同输出。
    """
    hints = []

    # 添加巡检项级别的调查提示
    if case.investigation_hints:
        hints.extend(case.investigation_hints)

    # 根据偏离度添加额外提示
    if case.threshold > 0:
        deviation_pct = abs(value - case.threshold) / case.threshold * 100
        if deviation_pct > 50:
            hints.append(f"指标偏离阈值 {deviation_pct:.1f}%，建议优先处理")
        elif deviation_pct > 20:
            hints.append(f"指标偏离阈值 {deviation_pct:.1f}%，建议关注")

    return hints


def build_evidence_sources(case: InspectionCase, data_source: str) -> List[str]:
    """
    构建证据来源列表

    纯函数，同输入同输出。
    """
    sources = []

    if data_source == "promql":
        sources.append(f"PromQL: {case.promql}")
    elif data_source == "cloudmonitor":
        sources.append(f"CloudMonitor: {case.cloudmonitor_metric}")
    elif data_source == "log":
        sources.append(f"Log Query: {case.log_query}")

    if case.duration > 0:
        sources.append(f"Duration Check: {case.duration}s")

    return sources


def evaluate(rows: List[Dict[str, Any]], case: InspectionCase,
             entity_label: str = "instance_id",
             name_label: str = "instance_id") -> Tuple[int, List[AbnormalResource]]:
    """
    评估一组行数据，返回 (总实体数, 异常资源列表)

    对于瞬时查询（duration=0），直接比较 value 与 threshold。
    对于持续时间查询（duration>0），计算 sustained seconds 并与 duration 比较。
    """
    total = len(rows)
    abnormal: List[AbnormalResource] = []

    for row in rows:
        metric = row.get("metric", {})
        entity_id = metric.get(entity_label, "unknown")
        entity_name = metric.get(name_label, entity_id)

        val_field = row.get("value")
        if val_field and len(val_field) >= 2:
            value = float(val_field[1])
        else:
            values = row.get("values", [])
            if values:
                value = float(values[-1][1])
            else:
                continue

        if compare_value(value, case.threshold, case.compare):
            sustained = 0
            if case.duration > 0:
                sustained = calc_sustained_seconds(row, case.threshold, case.compare)
                if sustained < case.duration:
                    continue

            abnormal.append(AbnormalResource(
                entity_id=entity_id,
                entity_name=entity_name,
                metric_value=value,
                threshold=case.threshold,
            ))

    return total, abnormal


# ──────────────────────────────────────────────
# 批量执行
# ──────────────────────────────────────────────

def run_case(case: InspectionCase, region: str, project: str, metricstore: str,
             time_range: str, limit: int = 10, audit_logstore: str = "",
             entity_type: str = "RDS", cloudmonitor_namespace: str = "") -> Dict[str, Any]:
    """
    执行单个巡检项

    数据源策略：
    1. 日志类巡检：使用 run_log_query
    2. 指标类巡检：优先 SLS PromQL，失败时回退到 CloudMonitor（如果提供了 cloudmonitor_namespace）
    3. 仅在异常项填充增强字段（raw_samples/topology/investigation_hints/trend/confidence/evidence_sources/umodel_context）
    """
    result = InspectionResult(
        case_id=case.case_id,
        item=case.item,
        severity=case.severity.value,
        status=Status.NO_PROBLEM_FOUND.value,
        duration_seconds=case.duration,
        time_range=time_range,
        total_entities=0,
        abnormal_count=0,
        abnormal_resources=[],
        raw_query=case.promql or case.log_query or case.cloudmonitor_metric,
    )

    # 日志类巡检项
    if case.log_query and (case.logstore or audit_logstore):
        log_project = case.log_project or project
        logstore = case.logstore
        if audit_logstore:
            logstore = audit_logstore

        success, data, error = run_log_query(
            region=region,
            project=log_project,
            logstore=logstore,
            query=case.log_query,
            time_range=time_range,
            limit=limit * 10,
        )
        if not success:
            result.status = Status.ERROR.value
            result.error = error
            return asdict(result)

        rows = parse_results(data)
        result.total_entities = len(rows)

        count = len(rows)
        if compare_value(float(count), case.threshold, case.compare):
            result.status = Status.FIND_PROBLEM.value
            result.abnormal_count = 1

            # 填充 raw_samples（脱敏）
            raw_samples = []
            for row_item in rows[:limit]:
                sample = {}
                for k, v in row_item.items():
                    if isinstance(v, str) and len(v) > 100:
                        v = v[:100] + "..."
                    if k.lower() in ("account", "ip", "password", "secret", "token"):
                        continue
                    sample[k] = v
                raw_samples.append(sample)

            # 填充增强字段
            topo = query_topology(entity_type, "logstore:" + logstore, depth=1, direction="both")
            investigation_hints = build_investigation_hints(case, float(count))
            evidence_sources = build_evidence_sources(case, "log")
            confidence = calc_confidence(float(count), case.threshold, case.compare, case.duration, 0)

            result.abnormal_resources = [{
                "entity_id": "logstore:" + logstore,
                "entity_name": logstore,
                "metric_value": count,
                "threshold": case.threshold,
                "raw_samples": raw_samples,
                "topology": topo,
                "investigation_hints": investigation_hints,
                "trend": {},
                "confidence": confidence,
                "evidence_sources": evidence_sources,
                "umodel_context": {},
            }]
        else:
            result.status = Status.PASS.value

        return asdict(result)

    # 指标类巡检项
    data_source = ""
    rows = []

    # 优先尝试 SLS PromQL
    if case.promql:
        success, data, error = run_promql(
            region=region,
            project=project,
            metricstore=metricstore,
            query=case.promql,
            time_range=time_range,
        )
        if success:
            rows = parse_results(data)
            data_source = "promql"
        elif not cloudmonitor_namespace:
            # PromQL 失败且没有 CloudMonitor 回退
            result.status = Status.ERROR.value
            result.error = error
            return asdict(result)

    # 回退到 CloudMonitor
    if not rows and cloudmonitor_namespace and case.cloudmonitor_metric:
        success, data, error = run_cloudmonitor(
            region=region,
            namespace=cloudmonitor_namespace,
            metric_name=case.cloudmonitor_metric,
            time_range=time_range,
        )
        if success:
            rows = parse_results(data)
            data_source = "cloudmonitor"
        else:
            result.status = Status.ERROR.value
            result.error = f"PromQL failed and CloudMonitor fallback failed: {error}"
            return asdict(result)

    if not rows:
        result.status = Status.ERROR.value
        result.error = "no metric data returned from configured data source"
        return asdict(result)

    result.data_source = data_source
    total, abnormal = evaluate(rows, case, case.entity_label, case.name_label)
    result.total_entities = total
    result.abnormal_count = len(abnormal)

    if abnormal:
        result.status = Status.FIND_PROBLEM.value
        for ar in abnormal:
            # 找到对应的 row
            matching_row = None
            for row in rows:
                m = row.get("metric", {})
                eid = m.get(case.entity_label, "unknown")
                if eid == ar.entity_id:
                    matching_row = row
                    break

            # 填充增强字段（仅异常项）
            raw_samples = []
            if matching_row:
                raw_samples = extract_raw_samples(matching_row, limit=limit)

            topo = query_topology(entity_type, ar.entity_id, depth=1, direction="both")
            investigation_hints = build_investigation_hints(case, ar.metric_value)
            evidence_sources = build_evidence_sources(case, data_source)

            sustained = 0
            if case.duration > 0 and matching_row:
                sustained = calc_sustained_seconds(matching_row, case.threshold, case.compare)

            confidence = calc_confidence(ar.metric_value, case.threshold, case.compare, case.duration, sustained)

            result.abnormal_resources.append({
                "entity_id": ar.entity_id,
                "entity_name": ar.entity_name,
                "metric_value": ar.metric_value,
                "threshold": ar.threshold,
                "raw_samples": raw_samples,
                "topology": topo,
                "investigation_hints": investigation_hints,
                "trend": {},
                "confidence": confidence,
                "evidence_sources": evidence_sources,
                "umodel_context": {},
            })
    else:
        result.status = Status.PASS.value

    return asdict(result)


def run_all_cases(cases: List[InspectionCase], region: str, project: str,
                  metricstore: str, time_range: str, limit: int = 10,
                  audit_logstore: str = "", entity_type: str = "RDS",
                  cloudmonitor_namespace: str = "",
                  case_filter: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    批量执行所有巡检项
    """
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
            limit=limit,
            audit_logstore=audit_logstore,
            entity_type=entity_type,
            cloudmonitor_namespace=cloudmonitor_namespace,
        )
        results.append(r)

    passed = sum(1 for r in results if r["status"] == Status.PASS.value)
    find_problem = sum(1 for r in results if r["status"] == Status.FIND_PROBLEM.value)
    errors = sum(1 for r in results if r["status"] == Status.ERROR.value)
    no_problem = sum(1 for r in results if r["status"] == Status.NO_PROBLEM_FOUND.value)

    output = BatchInspectionOutput(
        total_cases=len(results),
        passed=passed,
        find_problem_cases=find_problem,
        errors=errors,
        no_problem_found=no_problem,
        has_find_problem=(find_problem > 0),
        results=results,
    )
    return asdict(output)


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

def build_arg_parser(description: str) -> argparse.ArgumentParser:
    """构建通用 CLI 参数解析器"""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--region", default="", help="阿里云 region")
    parser.add_argument("--project", default="", help="SLS project")
    parser.add_argument("--metricstore", default="", help="SLS metricstore")
    parser.add_argument("--time-range", default="", help="时间范围，如 last_1h")
    parser.add_argument("--limit", type=int, default=10, help="raw_samples 最大条数 (default: 10)")
    parser.add_argument("--cases", nargs="+", default=None, help="指定巡检项 case_id 列表")
    parser.add_argument("--list-cases", action="store_true", help="列出所有巡检项并退出")
    parser.add_argument("--audit-logstore", default="", help="审计日志 logstore（日志脚本必填）")
    parser.add_argument("--cloudmonitor-namespace", default="", help="CloudMonitor namespace（用于回退）")
    return parser


def cli_main(cases: List[InspectionCase], description: str,
             entity_type: str = "RDS") -> None:
    """通用 CLI 入口"""
    parser = build_arg_parser(description)
    args = parser.parse_args()

    # --list-cases
    if args.list_cases:
        print(f"{'case_id':<35} {'severity':<10} {'item':<50} {'description'}")
        print("-" * 140)
        for c in cases:
            print(f"{c.case_id:<35} {c.severity.value:<10} {c.item:<50} {c.description}")
        print(f"\nTotal: {len(cases)} cases")
        sys.exit(0)

    # 校验必填参数
    if not args.region or not args.project or not args.metricstore or not args.time_range:
        parser.error("--region, --project, --metricstore, and --time-range are required for execution")

    # 日志脚本校验
    if args.audit_logstore == "" and any(c.log_query for c in cases):
        output = BatchInspectionOutput(
            total_cases=len(cases),
            passed=0,
            find_problem_cases=0,
            errors=len(cases),
            no_problem_found=0,
            has_find_problem=False,
            results=[{
                "case_id": c.case_id,
                "item": c.item,
                "severity": c.severity.value,
                "status": Status.ERROR.value,
                "duration_seconds": c.duration,
                "time_range": args.time_range,
                "total_entities": 0,
                "abnormal_count": 0,
                "abnormal_resources": [],
                "raw_query": c.log_query,
                "error": "--audit-logstore is required for log inspection cases",
            } for c in cases if c.log_query],
        )
        print(json.dumps(asdict(output), indent=2, ensure_ascii=False))
        sys.exit(1)

    output = run_all_cases(
        cases=cases,
        region=args.region,
        project=args.project,
        metricstore=args.metricstore,
        time_range=args.time_range,
        limit=args.limit,
        audit_logstore=args.audit_logstore,
        entity_type=entity_type,
        cloudmonitor_namespace=args.cloudmonitor_namespace,
        case_filter=args.cases,
    )
    print(json.dumps(output, indent=2, ensure_ascii=False))
