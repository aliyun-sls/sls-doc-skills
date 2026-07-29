# Config Contract

## Single Config Rule
All runtime-facing verification and refresh behavior must read configuration from the repository config surface, not from scattered ad hoc values.

Primary source:
- `devops_data_generator/config/app_config.yaml`

Supporting mapping files:
- `devops_data_generator/config/data_mapping.yaml`
- `devops_data_generator/config/repo_image_mapping.yaml`
- `devops_data_generator/config/static_topo.yaml`

## Active Git Provider
- `git_provider.type` selects the active git provider: `gitlab` or `codeup`.
- Only the matching provider block (`gitlab` or `codeup`) needs real values; the other can stay empty or be omitted entirely.

## Core Sections
### `gitlab` (when `git_provider.type = gitlab`)
- repository URL
- access token
- group/project identifiers
- release tag

### `codeup` (when `git_provider.type = codeup`)
- organization id (Alibaba Cloud DevOps organization)
- access key id / secret (Alibaba Cloud RAM)
- endpoint override (optional; defaults to `devops.cn-hangzhou.aliyuncs.com`)
- release tag

### `acr`
- instance id
- region
- access credentials

### `cms`
- endpoint
- workspace
- namespace filter
- access credentials

### `kubernetes`
- data source: `k8s` or `cms`
- cluster id
- namespace filter
- kubeconfig path
- context

### `sls`
- endpoint
- access credentials
- project
- logstore mapping for entities and relationships

### `tasks`
- enabled task list
- dependency order
- shared data TTL
- skipped SLS upload list

## Alignment Rule
For CMS visibility to work, `sls.project` and the logstore mappings must point at the CMS workspace backing SLS project and its entity/topo logstores for the current environment.

## Verification Script Rule
- `query_cms_devops.py`
- `verify_devops_details.py`
- `diagnose_cms_entity_store.py`

These scripts must load their runtime config through the shared config loader path, not independent environment-only inputs.
