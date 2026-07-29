# Workflow Stages

## Stage 1 - Resource Readiness
Goal:
- confirm the required external resources already exist

Checks:
- the active git provider repository exists (GitLab project for `git_provider.type = gitlab`; Codeup repository for `git_provider.type = codeup`)
- ACR instance / namespace / repo exists
- ACK deployment or pods exist
- CMS workspace already exists

Stop condition:
- if any required resource is missing, return `blocked`
- do not continue to workspace alignment or refresh

## Stage 2 - Workspace Alignment
Goal:
- confirm the generator is configured to write into the CMS workspace backing SLS project, not some unrelated SLS project

Checks:
- `cms.workspace` is set
- `sls.project` matches the workspace backing SLS project for this environment
- entity logstore mapping points to the workspace entity logstore
- relationship logstore mapping points to the workspace topo logstore

Stop condition:
- if alignment is wrong, return `blocked`
- do not continue to refresh

## Stage 3 - Workspace Refresh
Goal:
- execute the canonical refresh path that writes entity and relationship data toward the CMS workspace data plane

Canonical entry:
- `python3 devops_data_generator/main.py --mode single --config devops_data_generator/config`

Notes:
- this is the step that matters if the workspace currently has no fresh devops data
- query scripts do not replace this step

## Stage 4 - CMS Visibility Check
Goal:
- verify whether `devops.*` entities are visible in the CMS workspace entity store

Canonical entry:
- `python3 devops_data_generator/scripts/query_cms_devops.py --config devops_data_generator/config`

Success condition:
- expected devops entity types appear in the workspace

## Stage 5 - CMS Field Check
Goal:
- verify key fields on known entities after visibility is confirmed

Canonical entry:
- `python3 devops_data_generator/scripts/verify_devops_details.py --config devops_data_generator/config`

Success condition:
- required entity fields are present and look correct for the current environment

## Stage 6 - CMS/SLS Diagnose
Goal:
- identify why data is not visible or not aligned after refresh/visibility failure

Canonical entry:
- `python3 devops_data_generator/scripts/diagnose_cms_entity_store.py --config devops_data_generator/config`

Use only when:
- resource readiness passed
- workspace alignment is still uncertain or failed
- refresh ran but visibility failed
