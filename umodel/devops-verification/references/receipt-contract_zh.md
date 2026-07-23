# 验证结果契约

## 通用规则
- 必须声明运行的阶段
- 必须声明 PASS / FAIL / BLOCKED
- 不得在仅运行查询脚本时声称执行了 refresh

## 各阶段必需字段

### resource-readiness
`stage` / `git_provider` / `checked_resources` / `missing_resources` / `verdict`

### workspace-alignment
`stage` / `workspace` / `configured_sls_project` / `entity_logstore_target` / `topo_logstore_target` / `verdict`

### workspace-refresh
`stage` / `command` / `execution_summary_status` / `executed_tasks_summary` / `failed_tasks_summary` / `verdict`

### cms-visibility
`stage` / `workspace` / `visible_entity_types` / `devops_entity_counts` / `verdict`

### cms-field-check
`stage` / `git_provider` / `checked_entity_types` / `key_field_results` / `verdict`

### cms-sls-diagnose
`stage` / `workspace_metadata_summary` / `observed_entity_store_summary` / `suspected_root_cause` / `verdict`
