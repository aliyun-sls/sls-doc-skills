---
name: verification-cms-field-check
description: Inspect key devops entity fields in the CMS workspace after visibility has already been confirmed.
---

# Verification CMS Field Check

## Purpose
- Validate key fields on known entities once the workspace already shows the expected devops entity types.

## Read First
- `shared/verification/workflow-stages.md`
- `shared/verification/script-map.md`
- `shared/verification/receipt-contract.md`
- `devops_data_generator/config/app_config.yaml` — read `git_provider.type` to determine expected field values.

## Canonical Command
```bash
python3 devops_data_generator/scripts/verify_devops_details.py --config devops_data_generator/config
```

## Provider-Aware Field Assertions

**Step 1**: Read `git_provider.type` from `devops_data_generator/config/app_config.yaml`.

**Step 2**: Run the canonical command.

**Step 3**: Assert field values based on active provider:

### When `git_provider.type = gitlab`
- `devops.code_repository.git_provider` must equal `"gitlab"`
- `devops.code_repository.repo_name` format: `path_with_namespace` (e.g. `root/demo-app`)
- `devops.code_repository.default_branch` fallback: `"main"`
- `devops.code_release.release_type` from `release_classifier` (not hardcoded `"release"`)

### When `git_provider.type = codeup`
- `devops.code_repository.git_provider` must equal `"aliyun"`
- `devops.code_repository.repo_name` format: codeup repo name (e.g. `Codeup-Demo`)
- `devops.code_repository.repo_url` must contain `codeup.aliyun.com`
- `devops.code_repository.default_branch` fallback: `"master"`
- `devops.code_release.release_type` from `release_classifier` (not hardcoded)
- `devops.developer.repositories[*].access_level` = `0` (codeup does not expose access_level)

### Shared assertions (both providers)
- `devops.code_repository.repo_id` is a non-empty string
- `devops.code_release.release_id` format: `{repo_id_or_name}/{tag}`
- `devops.code_release.tag` is non-empty
- `devops.code_release.commit_sha` is non-empty
- `devops.image.image_id` is non-empty
- `devops.image.registry_id` is non-empty
- `devops.image_registry.registry_id` is non-empty
- `devops.image_registry.registry_url` is non-empty

## Receipt Format
```
- stage: cms-field-check
- git_provider: gitlab | codeup
- command: <canonical command>
- checked_entity_types: [code_repository, code_release, image, image_registry, developer]
- key_field_results:
    code_repository:
      git_provider: <actual value> (expected: gitlab|aliyun) — PASS|FAIL
      repo_id: PASS|FAIL
      repo_url: PASS|FAIL
    code_release:
      release_type: <actual value> — PASS|FAIL
      ...
- verdict: PASS | FAIL
```

## Do Not Do
- Do not use this as the first proof that refresh worked.
- Do not conflate field problems with resource-readiness problems by default.
- Do not hardcode expected `git_provider` value — always derive from `app_config.yaml`.
