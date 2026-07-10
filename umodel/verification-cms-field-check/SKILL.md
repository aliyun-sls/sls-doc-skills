---
name: verification-cms-field-check-sample
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
- `devops.repository.data_source` must equal `"gitlab"`
- `devops.repository.name` format: `path_with_namespace` (e.g. `root/demo-app`)
- `devops.repository.default_branch` fallback: `"main"`
- `devops.release.release_type` from `release_classifier` (not hardcoded `"release"`)

### When `git_provider.type = codeup`
- `devops.repository.data_source` must equal `"codeup"` (not `aliyun`)
- `devops.repository.name` format: codeup repo name (e.g. `Codeup-Demo`)
- `devops.repository.url` must contain `codeup.aliyun.com`
- `devops.repository.default_branch` fallback: `"master"`
- `devops.release.release_type` from `release_classifier` (not hardcoded)
- `devops.user.repositories[*].access_level` = `0` (codeup does not expose access_level)

### Shared assertions (both providers)
- `devops.repository.repository_id` is a non-empty string
- `devops.release.release_id` format: `{repo_id_or_name}/{tag}`
- `devops.release.tag_name` is non-empty
- `devops.release.commit_sha` is non-empty
- `devops.docker_image.docker_image_id` is non-empty
- `devops.docker_image.registry` is non-empty
- `devops.user.user_id` is non-empty
- `devops.artifact.artifact_id` pairs with `devops.docker_image.artifact_id` (decision B)

### Image alignment (cross-domain edge correctness)
- The canonical command finishes with `pod -> docker_image topology evidence`, queried from the configured SLS relationship logstore. Use those rows as the evidence source for `container_image`, `repository`, `tag`, endpoint IDs, relation/link type, and edge keep-alive fields; do not infer an edge only from entity records.
- Registry host must be normalized across sources. The same ACR instance may be reached via multiple endpoints (for example a VPC endpoint and a canonical endpoint). Pod `containers.image` and `devops.docker_image.full_image_name` must be compared after registry alias normalization, not by raw host string.
- Match requires namespace + repo + tag (or digest) all equal. Matching only on the bare repo name (for example `demo`) ignores namespace and tag and produces wrong cross-domain edges. No match -> no edge; do not force a fallback link.
- Test/branch tag images may have no corresponding `devops.release` record; this is a real release gap, not a field defect. Report the gap instead of forcing a link to a versioned release.

## Receipt Format
```
- stage: cms-field-check
- git_provider: gitlab | codeup
- command: <canonical command>
- checked_entity_types: [repository, release, docker_image, user, artifact]
- key_field_results:
    repository:
      data_source: <actual value> (expected: gitlab|codeup) — PASS|FAIL
      repository_id: PASS|FAIL
      url: PASS|FAIL
    release:
      release_type: <actual value> — PASS|FAIL
      ...
    docker_image:
      full_image_name: PASS|FAIL
      registry_alias_normalized: <evidence from task configuration> — PASS|FAIL
      image_alignment (namespace+repo+tag vs pod containers.image): <topology rows> — PASS|FAIL
- verdict: PASS | FAIL
```

## Do Not Do
- Do not use this as the first proof that refresh worked.
- Do not conflate field problems with resource-readiness problems by default.
- Do not hardcode expected `git_provider` value — always derive from `app_config.yaml`.
