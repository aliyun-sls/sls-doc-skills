# RDS 安全巡检项清单

## 巡检项清单

| # | case_id | severity | 巡检项 | 阈值 | 持续时间 | PromQL | 修复建议 |
|---|---|---|---|---|---|---|---|
| 1 | rds_ssl_disabled | P2 | SSL 未启用 | ssl_enabled == 0 | 瞬时 | `rds_ssl_enabled == 0` | 1. 启用 SSL/TLS 加密 2. 更新应用连接字符串 3. 验证证书有效性 |
| 2 | rds_public_access | P1 | 公网访问开启 | public_access == 1 | 瞬时 | `rds_public_access_enabled == 1` | 1. 关闭公网访问 2. 使用 VPC 内网连接 3. 配置白名单限制来源 IP |
| 3 | rds_backup_failed | P1 | 备份失败 | status == failed | 瞬时 | `rds_backup_status{status="failed"}` | 1. 检查备份任务日志 2. 确认存储空间充足 3. 重新执行备份 |
| 4 | rds_backup_retention_low | P3 | 备份保留天数不足 | < 7 天 | 瞬时 | `rds_backup_retention_days` | 1. 增加备份保留天数至 ≥7 2. 配置跨区域备份 3. 定期验证备份可恢复性 |
| 5 | rds_audit_log_disabled | P2 | 审计日志未启用 | audit_log == 0 | 瞬时 | `rds_audit_log_enabled == 0` | 1. 启用 SQL 审计日志 2. 配置日志存储与保留策略 3. 定期审计日志分析 |
| 6 | rds_high_privilege_accounts | P2 | 存在高权限账号 | count > 0 | 瞬时 | `rds_high_privilege_accounts > 0` | 1. 审查高权限账号列表 2. 遵循最小权限原则 3. 禁用或删除不必要的高权限账号 |
