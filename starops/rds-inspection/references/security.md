# 安全巡检项清单

## 巡检项列表

| case_id | severity | 描述 | 阈值 | 持续时间 |
|---------|----------|------|------|----------|
| rds_ssl_disabled | P2 | SSL 未启用 | 未启用 | 瞬时 |
| rds_public_access | P1 | 公网访问开启 | 开启 | 瞬时 |
| rds_backup_failed | P1 | 备份失败 | 失败 | 瞬时 |
| rds_backup_retention_low | P3 | 备份保留天数不足 | < 7 天 | 瞬时 |
| rds_audit_log_disabled | P2 | 审计日志未启用 | 未启用 | 瞬时 |
| rds_high_privilege_accounts | P2 | 存在高权限账号 | > 0 | 瞬时 |

## 修复建议

### rds_ssl_disabled

**修复建议**：
1. 启用 SSL 加密连接
2. 检查 SSL 证书有效性
3. 验证客户端连接要求
4. 检查合规性要求

**investigation_hints 示例**（脚本实际输出为中文自然语言提示）：
- 检查 SSL 证书
- 验证客户端连接要求
- 检查合规性要求

### rds_public_access

**修复建议**：
1. 禁用公网访问端点
2. 检查白名单配置
3. 检查安全组规则
4. 评估数据敏感性

### rds_backup_failed

**修复建议**：
1. 检查备份日志
2. 验证存储空间
3. 检查备份窗口冲突
4. 评估数据恢复风险

### rds_backup_retention_low

**修复建议**：
1. 检查备份策略
2. 验证合规性要求
3. 评估数据保留需求

### rds_audit_log_disabled

**修复建议**：
1. 启用审计日志
2. 检查审计日志配置
3. 验证合规性要求
4. 评估安全监控需求

### rds_high_privilege_accounts

**修复建议**：
1. 检查账号权限
2. 验证最小权限原则
3. 审查账号使用日志
4. 检查密码策略
