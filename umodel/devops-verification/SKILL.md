---
name: devops-verification
description: Verify DevOps data ingestion into the CMS workspace backed by SLS. Run the staged pipeline (resource-readiness -> workspace-alignment -> workspace-refresh -> cms-visibility -> cms-field-check -> cms-sls-diagnose) and route to the stage a situation needs. Use when devops entities or relationships are missing, stale, or misaligned in the CMS workspace, or to confirm a fresh ingest end-to-end.
---

# DevOps Verification

Use this skill to verify that the devops producer's entities and relationships are correctly
ingested into the configured CMS workspace (backed by SLS logstores). It is a staged pipeline:
stop early on missing resources, and escalate to diagnosis only when refresh or visibility fail.

This skill does **not** generate data. Generating data is `devops_data_generator/main.py`
(stage 3 runs it as the refresh step); this skill verifies what it produced.

## Mission

Confirm, end to end, that:
- the external resources and config exist (stage 1),
- the config points at the intended CMS workspace + SLS entity/topo logstores (stage 2),
- a real refresh was run (stage 3),
- devops entities are visible **and alive** in the CMS graph (stage 4),
- key fields and cross-domain edges are correct (stage 5),
- and, only when the above mismatch, the root cause is isolated (stage 6).

## When to use

- "verify my devops setup / data"
- entities or edges missing in the CMS workspace after refresh
- `entity neighbor` returns 0 for relationships that should exist
- after a refresh, visibility does not match expectations
- Not for producing data; not for ad-hoc CMS exploration unrelated to the devops ingest

## Pipeline

Run in order. Each stage emits a receipt (schema in `references/receipt-contract.md`). The
machine-readable flow, including `depends_on`, commands, and gate lists, is in
`references/workflow.yaml`.

1. **resource-readiness** — confirm config + external resources exist before anything else.
   No refresh, no CMS query. Provider-aware: read `git_provider.type` from
   `devops_data_generator/config/app_config.yaml` and check gitlab token / codeup org+AK/SK +
   acr instance + cms workspace + sls project. Required config files: `app_config.yaml`,
   `data_mapping.yaml`, `repo_image_mapping.yaml`, `static_topo.yaml`. See `references/prerequisites.md`.

2. **workspace-alignment** — confirm the config points at the correct CMS workspace and SLS
   entity/topo logstores before refresh. `sls.project` matches/contains `cms.workspace`; all
   entity logstores -> `{workspace}__entity`; all topo logstores -> `{workspace}__topo`;
   `kubernetes_pod` has an entity logstore mapping (missing -> pod SLS write fails). See
   `references/config-contract.md`.

3. **workspace-refresh** — run the canonical refresh:
   `python3 devops_data_generator/main.py --mode single --config devops_data_generator/config`.
   Record the execution summary honestly; distinguish `success` / `partial_success` / `error` /
   `blocked`. Do not substitute a manual wrapper; do not claim refresh happened if only
   verification scripts ran. See `references/script-map.md`.

4. **cms-visibility** — query CMS for visible `devops.*` entities:
   `python3 devops_data_generator/scripts/query_cms_devops.py --config devops_data_generator/config`.
   Check the keep-alive columns (`__method__`, `__last_observed_time__`, `__keep_alive_seconds__`,
   `__first_observed_time__`). When checking relationships via `entity neighbor`, always pass
   `--relation-type` (`uses`/`same_as`/`contains`/`tags`/`owns`); the default returns 0 and is
   misread as a missing relationship. See `references/script-map.md`.

5. **cms-field-check** — inspect key entity fields and the `pod -> docker_image` topology evidence:
   `python3 devops_data_generator/scripts/verify_devops_details.py --config devops_data_generator/config`.
   Derive `git_provider.type` from `app_config.yaml` (never hardcode). Provider-aware assertions:
   `data_source` is `gitlab` or `codeup` (not `aliyun`); repository/release/docker_image/user/
   artifact key fields; image alignment after registry alias normalization with namespace+repo+tag
   match. See `references/script-map.md`.

6. **cms-sls-diagnose** — diagnose only when refresh/visibility produced uncertainty or mismatch:
   `python3 devops_data_generator/scripts/diagnose_cms_entity_store.py --config devops_data_generator/config`.
   Check the four root-cause classes before concluding a relationship is missing: endpoint-id
   encoding mismatch, missing keep-alive fields, cross-source pod id divergence, loose image
   matching. Use the field-check topology evidence before making a pod/image claim. See
   `references/failure-diagnosis.md`.

## Routing rules

- Default: run stages 1 -> 6 in order; stop at the first `BLOCKED`/`FAIL` stage.
- Stage 6 (diagnose) runs only when refresh (3) and visibility (4) justify it. Never the default
  first action; never use it to hide that an earlier stage was skipped.
- Provider awareness: read `git_provider.type` from `app_config.yaml` to pick provider-specific
  assertions; never hardcode it.

## Quality bar (CMS-graph correctness gates)

- **Keep-alive fields**: every entity and edge record must carry `__method__`,
  `__last_observed_time__`, `__keep_alive_seconds__`, `__first_observed_time__`. Without them a
  record is written to the logstore but not alive in the graph, so `entity neighbor` returns 0.
- **Endpoint id alignment**: edge `__src_entity_id__` / `__dest_entity_id__` must use the same
  md5 form as the node `__entity_id__`; raw primary-key strings dangle.
- **`entity neighbor --relation-type`**: always pass it; the default returns 0 and is misread as
  a missing relationship.
- **Registry alias normalization**: compare pod `containers.image` vs `docker_image.full_image_name`
  after normalizing ACR endpoint aliases, not by raw host string.
- **Strict image match**: namespace + repo + tag (or digest) all equal; no match -> no edge; no
  forced fallback link.
- **Cross-source pod id**: keep the CMS original `entity_id` for `k8s.pod`; do not recompute it.

## Hard rules / Do Not Do

- Do not run refresh before resource-readiness + workspace-alignment.
- Do not diagnose before confirming the visibility result.
- Do not declare a relationship missing while only a no-filter `entity neighbor` was tried; retry
  with `--relation-type`.
- Do not hardcode the expected `git_provider` value; derive it from `app_config.yaml`.
- Do not force a fallback link when an image match fails; report the release gap instead.
- Do not claim refresh happened if only verification scripts ran.
- Do not treat mock or obvious fault injection as the core diagnostic value.

## References

- `references/workflow.yaml` — pipeline, routing, quality gates, anti-patterns (machine-readable).
- `references/workflow-stages.md` (+`_zh`) — stage definitions.
- `references/prerequisites.md` (+`_zh`) — resource checklist.
- `references/config-contract.md` (+`_zh`) — config contract.
- `references/receipt-contract.md` (+`_zh`) — receipt schema.
- `references/script-map.md` (+`_zh`) — canonical commands.
- `references/failure-diagnosis.md` (+`_zh`) — diagnosis root-cause classes.
- `references/non-portable-values.md` (+`_zh`) — environment-specific values.

## Scripts

The verification scripts live in `devops_data_generator/scripts/` (shared with the data
generator, not copied into this skill). They are mapped in `references/script-map.md`:

- `devops_data_generator/main.py` — refresh (stage 3).
- `devops_data_generator/scripts/query_cms_devops.py` — visibility (stage 4).
- `devops_data_generator/scripts/verify_devops_details.py` — field check (stage 5).
- `devops_data_generator/scripts/diagnose_cms_entity_store.py` — diagnose (stage 6).
