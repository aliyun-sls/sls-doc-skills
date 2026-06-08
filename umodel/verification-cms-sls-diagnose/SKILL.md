---
name: verification-cms-sls-diagnose
description: Diagnose CMS workspace and SLS alignment issues when refresh or visibility results do not match expectations.
---

# Verification CMS SLS Diagnose

## Purpose
- Identify why data is not visible or not aligned after the earlier stages have already failed or produced uncertainty.

## Read First
- `shared/verification/failure-diagnosis.md`
- `shared/verification/script-map.md`
- `shared/verification/receipt-contract.md`
- `shared/verification/config-contract.md`

## Canonical Command
```bash
python3 devops_data_generator/scripts/diagnose_cms_entity_store.py --config devops_data_generator/config
```

## Do
- Use diagnosis only after resource readiness and refresh/visibility checks justify it.
- Report workspace metadata, entity store surface, and suspected root cause.

## Do Not Do
- Do not use diagnosis as the default first action.
- Do not let diagnosis hide that a prior stage was never actually executed.
