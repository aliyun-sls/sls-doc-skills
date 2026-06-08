---
name: verification-resource-readiness
description: Check whether the external resources required for the verification chain already exist before any workspace refresh or CMS query is attempted.
---

# Verification Resource Readiness

## Purpose
- Confirm the environment is actually ready for verification work.
- Stop early when required resources do not exist.

## Read First
- `shared/verification/prerequisites.md`
- `shared/verification/receipt-contract.md`
- `shared/verification/workflow-stages.md`
- `devops_data_generator/config/app_config.yaml` — read `git_provider.type` to determine which credentials to check.

## Provider-Aware Checks

**Step 1**: Read `git_provider.type` from `devops_data_generator/config/app_config.yaml`.

**Step 2**: Based on the value, check the corresponding credentials and resources:

### When `git_provider.type = gitlab`
- `gitlab.url` is set and not a placeholder
- `gitlab.access_token` is set and not a placeholder
- If `gitlab.project_id` is set, confirm the project is reachable
- Report provider as **GitLab**

### When `git_provider.type = codeup`
- `codeup.organization_id` is set and not a placeholder
- `codeup.access_key_id` and `codeup.access_key_secret` are set and not placeholders
- If `codeup.auth_mode = pat`, confirm `codeup.access_token` is set and not a placeholder
- Report provider as **Codeup (Alibaba Cloud DevOps)**

### Shared checks (both providers)
- `acr.instance_id` is set and not a placeholder
- `acr.access_key_id` and `acr.access_key_secret` are set
- `cms.workspace` is set and not a placeholder
- `cms.endpoint` is set
- `sls.project` is set and not a placeholder
- `sls.endpoint` is set
- Required config files exist: `app_config.yaml`, `data_mapping.yaml`, `repo_image_mapping.yaml`, `manage_mapping.yaml`, `static_topo.yaml`

## Receipt Format
```
- stage: resource-readiness
- git_provider: gitlab | codeup
- auth_mode: (codeup only) ram | pat
- checked_resources: [list]
- missing_resources: [list]
- verdict: PASS | BLOCKED
```

## Do Not Do
- Do not run refresh.
- Do not run CMS query scripts as a substitute for missing resources.
- Do not create missing resources in the first-wave flow.
