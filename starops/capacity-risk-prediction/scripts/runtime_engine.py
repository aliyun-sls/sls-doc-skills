#!/usr/bin/env python3
"""
capacity-risk-prediction: 通用容量风险预测执行引擎

接收 Mission Profile JSON，对任意预测对象执行 series_forecast / series_describe，
输出结构化风险报告。

用法:
  python3 runtime_engine.py --profile profile.json [--output report.json] [--dry-run]

--dry-run 模式：只构造命令不执行，输出待执行命令列表和 Profile 校验结果。
--execute 模式：实际执行 CLI 命令（subprocess list mode，无 shell 转义问题）。
"""

import json
import sys
import os
import csv
import io
import argparse
import subprocess
import re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from collections import defaultdict


# ──────────────────────────────────────────────
# Profile 解析与校验
# ──────────────────────────────────────────────

def load_profile(path: str) -> Dict[str, Any]:
    with open(path, 'r') as f:
        profile = json.load(f)

    errors = []
    for key in ('workspace', 'region', 'time_range', 'forecast_targets'):
        if key not in profile or not profile[key]:
            errors.append(f"Missing required field: {key}")

    if errors:
        raise ValueError(f"Profile validation failed: {'; '.join(errors)}")

    for i, target in enumerate(profile.get('forecast_targets', [])):
        prefix = f"forecast_targets[{i}]"
        if not target.get('target_id'):
            errors.append(f"{prefix}.target_id is required")
        if not target.get('object_ref'):
            errors.append(f"{prefix}.object_ref is required")
        if not target.get('data_source'):
            errors.append(f"{prefix}.data_source is required")
        else:
            ds_type = target['data_source'].get('type', '')
            valid_types = ('metricstore_prom_call', 'prometheus_query', 'cloudmonitor_entity', 'sls_logstore')
            if ds_type not in valid_types:
                errors.append(f"{prefix}.data_source.type must be one of {valid_types}, got '{ds_type}'")
        if not target.get('signals') or len(target['signals']) == 0:
            errors.append(f"{prefix}.signals must have at least one signal")

    if errors:
        raise ValueError(f"Profile validation failed: {'; '.join(errors)}")

    return profile


def resolve_templates(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    resolved = []
    for target in profile['forecast_targets']:
        context = target.get('context', {})
        t = json.loads(json.dumps(target))

        if t.get('data_source', {}).get('query_template'):
            t['data_source']['resolved_query'] = _apply_template(
                t['data_source']['query_template'], context)

        for sig in t.get('signals', []):
            if sig.get('query_template'):
                sig['resolved_query'] = _apply_template(sig['query_template'], context)

        resolved.append(t)
    return resolved


def _apply_template(template: str, context: Dict[str, str]) -> str:
    result = template
    for key, value in context.items():
        result = result.replace('{{' + key + '}}', str(value))
    return result


# ──────────────────────────────────────────────
# CLI 命令构造（subprocess list mode）
# ──────────────────────────────────────────────

def build_cli_args(target: Dict[str, Any], signal: Dict[str, Any],
                   profile: Dict[str, Any],
                   func: str = "both") -> List[str]:
    ds = target['data_source']
    ds_type = ds['type']
    region = profile['region']
    time_range = profile['time_range']
    forecast_step = profile.get('forecast_step', 30)
    resolved_query = signal.get('resolved_query', ds.get('resolved_query', ''))

    if ds_type == 'metricstore_prom_call':
        project = ds['project']
        store = ds['store']
        spl = _build_spl(resolved_query, forecast_step, func)
        return ['starops', 'observe', 'log_store', 'query',
                '--region', region,
                '--project', project,
                '--logstore', store,
                '--query', spl,
                '--time-range', time_range]

    elif ds_type == 'prometheus_query':
        prom_id = ds.get('prometheus_instance_id', '')
        if ds.get('project') and ds.get('store') and func in ('forecast', 'both'):
            project = ds['project']
            store = ds['store']
            spl = _build_spl(resolved_query, forecast_step, func)
            return ['starops', 'observe', 'log_store', 'query',
                    '--region', region,
                    '--project', project,
                    '--logstore', store,
                    '--query', spl,
                    '--time-range', time_range]
        else:
            return ['starops', 'observe', 'metric_store', 'query',
                    '--prometheus-instance-id', prom_id,
                    '--region', region,
                    '--query', resolved_query,
                    '--time-range', time_range]

    elif ds_type == 'cloudmonitor_entity':
        workspace = profile['workspace']
        obj_ref = target['object_ref']
        # 优先使用 platform_entity_id（平台 entity_id），回退到 id
        entity_id = obj_ref.get('platform_entity_id', obj_ref.get('id', ''))
        entity_domain = obj_ref.get('domain', 'acs')
        entity_type = obj_ref.get('type', 'acs.rds.instance')
        msd = ds.get('metric_set_domain', 'acs')
        msn = ds.get('metric_set_name', '')
        metric_name = signal.get('signal_id', ds.get('metric_name', ''))
        return ['starops', 'observe', 'metric_store', 'query',
                '-w', workspace,
                '--entity-domain', entity_domain,
                '--entity-type', entity_type,
                '--entity-id', entity_id,
                '--metric-set-domain', msd,
                '--metric-set-name', msn,
                '--query', metric_name,
                '--time-range', time_range,
                '--raw']

    elif ds_type == 'sls_logstore':
        project = ds['project']
        store = ds['store']
        query = resolved_query
        return ['starops', 'observe', 'log_store', 'query',
                '--region', region,
                '--project', project,
                '--logstore', store,
                '--query', query,
                '--time-range', time_range]

    return []


def _build_spl(promql: str, forecast_step: int, func: str) -> str:
    base = f".metricstore | prom-call promql_query_range('{promql}')"
    if func == 'both':
        return (f"{base} | extend ret = series_forecast(__value__, {forecast_step}), "
                f"desc = series_describe(__value__)")
    elif func == 'describe':
        return f"{base} | extend desc = series_describe(__value__)"
    else:
        return f"{base} | extend ret = series_forecast(__value__, {forecast_step})"


def args_to_display_string(args: List[str]) -> str:
    parts = []
    for a in args:
        if ' ' in a or '|' in a or '~' in a or '"' in a or "'" in a:
            parts.append(f'"{a}"')
        else:
            parts.append(a)
    return ' '.join(parts)


# ──────────────────────────────────────────────
# CLI 执行（subprocess list mode, shell=False）
# ──────────────────────────────────────────────

def execute_command(args: List[str], timeout: int = 180) -> Tuple[bool, str, str]:
    try:
        proc = subprocess.run(
            args, shell=False, capture_output=True, text=True, timeout=timeout
        )
        return (proc.returncode == 0, proc.stdout, proc.stderr)
    except subprocess.TimeoutExpired:
        return (False, '', f'Command timed out after {timeout}s')
    except Exception as e:
        return (False, '', str(e))


# ──────────────────────────────────────────────
# 结果解析
# ──────────────────────────────────────────────

def _safe_json_parse(s: str) -> Any:
    if not s or not isinstance(s, str):
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        pass
    cleaned = s.replace('""', '"')
    while cleaned.startswith('"') and cleaned.endswith('"'):
        cleaned = cleaned[1:-1]
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        return json.loads(s.replace('\\"', '"').replace('\\\\', '\\'))
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _parse_csv_output(raw_output: str) -> List[Dict[str, str]]:
    if not raw_output or not raw_output.strip():
        return []
    first_line = raw_output.strip().split('\n')[0]
    if ',' in first_line and not first_line.startswith('{') and not first_line.startswith('['):
        try:
            reader = csv.DictReader(io.StringIO(raw_output))
            return list(reader)
        except Exception:
            pass
    try:
        data = json.loads(raw_output)
        if isinstance(data, dict):
            rows = data.get('rows', data.get('logs', data.get('data', [])))
            if isinstance(rows, list):
                return rows
        elif isinstance(data, list):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def parse_forecast_from_row(row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    ret_raw = row.get('ret', '')
    if not ret_raw:
        return None

    ret = _safe_json_parse(ret_raw)
    if ret is None:
        return None
    if isinstance(ret, list) and len(ret) == 1 and isinstance(ret[0], str):
        ret = _safe_json_parse(ret[0])
    if isinstance(ret, list) and len(ret) == 1 and isinstance(ret[0], list):
        ret = ret[0]
    if not isinstance(ret, list) or len(ret) < 7:
        return None

    result = {
        'timestamps': ret[0] if isinstance(ret[0], list) else [],
        'values': ret[1] if isinstance(ret[1], list) else [],
        'predicted_values': ret[2] if isinstance(ret[2], list) else [],
        'upper_bound': ret[3] if isinstance(ret[3], list) else [],
        'lower_bound': ret[4] if isinstance(ret[4], list) else [],
        'input_points': ret[5] if isinstance(ret[5], (int, float)) else 0,
        'forecast_steps': ret[6] if isinstance(ret[6], (int, float)) else 0,
    }

    step = int(result['forecast_steps'])
    if step > 0 and result['predicted_values']:
        pv = result['predicted_values']
        future_predicted = [v for v in pv[-step:] if v is not None]
        result['future_predicted'] = future_predicted
        result['predicted_max'] = max(future_predicted) if future_predicted else None
        result['predicted_min'] = min(future_predicted) if future_predicted else None

        ub = result['upper_bound'][-step:] if result['upper_bound'] else []
        lb = result['lower_bound'][-step:] if result['lower_bound'] else []
        result['future_upper'] = [v for v in ub if v is not None]
        result['future_lower'] = [v for v in lb if v is not None]

    return result


def parse_describe_from_row(row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    desc_raw = row.get('desc', '')
    if not desc_raw:
        return None

    desc = _safe_json_parse(desc_raw)
    if desc is None:
        return None
    if isinstance(desc, list) and len(desc) >= 1:
        if isinstance(desc[0], str):
            desc = _safe_json_parse(desc[0])
        else:
            desc = desc[0]
    if not isinstance(desc, dict):
        return None

    return {
        'max': desc.get('max'),
        'min': desc.get('min'),
        'mean': desc.get('mean'),
        'sum': desc.get('sum'),
        'std': desc.get('std'),
        'p5': desc.get('p5'),
        'p25': desc.get('p25'),
        'p50': desc.get('p50'),
        'p75': desc.get('p75'),
        'p95': desc.get('p95'),
        'actual_point_count': desc.get('actual_point_count', 0),
        'missing_point_count': desc.get('missing_point_count', 0),
        'time_granularity': desc.get('time_granularity'),
        'segments': desc.get('segments', []),
        'transitions': desc.get('transitions', []),
    }


# ──────────────────────────────────────────────
# CloudMonitor/RDS 原始 JSON 结果解析
# ──────────────────────────────────────────────

def parse_cloudmonitor_raw(raw_output: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    解析 metric_store query --raw 的 JSON 输出（CloudMonitor/RDS 等）。

    格式: [{"__name__": "...", "__summary__": {...}, "__ts__": "[...]", "__value__": "[...]"}]

    返回 (forecast_result, describe_result)。
    forecast_result 是从 __value__ 构造的简单线性外推。
    describe_result 是从 __summary__ 提取的统计量。
    """
    if not raw_output or not raw_output.strip():
        return (None, None)

    try:
        data = json.loads(raw_output)
    except (json.JSONDecodeError, TypeError):
        return (None, None)

    if not isinstance(data, list) or len(data) == 0:
        return (None, None)

    series = data[0]
    summary = series.get('__summary__', {})
    cur_stats = summary.get('cur_statistics', {})

    # 解析 __ts__ 和 __value__
    ts_raw = series.get('__ts__', '[]')
    val_raw = series.get('__value__', '[]')

    if isinstance(ts_raw, str):
        try:
            timestamps = json.loads(ts_raw)
        except:
            timestamps = []
    else:
        timestamps = ts_raw if isinstance(ts_raw, list) else []

    if isinstance(val_raw, str):
        try:
            values = json.loads(val_raw)
        except:
            values = []
    else:
        values = val_raw if isinstance(val_raw, list) else []

    if not values or not timestamps:
        return (None, None)

    # 构造 describe_result（从 __summary__）
    describe_result = {
        'max': cur_stats.get('max_value'),
        'min': cur_stats.get('min_value'),
        'mean': cur_stats.get('mean_value'),
        'sum': cur_stats.get('sum_value'),
        'std': cur_stats.get('std_value'),
        'p5': cur_stats.get('p5_value'),
        'p25': cur_stats.get('p25_value'),
        'p50': cur_stats.get('p50_value'),
        'p75': cur_stats.get('p75_value'),
        'p95': cur_stats.get('p95_value'),
        'actual_point_count': len(values),
        'missing_point_count': 0,
        'time_granularity': _estimate_granularity(timestamps),
        'segments': [],
        'transitions': [],
    }

    # 构造 forecast_result（简单线性外推）
    clean_values = [v for v in values if v is not None]
    if len(clean_values) < 10:
        return (None, describe_result)

    # 简单线性回归
    n = len(clean_values)
    x_mean = (n - 1) / 2.0
    y_mean = sum(clean_values) / n
    numerator = sum((i - x_mean) * (clean_values[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    slope = numerator / denominator if denominator > 0 else 0
    intercept = y_mean - slope * x_mean

    # 预测未来 30 步
    forecast_step = 30
    future_predicted = [intercept + slope * (n + i) for i in range(forecast_step)]

    # 计算置信区间（基于残差标准差）
    residuals = [clean_values[i] - (intercept + slope * i) for i in range(n)]
    residual_std = (sum(r ** 2 for r in residuals) / max(n - 2, 1)) ** 0.5
    future_upper = [v + 1.96 * residual_std for v in future_predicted]
    future_lower = [v - 1.96 * residual_std for v in future_predicted]

    # 完整预测值数组（历史拟合 + 未来预测）
    fitted = [intercept + slope * i for i in range(n)]
    all_predicted = fitted + future_predicted

    forecast_result = {
        'timestamps': timestamps,
        'values': clean_values,
        'predicted_values': all_predicted,
        'upper_bound': [v + 1.96 * residual_std for v in all_predicted],
        'lower_bound': [v - 1.96 * residual_std for v in all_predicted],
        'input_points': n,
        'forecast_steps': forecast_step,
        'future_predicted': future_predicted,
        'predicted_max': max(future_predicted) if future_predicted else None,
        'predicted_min': min(future_predicted) if future_predicted else None,
        'future_upper': future_upper,
        'future_lower': future_lower,
    }

    return (forecast_result, describe_result)


def _estimate_granularity(timestamps: list) -> Optional[int]:
    """从时间戳数组估计时间粒度（纳秒）"""
    if len(timestamps) < 2:
        return None
    try:
        diffs = [timestamps[i+1] - timestamps[i] for i in range(min(10, len(timestamps)-1))]
        if diffs:
            return int(sum(diffs) / len(diffs))
    except:
        pass
    return None


# ──────────────────────────────────────────────
# 统一解析入口
# ──────────────────────────────────────────────

def parse_stdout(raw_output: str, ds_type: str = '') -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    统一解析 CLI stdout。

    根据 ds_type 选择解析路径：
    - cloudmonitor_entity: JSON 格式（metric_store query --raw）
    - 其他: CSV 格式（log_store query 默认输出）
    """
    if ds_type == 'cloudmonitor_entity':
        return parse_cloudmonitor_raw(raw_output)

    # 默认 CSV 格式
    rows = _parse_csv_output(raw_output)
    if not rows:
        return (None, None)

    row = rows[0]
    forecast = parse_forecast_from_row(row)
    describe = parse_describe_from_row(row)
    return (forecast, describe)


# ──────────────────────────────────────────────
# 阈值评估
# ──────────────────────────────────────────────

def evaluate_risk(signal: Dict[str, Any], forecast: Optional[Dict[str, Any]],
                  describe: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    thresholds = signal.get('thresholds', {})
    warning = thresholds.get('warning')
    critical = thresholds.get('critical')
    direction = signal.get('direction', 'higher_is_worse')
    data_format = signal.get('data_format', '')

    risk_level = 'normal'
    breach_time = None
    confidence = 'unknown'

    if forecast and forecast.get('future_predicted'):
        predicted = forecast['future_predicted']
        predicted_max = forecast.get('predicted_max')
        predicted_min = forecast.get('predicted_min')

        # 对 ratio/percent 信号，检查预测值是否合理
        # 如果 data_format 是 percent 且当前值很小（<0.1），但预测值远超当前值（>10x），
        # 说明预测不可靠（噪声外推），标记为 unreliable
        if data_format == 'percent' and describe and describe.get('mean') is not None:
            mean_val = describe['mean']
            if mean_val > 0 and mean_val < 0.1 and predicted_max is not None:
                ratio = predicted_max / mean_val
                # 如果预测值超过当前均值的 10 倍，视为不可靠
                if ratio > 10:
                    confidence = 'unreliable'
                    return {
                        'risk_level': 'normal',
                        'current_value': mean_val,
                        'predicted_max': predicted_max,
                        'predicted_min': predicted_min,
                        'threshold_breach_time': None,
                        'confidence': 'unreliable',
                        'warning_threshold': warning,
                        'critical_threshold': critical,
                        '_unreliable': True,
                        '_unreliable_reason': f'ratio 信号预测值 {predicted_max:.4f} 是当前均值 {mean_val:.4f} 的 {ratio:.1f} 倍，预测不可靠',
                    }

        if direction == 'higher_is_worse':
            if critical is not None and predicted_max is not None and predicted_max >= critical:
                risk_level = 'critical'
            elif warning is not None and predicted_max is not None and predicted_max >= warning:
                risk_level = 'warning'
        else:
            if critical is not None and predicted_min is not None and predicted_min <= critical:
                risk_level = 'critical'
            elif warning is not None and predicted_min is not None and predicted_min <= warning:
                risk_level = 'warning'

        if risk_level != 'normal':
            threshold = critical if risk_level == 'critical' else warning
            granularity_ns = describe.get('time_granularity', 300_000_000_000) if describe else 300_000_000_000
            granularity_s = granularity_ns / 1e9 if granularity_ns else 300
            for i, v in enumerate(predicted):
                if v is not None:
                    if direction == 'higher_is_worse' and threshold and v >= threshold:
                        breach_time = f"+{int(i * granularity_s)}s"
                        break
                    elif direction == 'lower_is_worse' and threshold and v <= threshold:
                        breach_time = f"+{int(i * granularity_s)}s"
                        break

        if forecast.get('future_upper') and forecast.get('future_lower'):
            ub = forecast['future_upper']
            lb = forecast['future_lower']
            if ub and lb and len(ub) > 0 and len(lb) > 0:
                avg_width = sum(u - l for u, l in zip(ub, lb) if u is not None and l is not None) / max(len(ub), 1)
                pv = [v for v in predicted if v is not None]
                avg_pred = sum(pv) / max(len(pv), 1) if pv else 1
                relative_width = avg_width / abs(avg_pred) if avg_pred != 0 else 1
                if relative_width < 0.2:
                    confidence = 'high'
                elif relative_width < 0.5:
                    confidence = 'medium'
                else:
                    confidence = 'low'

    current_value = None
    if describe:
        current_value = describe.get('mean')
    elif forecast and forecast.get('values'):
        non_null = [v for v in forecast['values'] if v is not None]
        if non_null:
            current_value = non_null[-1]

    return {
        'risk_level': risk_level,
        'current_value': current_value,
        'predicted_max': forecast.get('predicted_max') if forecast else None,
        'predicted_min': forecast.get('predicted_min') if forecast else None,
        'threshold_breach_time': breach_time,
        'confidence': confidence,
        'warning_threshold': warning,
        'critical_threshold': critical,
    }


# ──────────────────────────────────────────────
# 共振检测
# ──────────────────────────────────────────────

def detect_resonance(risk_items: List[Dict[str, Any]],
                     resonance_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not resonance_config.get('enabled', False):
        return []

    min_signals = resonance_config.get('min_signals', 2)
    at_risk = [item for item in risk_items
               if item.get('risk_level') in ('warning', 'critical')]

    if len(at_risk) < min_signals:
        return []

    events = []

    by_object = defaultdict(list)
    for item in at_risk:
        by_object[item.get('object_name', 'unknown')].append(item)

    for obj_name, items in by_object.items():
        if len(items) >= min_signals:
            signals = [it['signal_id'] for it in items]
            max_severity = 'critical' if any(it['risk_level'] == 'critical' for it in items) else 'warning'
            events.append({
                'type': 'multi_signal_resonance',
                'group': obj_name,
                'targets': [it['target_id'] for it in items],
                'signals': signals,
                'description': f"{obj_name} 的 {', '.join(signals)} 共 {len(items)} 个信号同时恶化",
                'severity': max_severity,
            })

    by_chain = defaultdict(list)
    for item in at_risk:
        chain = item.get('_chain', item.get('object_name', 'unknown'))
        by_chain[chain].append(item)

    for chain, items in by_chain.items():
        unique_objects = set(it.get('object_name') for it in items)
        if len(unique_objects) >= min_signals:
            events.append({
                'type': 'multi_object_resonance',
                'group': chain,
                'targets': [it['target_id'] for it in items],
                'objects': list(unique_objects),
                'description': f"chain '{chain}' 下 {', '.join(unique_objects)} 共 {len(unique_objects)} 个对象同时恶化",
                'severity': 'critical',
            })

    return events


# ──────────────────────────────────────────────
# 错误分类
# ──────────────────────────────────────────────

def classify_error(stderr: str, stdout: str) -> str:
    combined = (stderr + ' ' + stdout).lower()
    if 'batch prediction failed' in combined:
        return 'no_data'
    if 'feature array length is out of range' in combined:
        return 'no_data'
    if 'expected in [15' in combined or 'expected in [200' in combined:
        return 'no_data'
    if 'no data' in combined or 'empty result' in combined:
        return 'no_data'
    if 'not found' in combined and 'metric' in combined:
        return 'no_data'
    return 'error'


# ──────────────────────────────────────────────
# 报告生成
# ──────────────────────────────────────────────

def _fmt_val(v) -> str:
    if v is None:
        return 'N/A'
    if isinstance(v, float):
        return f"{v:.4f}" if abs(v) < 1 else f"{v:.2f}"
    return str(v)


def generate_report(profile: Dict[str, Any],
                    risk_items: List[Dict[str, Any]],
                    resonance_events: List[Dict[str, Any]],
                    execution_time: str) -> Dict[str, Any]:
    critical = sum(1 for r in risk_items if r.get('risk_level') == 'critical')
    warning = sum(1 for r in risk_items if r.get('risk_level') == 'warning')
    normal = sum(1 for r in risk_items if r.get('risk_level') == 'normal')
    no_data = sum(1 for r in risk_items if r.get('status') == 'no_data')
    errors = sum(1 for r in risk_items if r.get('status') == 'error')

    return {
        'profile_id': profile.get('profile_id', 'unknown'),
        'execution_time': execution_time,
        'time_range': profile.get('time_range', ''),
        'region': profile.get('region', ''),
        'workspace': profile.get('workspace', ''),
        'summary': {
            'total_targets': len(risk_items),
            'critical': critical,
            'warning': warning,
            'normal': normal,
            'no_data': no_data,
            'errors': errors,
            'resonance_events': len(resonance_events),
        },
        'risk_items': risk_items,
        'resonance_events': resonance_events,
    }


def generate_markdown_report(report: Dict[str, Any]) -> str:
    lines = []
    lines.append("# 容量风险预测报告\n")
    lines.append(f"**Profile**: {report.get('profile_id', 'unknown')}")
    lines.append(f"**执行时间**: {report.get('execution_time', '')}")
    lines.append(f"**时间窗口**: {report.get('time_range', '')}")
    lines.append(f"**Region**: {report.get('region', '')}\n")

    s = report.get('summary', {})
    lines.append("## 总览\n")
    lines.append("| 指标 | 数量 |")
    lines.append("|------|:----:|")
    lines.append(f"| 预测对象总数 | {s.get('total_targets', 0)} |")
    lines.append(f"| Critical | {s.get('critical', 0)} |")
    lines.append(f"| Warning | {s.get('warning', 0)} |")
    lines.append(f"| Normal | {s.get('normal', 0)} |")
    lines.append(f"| No Data (降级 Normal) | {s.get('no_data', 0)} |")
    lines.append(f"| 错误 | {s.get('errors', 0)} |")
    lines.append(f"| 共振事件 | {s.get('resonance_events', 0)} |\n")

    lines.append("## 风险项列表\n")
    for item in report.get('risk_items', []):
        level = item.get('risk_level', 'unknown').upper()
        obj_name = item.get('object_name', '?')
        sig_id = item.get('signal_id', '?')
        lines.append(f"### {level} - {obj_name} / {sig_id}\n")
        lines.append("| 属性 | 值 |")
        lines.append("|------|-----|")

        obj_ref = item.get('object_ref', {})
        lines.append(f"| 对象 | {obj_name} ({obj_ref.get('domain', '?')}/{obj_ref.get('type', '?')}) |")
        lines.append(f"| 信号 | {sig_id} |")
        lines.append(f"| 状态 | {item.get('status', 'unknown')} |")
        lines.append(f"| 风险等级 | **{level}** |")

        cv = item.get('current_value')
        lines.append(f"| 当前值 | {_fmt_val(cv)} |")
        pm = item.get('predicted_max')
        lines.append(f"| 预测最大值 | {_fmt_val(pm)} |")
        pmin = item.get('predicted_min')
        lines.append(f"| 预测最小值 | {_fmt_val(pmin)} |")
        lines.append(f"| Warning 阈值 | {_fmt_val(item.get('warning_threshold'))} |")
        lines.append(f"| Critical 阈值 | {_fmt_val(item.get('critical_threshold'))} |")
        lines.append(f"| 预计触阈时间 | {item.get('threshold_breach_time', '未触阈')} |")
        lines.append(f"| 置信度 | {item.get('confidence', 'N/A')} |")

        dq = item.get('data_quality', {})
        if dq:
            lines.append(f"| 数据质量 | actual={dq.get('actual_points', '?')}, missing={dq.get('missing_points', '?')} |")

        segs = item.get('segments', [])
        if segs:
            shapes = [s.get('shape', s.get('unified_shape_name', '?')) if isinstance(s, dict) else str(s) for s in segs]
            shapes = [sh.replace('SegmentShapeName.', '') for sh in shapes]
            lines.append(f"| 序列分段({len(shapes)}) | {', '.join(shapes)} |")

        lines.append("")

        if item.get('evidence'):
            lines.append(f"**证据**: {item['evidence']}\n")
        if item.get('counter_evidence'):
            lines.append(f"**反证**: {item['counter_evidence']}\n")
        if item.get('gaps'):
            lines.append(f"**缺口**: {item['gaps']}\n")
        if item.get('error'):
            lines.append(f"**错误**: {item['error']}\n")
        lines.append("---\n")

    lines.append("## 共振事件\n")
    for evt in report.get('resonance_events', []):
        lines.append(f"### {evt.get('type', '?')} - {evt.get('group', '?')}\n")
        lines.append(f"- **涉及对象**: {', '.join(evt.get('objects', evt.get('targets', [])))}")
        lines.append(f"- **严重程度**: {evt.get('severity', '?')}")
        lines.append(f"- **描述**: {evt.get('description', '')}\n")

    if not report.get('resonance_events'):
        lines.append("无共振事件。\n")

    lines.append("---\n")
    lines.append("*方法论: series_forecast + series_describe (SLS SPL 管道函数); CloudMonitor 使用线性回归外推*")

    return '\n'.join(lines)


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────

def run(profile_path: str, output_path: Optional[str] = None,
        dry_run: bool = False, execute: bool = False) -> Dict[str, Any]:
    profile = load_profile(profile_path)
    resolved_targets = resolve_templates(profile)
    execution_time = datetime.now(timezone.utc).isoformat()

    if dry_run:
        commands = []
        for target in resolved_targets:
            for signal in target.get('signals', []):
                args = build_cli_args(target, signal, profile, func='both')
                commands.append({
                    'target_id': target['target_id'],
                    'signal_id': signal.get('signal_id', ''),
                    'command': args_to_display_string(args),
                })
        result = {
            'status': 'dry_run',
            'profile_id': profile.get('profile_id'),
            'total_targets': len(resolved_targets),
            'total_signals': sum(len(t.get('signals', [])) for t in resolved_targets),
            'commands': commands,
        }
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        return result

    if execute:
        risk_items = []
        for target in resolved_targets:
            ds_type = target['data_source']['type']
            for signal in target.get('signals', []):
                args = build_cli_args(target, signal, profile, func='both')
                success, stdout, stderr = execute_command(args)

                item = {
                    'target_id': target['target_id'],
                    'object_name': target['object_ref'].get('name', ''),
                    'object_ref': target['object_ref'],
                    'signal_id': signal.get('signal_id', ''),
                }

                if not success:
                    err_type = classify_error(stderr, stdout)
                    if err_type == 'no_data':
                        item['status'] = 'no_data'
                        item['risk_level'] = 'normal'
                        item['current_value'] = None
                        item['predicted_max'] = None
                        item['predicted_min'] = None
                        item['warning_threshold'] = signal.get('thresholds', {}).get('warning')
                        item['critical_threshold'] = signal.get('thresholds', {}).get('critical')
                        item['confidence'] = 'N/A'
                        item['evidence'] = '无足够数据点运行预测（数据点 < 200 或查询返回空）'
                        item['counter_evidence'] = ''
                        item['gaps'] = f'降级为 Normal: {stderr[:200] if stderr else "no data returned"}'
                        item['data_quality'] = {'actual_points': 0, 'missing_points': 0}
                        item['segments'] = []
                    else:
                        item['status'] = 'error'
                        item['error'] = stderr[:500] if stderr else 'Unknown error'
                        item['risk_level'] = 'unknown'
                        item['evidence'] = ''
                        item['counter_evidence'] = ''
                        item['gaps'] = ''
                    risk_items.append(item)
                    continue

                # 解析结果（根据数据源类型选择解析器）
                forecast, describe = parse_stdout(stdout, ds_type)

                if forecast is None and describe is None:
                    item['status'] = 'no_data'
                    item['risk_level'] = 'normal'
                    item['current_value'] = None
                    item['predicted_max'] = None
                    item['predicted_min'] = None
                    item['warning_threshold'] = signal.get('thresholds', {}).get('warning')
                    item['critical_threshold'] = signal.get('thresholds', {}).get('critical')
                    item['confidence'] = 'N/A'
                    item['evidence'] = '查询成功但无法解析预测结果（可能无数据或格式不匹配）'
                    item['counter_evidence'] = ''
                    item['gaps'] = '降级为 Normal: 解析结果为空'
                    item['data_quality'] = {'actual_points': 0, 'missing_points': 0}
                    item['segments'] = []
                    risk_items.append(item)
                    continue

                # 评估风险
                risk = evaluate_risk(signal, forecast, describe)
                item.update(risk)
                item['status'] = 'completed'

                # 附加预测详情
                if forecast:
                    item['predicted_values'] = forecast.get('future_predicted', [])
                    item['upper_bound'] = forecast.get('future_upper', [])
                    item['lower_bound'] = forecast.get('future_lower', [])
                    item['data_quality'] = {
                        'actual_points': forecast.get('input_points', 0),
                        'forecast_steps': forecast.get('forecast_steps', 0),
                    }
                if describe:
                    item['segments'] = [
                        {'shape': s.get('unified_shape_name', s.get('shape_name', '?')),
                         'confidence': s.get('confidence', 0)}
                        for s in describe.get('segments', [])
                    ]
                    item['transitions'] = [
                        {'type': t.get('type', '?'), 'confidence': t.get('confidence', 0)}
                        for t in describe.get('transitions', [])
                    ]
                    item['data_quality'] = item.get('data_quality', {})
                    item['data_quality']['actual_points'] = describe.get('actual_point_count', 0)
                    item['data_quality']['missing_points'] = describe.get('missing_point_count', 0)

                # 证据/反证/缺口
                if risk.get('_unreliable'):
                    item['evidence'] = risk['_unreliable_reason']
                    item['counter_evidence'] = '预测不可靠，不触发告警'
                    item['gaps'] = 'ratio 信号（如 error_rate）在低值区间噪声大，series_forecast 外推不可靠'
                elif risk['risk_level'] != 'normal':
                    item['evidence'] = (
                        f"series_forecast 预测 {forecast.get('forecast_steps', 0) if forecast else 0} 步后 "
                        f"最大值 {_fmt_val(risk.get('predicted_max'))} "
                        f"超过 {'critical' if risk['risk_level'] == 'critical' else 'warning'} 阈值 "
                        f"{_fmt_val(risk.get('critical_threshold') if risk['risk_level'] == 'critical' else risk.get('warning_threshold'))}"
                    )
                else:
                    item['evidence'] = "预测值在阈值范围内"

                if forecast and forecast.get('future_upper') and forecast.get('future_lower'):
                    ub = forecast['future_upper']
                    lb = forecast['future_lower']
                    if ub and lb:
                        avg_width = sum(u - l for u, l in zip(ub, lb) if u is not None and l is not None) / max(len(ub), 1)
                        item['counter_evidence'] = f"上下界平均宽度 {avg_width:.2f}，置信度 {risk.get('confidence', 'unknown')}"

                if not item.get('gaps'):
                    item['gaps'] = ""

                risk_items.append(item)

        resonance_config = profile.get('resonance', {})
        resonance_events = detect_resonance(risk_items, resonance_config)
        report = generate_report(profile, risk_items, resonance_events, execution_time)
        markdown = generate_markdown_report(report)

        result = {
            'status': 'completed',
            'report': report,
            'markdown_report': markdown,
        }

        if output_path:
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            md_path = output_path.replace('.json', '.md')
            with open(md_path, 'w') as f:
                f.write(markdown)

        return result

    return run(profile_path, output_path, dry_run=True)


def main():
    parser = argparse.ArgumentParser(description='Capacity Risk Prediction Runtime Engine')
    parser.add_argument('--profile', required=True, help='Mission Profile JSON path')
    parser.add_argument('--output', help='Output report JSON path')
    parser.add_argument('--dry-run', action='store_true', help='Only construct commands')
    parser.add_argument('--execute', action='store_true', help='Execute CLI commands')
    args = parser.parse_args()

    result = run(args.profile, args.output, dry_run=args.dry_run, execute=args.execute)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
