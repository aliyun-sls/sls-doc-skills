#!/usr/bin/env python3
"""
rds-core-inspection.py - RDS 核心指标巡检（7 项）

业务脚本：只声明 InspectionCase 配置，零计算逻辑。
所有计算由 rds_inspection_common.py 公共引擎承载。

CloudMonitor 指标名映射：
- CpuUsage: CPU 使用率 (%)
- MemoryUsage: 内存使用率 (%)
- DiskUsage: 磁盘使用率 (%)
- IOPSUsage: IOPS 使用率 (%)
- ConnectionUsage: 连接数使用率 (%)
- MySQL_NetworkTraffic: 网络流量
- ReplicationDelay: 复制延迟 (秒)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rds_inspection_common import (
    InspectionCase, Severity, CompareOp, cli_main
)


def build_cases(time_range: str = "") -> list:
    """
    声明 7 个核心指标巡检项（数据驱动，零计算逻辑）

    新增巡检项 = 新增一个 InspectionCase 数据项，不需要写新的计算代码。
    """
    return [
        InspectionCase(
            case_id="rds_cpu_high",
            item="RDS CPU 使用率过高",
            severity=Severity.P1,
            promql='avg by (instance_id) (CpuUsage)',
            cloudmonitor_metric="CpuUsage",
            threshold=80.0,
            duration=300,
            compare=CompareOp.GT,
            data_format="percent",
            description="CPU 使用率 > 80%，持续 5 分钟",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查是否存在慢查询或全表扫描",
                "检查是否有锁等待导致的 CPU 堆积",
                "查看活跃连接数和 QPS 是否异常升高",
                "考虑升配 CPU 或启用读写分离",
            ],
        ),
        InspectionCase(
            case_id="rds_memory_high",
            item="RDS 内存使用率过高",
            severity=Severity.P1,
            promql='avg by (instance_id) (MemoryUsage)',
            cloudmonitor_metric="MemoryUsage",
            threshold=85.0,
            duration=300,
            compare=CompareOp.GT,
            data_format="percent",
            description="内存使用率 > 85%，持续 5 分钟",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查缓冲池命中率是否偏低",
                "检查是否存在内存密集型查询（大排序、临时表）",
                "检查临时表创建频率",
                "考虑升配内存或优化 innodb_buffer_pool_size",
            ],
        ),
        InspectionCase(
            case_id="rds_disk_high",
            item="RDS 磁盘使用率过高",
            severity=Severity.P2,
            promql='avg by (instance_id) (DiskUsage)',
            cloudmonitor_metric="DiskUsage",
            threshold=80.0,
            duration=600,
            compare=CompareOp.GT,
            data_format="percent",
            description="磁盘使用率 > 80%，持续 10 分钟",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查 binlog / slowlog / errorlog 是否占用过多空间",
                "检查是否存在大量无用数据或历史数据需要归档",
                "检查临时表空间是否异常增长",
                "考虑扩容磁盘或清理无用数据",
            ],
        ),
        InspectionCase(
            case_id="rds_iops_high",
            item="RDS IOPS 使用率过高",
            severity=Severity.P2,
            promql='avg by (instance_id) (IOPSUsage)',
            cloudmonitor_metric="IOPSUsage",
            threshold=80.0,
            duration=300,
            compare=CompareOp.GT,
            data_format="percent",
            description="IOPS 使用率 > 80%，持续 5 分钟",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查是否存在高频小 IO 的 SQL（如大量随机查询）",
                "检查缓冲池命中率，低命中率会导致更多磁盘 IO",
                "检查是否有批量导入/导出任务正在执行",
                "考虑升配 IOPS 或增加缓存层",
            ],
        ),
        InspectionCase(
            case_id="rds_connections_high",
            item="RDS 连接数过高",
            severity=Severity.P2,
            promql='avg by (instance_id) (ConnectionUsage)',
            cloudmonitor_metric="ConnectionUsage",
            threshold=80.0,
            duration=300,
            compare=CompareOp.GT,
            data_format="percent",
            description="连接数 > 80% 最大连接数，持续 5 分钟",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查应用端是否存在连接泄漏（未正确关闭连接）",
                "检查是否缺少连接池配置",
                "检查是否存在长事务占用连接",
                "考虑启用连接池或增加最大连接数配置",
            ],
        ),
        InspectionCase(
            case_id="rds_instance_down",
            item="RDS 实例状态异常",
            severity=Severity.P1,
            promql='rds_instance_status{status!="running"}',
            cloudmonitor_metric="",
            threshold=0.0,
            duration=0,
            compare=CompareOp.GT,
            data_format="raw",
            description="实例状态非 running",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查 RDS 控制台实例状态与事件通知",
                "检查是否存在主备切换事件",
                "检查实例是否因磁盘满/内存 OOM 等原因被锁定",
                "必要时联系阿里云技术支持或切换备实例",
            ],
        ),
        InspectionCase(
            case_id="rds_replication_lag",
            item="RDS 复制延迟过高",
            severity=Severity.P2,
            promql='avg by (instance_id) (ReplicationDelay)',
            cloudmonitor_metric="ReplicationDelay",
            threshold=10.0,
            duration=300,
            compare=CompareOp.GT,
            data_format="s",
            description="主从复制延迟 > 10s，持续 5 分钟",
            entity_label="instance_id",
            name_label="instance_id",
            investigation_hints=[
                "检查主实例负载（CPU/IOPS）是否过高导致 binlog 生成慢",
                "检查是否存在大事务导致复制阻塞",
                "检查主备之间的网络延迟",
                "检查备实例的 IO 能力是否不足",
            ],
        ),
    ]


if __name__ == "__main__":
    cases = build_cases()
    cli_main(
        cases=cases,
        description="RDS 核心指标巡检（7 项）：CPU、内存、磁盘、IOPS、连接数、实例状态、复制延迟",
        entity_type="RDS",
    )
