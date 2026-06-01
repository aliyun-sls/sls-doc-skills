# RDS 关联日志巡检项清单

## 巡检项清单

| # | case_id | severity | 巡检项 | 阈值 | 持续时间 | 日志查询 | 数据来源 | 修复建议 |
|---|---|---|---|---|---|---|---|---|
| 1 | rds_slow_sql_high | P2 | 慢 SQL 数量过高 | > 10 / 5min | 瞬时 | `* and "execute_time" and "execute_time" > "1s" \| select count(*) as cnt` | 审计日志 | 1. 分析慢 SQL 执行计划 2. 添加缺失索引 3. 优化查询逻辑 4. 考虑 SQL 限流 |
| 2 | rds_error_log_high | P2 | ERROR 级别日志过多 | > 10 / 5min | 瞬时 | `"ERROR" \| select count(*) as cnt` | 错误日志 | 1. 查看 ERROR 日志详情 2. 定位根因（连接超时、权限、语法等） 3. 修复应用或配置问题 |

## 慢 SQL 查询条件

- **关键字**: `execute_time > 1s`
- **日志来源**: 审计日志（RDS SQL Audit）
- **查询语法**: SLS SQL
- **阈值**: 5 分钟内 > 10 条

## ERROR 日志查询条件

- **过滤条件**: `"ERROR"`（全文搜索，兼容未建立 key-value 索引的 LogStore）
- **日志来源**: 错误日志（RDS Error Log）
- **查询语法**: SLS SQL
- **阈值**: 5 分钟内 > 10 条

## 审计日志接入与 `--audit-logstore` 配置说明

### 必填参数

日志脚本 `rds-logs-inspection.py` **必须**传入 `--audit-logstore` 参数，否则直接返回 `error` 状态并提示参数缺失。

```bash
python3 rds-logs-inspection.py \
  --region cn-hangzhou \
  --project my-project \
  --metricstore my-ms \
  --time-range last_1h \
  --audit-logstore rds-audit-log
```

### 审计日志接入步骤

1. 在 RDS 控制台启用 SQL 审计功能
2. 配置审计日志投递到 SLS LogStore
3. 确认 LogStore 名称并传入 `--audit-logstore`
4. 确认日志格式包含 `execute_time` 字段

### 脱敏规则

异常项的 `raw_samples` 字段填充最近 N 条命中日志的脱敏摘要：

- SQL 文本超过 100 字符的部分截断为 `...`
- 不输出账号、IP、表全名等敏感字段
- 自动跳过 `account`、`ip`、`password`、`secret`、`token` 等字段
