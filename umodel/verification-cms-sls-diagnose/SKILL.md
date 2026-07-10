---
name: verification-cms-sls-diagnose-sample
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
- When `entity neighbor` returns 0 for entities that are known to be written, check the four known root-cause classes before concluding the relationship is missing:
  1. **Endpoint ID encoding mismatch**: edge endpoints (`__src_entity_id__` / `__dest_entity_id__`) must use the same ID form as the node (`__entity_id__`). Nodes use md5 of primary keys; if edges carry raw primary-key strings, edges dangle. Confirm edge endpoints are md5-aligned with node IDs.
  2. **Missing keep-alive fields**: the CMS graph engine only treats records within `__last_observed_time__` + `__keep_alive_seconds__` as alive. Devops records written without `__method__` / `__last_observed_time__` / `__keep_alive_seconds__` / `__first_observed_time__` are written to the logstore but not in the graph, so `neighbor` returns 0. Confirm keep-alive fields are stamped on both entities and edges.
  3. **Cross-source pod ID divergence**: if a runtime entity (for example `k8s.pod`) is also ingested by CMS built-in producer, CMS holds the canonical entity_id (based on metadata.uid). A task that recomputes the pod entity_id diverges from the CMS node, so cross-domain edges with the recomputed src dangle. Keep the CMS original entity_id, do not recompute it.
  4. **Loose image matching**: cross-domain `pod -> docker_image` edges must match on namespace + repo + tag (or digest) after registry alias normalization. Matching only on the bare repo name links pods to the wrong image. Confirm the match is strict and unmatched images produce no edge.
- Use the field-check topology evidence before making a pod/image semantic claim. If `verify_devops_details.py` did not print `pod -> docker_image topology evidence`, the required edge evidence was not collected; report that gap instead of declaring the `uses` relation correct.

## Do Not Do
- Do not use diagnosis as the default first action.
- Do not let diagnosis hide that a prior stage was never actually executed.
- Do not declare a relationship missing while only the no-filter `entity neighbor` was tried; always retry with `--relation-type`.
