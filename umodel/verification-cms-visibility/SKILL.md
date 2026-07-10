---
name: verification-cms-visibility-sample
description: Query the CMS workspace to verify whether devops entities are visible after refresh.
---

# Verification CMS Visibility

## Purpose
- Check whether `devops.*` entities are visible in the CMS workspace.

## Read First
- `shared/verification/workflow-stages.md`
- `shared/verification/script-map.md`
- `shared/verification/receipt-contract.md`

## Canonical Command
```bash
python3 devops_data_generator/scripts/query_cms_devops.py --config devops_data_generator/config
```

## Do
- Use the canonical visibility command.
- Report visible entity types and counts.
- Treat this as verification, not refresh.
- Check the keep-alive columns printed by the canonical command: `__method__`, `__last_observed_time__`, `__keep_alive_seconds__`, and `__first_observed_time__`. The CMS graph engine treats a record as alive only within `__last_observed_time__` + `__keep_alive_seconds__`; entities written to the logstore without these fields are not alive in the graph, so `entity neighbor` returns 0 even though the entity exists.
- When checking relationships via `entity neighbor`, always pass `--relation-type` (for example `uses`, `same_as`, `contains`, `tags`, `owns`). Without the filter the default returns 0 and gets misread as a missing relationship.

## Do Not Do
- Do not run this first when refresh has not been attempted for the relevant environment.
- Do not diagnose before confirming the visibility result.
- Do not declare entities visible solely because they were written to the logstore; a stale or non-keep-alive record is not alive in the graph.
