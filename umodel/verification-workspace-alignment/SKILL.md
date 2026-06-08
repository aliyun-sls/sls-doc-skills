---
name: verification-workspace-alignment
description: Verify that the repository config points at the correct CMS workspace backing SLS project and workspace entity/topo logstores before refreshing data.
---

# Verification Workspace Alignment

## Purpose
- Confirm that refresh would write into the intended CMS workspace data plane.

## Read First
- `shared/verification/workflow-stages.md`
- `shared/verification/config-contract.md`
- `shared/verification/receipt-contract.md`
- `shared/verification/failure-diagnosis.md`
- `devops_data_generator/config/app_config.yaml` — read `git_provider.type` for provider-specific alignment notes.

## Provider-Aware Alignment

**Step 1**: Read `git_provider.type` from `devops_data_generator/config/app_config.yaml`.

**Step 2**: Perform shared alignment checks:
- `cms.workspace` is set
- `sls.project` matches or contains the workspace name (convention: backing SLS project includes the workspace name)
- All entity logstore mappings (`sls.logstore_mapping.entities.*`) point to `{workspace}__entity`
- All topo logstore mappings (`sls.logstore_mapping.relationships.*`) point to `{workspace}__topo`
- `kubernetes_pod` has a logstore mapping in `sls.logstore_mapping.entities` (missing = SLS write fails for pods)
- `kubernetes.data_source` is `cms` or `k8s`; if `cms`, confirm it reads from the same `cms.workspace`

**Step 3**: Provider-specific notes in the receipt:

### When `git_provider.type = gitlab`
- Note: git data will be written with `git_provider=gitlab` in SLS entities
- Note: `gitlab.url` endpoint is independent of SLS/CMS region

### When `git_provider.type = codeup`
- Note: git data will be written with `git_provider=aliyun` in SLS entities
- Note: codeup endpoint (default `devops.cn-hangzhou.aliyuncs.com`) may differ from SLS/CMS region — this is expected and not a misalignment
- If `auth_mode=pat`, note that PAT scope may return more repos than RAM AK scope

## Receipt Format
```
- stage: workspace-alignment
- git_provider: gitlab | codeup
- workspace: <value>
- configured_sls_project: <value>
- entity_logstore_target: <value>
- topo_logstore_target: <value>
- kubernetes_pod_logstore: configured | MISSING
- alignment: ALIGNED | MISALIGNED
- provider_notes: [provider-specific observations]
- verdict: PASS | BLOCKED
```

## Do Not Do
- Do not run refresh before alignment is understood.
- Do not assume any arbitrary SLS project is acceptable just because write permissions exist.
