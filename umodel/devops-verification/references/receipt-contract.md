# Receipt Contract

## General Rules
- receipts must state what stage ran
- receipts must state the exact command or inspection target
- receipts must state PASS / FAIL / BLOCKED honestly
- receipts must not claim refresh happened when only query scripts ran

## Resource Readiness Receipt
Required fields:
- stage: `resource-readiness`
- checked_resources
- missing_resources
- verdict

## Workspace Alignment Receipt
Required fields:
- stage: `workspace-alignment`
- workspace
- configured_sls_project
- expected_workspace_sls_project
- entity_logstore_target
- topo_logstore_target
- verdict

## Workspace Refresh Receipt
Required fields:
- stage: `workspace-refresh`
- command
- config_source
- execution_summary_status
- executed_tasks_summary
- failed_tasks_summary
- verdict

## CMS Visibility Receipt
Required fields:
- stage: `cms-visibility`
- command
- workspace
- visible_entity_types
- devops_entity_counts
- verdict

## CMS Field Check Receipt
Required fields:
- stage: `cms-field-check`
- command
- checked_entity_types
- key_field_results
- verdict

## Diagnose Receipt
Required fields:
- stage: `cms-sls-diagnose`
- command
- workspace_metadata_summary
- observed_entity_store_summary
- suspected_root_cause
- verdict
