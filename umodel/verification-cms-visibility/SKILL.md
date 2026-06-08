---
name: verification-cms-visibility
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

## Do Not Do
- Do not run this first when refresh has not been attempted for the relevant environment.
- Do not diagnose before confirming the visibility result.
