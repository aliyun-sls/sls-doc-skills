# 关联日志巡检项清单

## 巡检项列表

| case_id | severity | 描述 | 阈值 | 数据来源 |
|---------|----------|------|------|----------|
| rds_slow_sql_high | P2 | 慢 SQL 数量过高 | > 10 / 5min | 审计日志 |
| rds_error_log_high | P2 | ERROR 级别日志过多 | > 10 / 5min | 错误日志 |

## 查询条件

### rds_slow_sql_high

**查询条件**：
```
* and "execute_time" and "execute_time" > "1s" | select count(*) as cnt
```

**阈值**：10 条 / 5 分钟

**修复建议**：
1. 查询慢 SQL 摘要，识别高频慢 SQL
2. 检查索引使用情况，添加缺失索引
3. 追踪慢 SQL 模式，识别共性问题
4. 检查表统计信息是否最新

**investigation_hints 示例**（脚本实际输出为中文自然语言提示）：
- 查询慢查询摘要
- 检查索引使用情况
- 追踪慢 SQL 模式
- 检查表统计信息

### rds_error_log_high

**查询条件**：
```
"ERROR" | select count(*) as cnt
```

**阈值**：10 条 / 5 分钟

**修复建议**：
1. 检查错误日志详情
2. 关联指标异常
3. 追踪错误模式
4. 检查近期变更

## 审计日志接入说明

### 配置步骤

1. **启用 RDS 审计日志**：
   - 登录 RDS 控制台
   - 选择目标实例
   - 进入"数据安全性" > "SQL 审计"
   - 开启 SQL 审计功能

2. **配置日志投递到 SLS**：
   - 在 SQL 审计页面，选择"投递到 SLS"
   - 选择目标 SLS Project 和 Logstore
   - 配置投递策略

3. **获取 Logstore 名称**：
   - 审计日志 Logstore 命名格式：`rds-audit-log-{instance-id}`
   - 错误日志 Logstore 命名格式：`rds-error-log-{instance-id}`

### 使用 --audit-logstore 参数

执行日志巡检时，必须提供 `--audit-logstore` 参数：

```bash
python3 rds-logs-inspection.py \
  --region cn-hangzhou \
  --project my-project \
  --metricstore my-metricstore \
  --time-range last_1h \
  --audit-logstore rds-audit-log-rm-xxx
```

### 日志字段说明

**审计日志字段**：
- `instance_id`：RDS 实例 ID
- `execute_time`：SQL 执行时间（毫秒）
- `sql_text`：SQL 文本（超过 100 字符自动截断）
- `user`：执行用户
- `client_ip`：客户端 IP
- `status`：执行状态

**错误日志字段**：
- `instance_id`：RDS 实例 ID
- `level`：日志级别（ERROR/WARN/INFO）
- `message`：错误消息
- `timestamp`：时间戳

### 敏感信息脱敏

脚本自动脱敏以下字段：
- 账号信息
- IP 地址
- 密码/Token
- SQL 文本超过 100 字符的部分自动截断
