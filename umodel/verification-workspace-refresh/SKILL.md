---
name: verification-workspace-refresh
description: Execute the canonical repository refresh path that writes entity and relationship data toward the configured CMS workspace data plane.
---

# Verification Workspace Refresh

## Purpose
- Run the real refresh path that matters when the workspace has no fresh devops data.

## Read First
- `shared/verification/workflow-stages.md`
- `shared/verification/script-map.md`
- `shared/verification/config-contract.md`
- `shared/verification/receipt-contract.md`

## Canonical Command
```bash
python3 devops_data_generator/main.py --mode single --config devops_data_generator/config
```

## Do
- Use the canonical command from `shared/verification/script-map.md`.
- Record the execution summary honestly.
- Distinguish `success`, `partial_success`, `error`, and `blocked` clearly.

## Do Not Do
- Do not replace this with any historical manual wrapper path.
- Do not claim refresh happened if only verification scripts were run.
