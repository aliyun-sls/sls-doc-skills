#!/usr/bin/env python3
"""
rds-trend-inspection.py - RDS 趋势巡检（6 项）

业务脚本：只声明 InspectionCase 配置，零计算逻辑。
所有计算由 rds_inspection_common.py 公共引擎承载。

趋势巡检：分析 7 天 / 15 天趋势，识别增长速率与趋势方向。

CloudMonitor 指标名映射：
- DiskUsage: 磁盘使用率趋势
- IOPSUsage: IOPS 使用率趋势
- CpuUsage: CPU 使用率趋势
- MemoryUsage: 内存使用率趋势
- ConnectionUsage: 连接数使用率趋势
- MySQL_SlowQueries: 慢查询趋势
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rds_inspection_common import (
    InspectionCase, Severity, CompareOp, run_promql, parse_results,
    query_topology, build_investigation_hints, build_evidence_sources,
    calc_confidence, InspectionResult, Status, BatchInspectionOutput
)
from dataclasses import asdict
from typing import List, Dict, Any
import json


def build_cases(time_range: str = "") -> list:
    """
    声明 6 个趋势巡检项（数据驱动，零计算逻辑）

    趋势巡检使用 7d / 15d 时间窗口，分析增长速率。
    """
    return [
        InspectionCase(
            case_id="rds_disk_trend",
            item="RDS 磁盘使用趋势",
            severity=Severity.P2,
            promql='avg by (instance_id) (DiskUsage)',
            cloudmonitor_metric="DiskUsage",
            threshold=10.0,  # 周增长率 > 10% 告警
            duration=0,
            compare=CompareOp.GT,
            data_format="percent",
            description="磁盘使用率周增长率 > 10%",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查是否存在数据快速增长（如日志表、临时表）",
                "检查是否需要归档历史数据",
                "评估磁盘扩容计划",
                "检查 binlog / slowlog 保留策略",
            ],
        ),
        InspectionCase(
            case_id="rds_iops_trend",
            item="RDS IOPS 使用趋势",
            severity=Severity.P2,
            promql='avg by (instance_id) (IOPSUsage)',
            cloudmonitor_metric="IOPSUsage",
            threshold=10.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="percent",
            description="IOPS 使用率周增长率 > 10%",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查是否存在新增高频 IO 的查询",
                "检查缓冲池命中率是否下降",
                "评估是否需要升配 IOPS",
                "检查是否有批量任务导致 IO 增长",
            ],
        ),
        InspectionCase(
            case_id="rds_cpu_trend",
            item="RDS CPU 使用趋势",
            severity=Severity.P3,
            promql='avg by (instance_id) (CpuUsage)',
            cloudmonitor_metric="CpuUsage",
            threshold=10.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="percent",
            description="CPU 使用率周增长率 > 10%",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查是否存在新增高 CPU 消耗的查询",
                "检查 QPS 是否同步增长",
                "评估是否需要升配 CPU 或优化查询",
                "检查是否有定时任务导致 CPU 周期性增长",
            ],
        ),
        InspectionCase(
            case_id="rds_memory_trend",
            item="RDS 内存使用趋势",
            severity=Severity.P3,
            promql='avg by (instance_id) (MemoryUsage)',
            cloudmonitor_metric="MemoryUsage",
            threshold=10.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="percent",
            description="内存使用率周增长率 > 10%",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查是否存在内存泄漏（如连接未释放）",
                "检查缓冲池大小是否自动增长",
                "评估是否需要升配内存",
                "检查临时表创建频率是否增长",
            ],
        ),
        InspectionCase(
            case_id="rds_connections_trend",
            item="RDS 连接数趋势",
            severity=Severity.P3,
            promql='avg by (instance_id) (ConnectionUsage)',
            cloudmonitor_metric="ConnectionUsage",
            threshold=10.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="percent",
            description="连接数使用率周增长率 > 10%",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查应用端是否存在连接泄漏",
                "检查是否新增了应用实例导致连接数增长",
                "评估是否需要启用连接池",
                "检查最大连接数配置是否合理",
            ],
        ),
        InspectionCase(
            case_id="rds_slow_sql_trend",
            item="RDS 慢 SQL 趋势",
            severity=Severity.P3,
            promql='sum by (instance_id) (MySQL_SlowQueries)',
            cloudmonitor_metric="MySQL_SlowQueries",
            threshold=10.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="慢查询数量周增长率 > 10%",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "分析新增慢 SQL 的执行计划",
                "检查是否缺少索引",
                "检查数据量增长是否导致查询变慢",
                "评估是否需要优化查询或添加索引",
            ],
        ),
    ]


def analyze_trend(series: List[Dict[str, Any]], threshold: float) -> Dict[str, Any]:
    """
    分析时间序列趋势，计算增长率

    返回:
        {
            "growth_rate": float,  # 增长率 (%)
            "start_value": float,  # 起始值
            "end_value": float,    # 结束值
            "is_warning": bool,    # 是否超过阈值
        }
    """
    if not series:
        return {"error": "no series data", "is_warning": False}

    # 提取所有值并按时间排序
    all_points = []
    for s in series:
        values = s.get("values", [])
        if not values:
            val = s.get("value")
            if val and len(val) >= 2:
                all_points.append((float(val[0]), float(val[1])))
        else:
            for ts, val in values:
                all_points.append((float(ts), float(val)))

    if len(all_points) < 2:
        return {"error": "insufficient data points for trend analysis", "is_warning": False}

    all_points.sort(key=lambda x: x[0])

    # 取前 10% 和后 10% 的平均值作为起始/结束值
    n = len(all_points)
    window = max(1, n // 10)

    start_values = [p[1] for p in all_points[:window]]
    end_values = [p[1] for p in all_points[-window:]]

    start_value = sum(start_values) / len(start_values)
    end_value = sum(end_values) / len(end_values)

    # 计算增长率
    if start_value == 0:
        growth_rate = 0.0 if end_value == 0 else 100.0
    else:
        growth_rate = ((end_value - start_value) / start_value) * 100

    is_warning = growth_rate > threshold

    return {
        "growth_rate": round(growth_rate, 2),
        "start_value": round(start_value, 2),
        "end_value": round(end_value, 2),
        "data_points": len(all_points),
        "completeness": "low" if len(all_points) < 24 else "medium" if len(all_points) < 168 else "high",
        "trend_direction": "increasing" if growth_rate > 0 else "decreasing" if growth_rate < 0 else "stable",
        "is_warning": is_warning,
    }


def run_trend_case(case: InspectionCase, region: str, project: str, metricstore: str,
                   time_range: str, limit: int = 10, cloudmonitor_namespace: str = "") -> Dict[str, Any]:
    """
    执行单个趋势巡检项

    使用 7d 时间窗口分析趋势。
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
        raw_query=case.promql or case.cloudmonitor_metric,
    )

    # 使用 7d 时间窗口。趋势项需要连续时序，当前实现不对趋势数据做 CloudMonitor 降级。
    trend_time_range = "last_7d"

    data_source = ""
    rows = []

    # 优先尝试 SLS PromQL
    if case.promql:
        success, data, error = run_promql(
            region=region,
            project=project,
            metricstore=metricstore,
            query=case.promql,
            time_range=trend_time_range,
        )
        if success:
            rows = parse_results(data)
            data_source = "promql"
        else:
            result.status = Status.ERROR.value
            result.error = error
            return asdict(result)

    if not rows:
        result.status = Status.ERROR.value
        result.error = "no trend data returned from SLS PromQL"
        return asdict(result)

    result.data_source = data_source
    result.total_entities = len(rows)

    # 按 instance_id 分组并分析趋势
    from rds_inspection_common import group_by_key
    groups = group_by_key(rows, case.entity_label)

    abnormal_resources = []
    for entity_id, entity_rows in groups.items():
        trend_data = analyze_trend(entity_rows, case.threshold)
        if trend_data.get("error"):
            continue

        if trend_data["is_warning"]:
            # 获取 entity_name
            entity_name = entity_id
            if entity_rows:
                metric = entity_rows[0].get("metric", {})
                entity_name = metric.get(case.name_label, entity_id)

            # 获取最新值
            end_value = trend_data["end_value"]

            # 填充增强字段
            raw_samples = []
            if entity_rows:
                from rds_inspection_common import extract_raw_samples
                raw_samples = extract_raw_samples(entity_rows[0], limit=limit)

            topo = query_topology("RDS", entity_id, depth=1, direction="both")
            investigation_hints = build_investigation_hints(case, trend_data["growth_rate"])
            evidence_sources = build_evidence_sources(case, data_source)
            confidence = calc_confidence(trend_data["growth_rate"], case.threshold, case.compare, 0, 0)

            abnormal_resources.append({
                "entity_id": entity_id,
                "entity_name": entity_name,
                "metric_value": end_value,
                "threshold": case.threshold,
                "raw_samples": raw_samples,
                "topology": topo,
                "investigation_hints": investigation_hints,
                "trend": trend_data,
                "confidence": confidence,
                "evidence_sources": evidence_sources,
                "umodel_context": {},
            })

    result.abnormal_count = len(abnormal_resources)
    result.abnormal_resources = abnormal_resources

    if abnormal_resources:
        result.status = Status.FIND_PROBLEM.value
    elif any(analyze_trend(entity_rows, case.threshold).get("error") for entity_rows in groups.values()):
        result.status = Status.ERROR.value
        result.error = "insufficient data points for trend analysis"
    else:
        result.status = Status.PASS.value

    return asdict(result)


def run_all_trend_cases(cases: List[InspectionCase], region: str, project: str,
                        metricstore: str, time_range: str, limit: int = 10,
                        cloudmonitor_namespace: str = "",
                        case_filter: List[str] = None) -> Dict[str, Any]:
    """
    批量执行所有趋势巡检项
    """
    filtered_cases = cases
    if case_filter:
        filtered_cases = [c for c in cases if c.case_id in case_filter]

    results = []
    for case in filtered_cases:
        r = run_trend_case(
            case=case,
            region=region,
            project=project,
            metricstore=metricstore,
            time_range=time_range,
            limit=limit,
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


if __name__ == "__main__":
    import argparse

    cases = build_cases()

    parser = argparse.ArgumentParser(description="RDS 趋势巡检（6 项）：磁盘、IOPS、CPU、内存、连接数、慢 SQL 趋势分析")
    parser.add_argument("--region", default="", help="阿里云 region")
    parser.add_argument("--project", default="", help="SLS project")
    parser.add_argument("--metricstore", default="", help="SLS metricstore")
    parser.add_argument("--time-range", default="", help="时间范围（趋势巡检固定使用 last_7d）")
    parser.add_argument("--limit", type=int, default=10, help="raw_samples 最大条数 (default: 10)")
    parser.add_argument("--cases", nargs="+", default=None, help="指定巡检项 case_id 列表")
    parser.add_argument("--list-cases", action="store_true", help="列出所有巡检项并退出")
    parser.add_argument("--cloudmonitor-namespace", default="", help="CloudMonitor namespace（用于回退）")

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
    if not args.region or not args.project or not args.metricstore:
        parser.error("--region, --project, and --metricstore are required for execution")

    output = run_all_trend_cases(
        cases=cases,
        region=args.region,
        project=args.project,
        metricstore=args.metricstore,
        time_range=args.time_range or "last_7d",
        limit=args.limit,
        cloudmonitor_namespace=args.cloudmonitor_namespace,
        case_filter=args.cases,
    )
    print(json.dumps(output, indent=2, ensure_ascii=False))
