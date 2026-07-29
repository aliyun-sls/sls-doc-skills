# Script Map

## Canonical Refresh Entry
- command:
  - `python3 devops_data_generator/main.py --mode single --config devops_data_generator/config`
- purpose:
  - execute the generator/orchestrator path that fetches data, maps entities/relationships, and writes toward the configured SLS target
- why canonical:
  - this is the real refresh path used by the repository

## Generator Core
- `devops_data_generator/orchestrator.py`
- role:
  - loads config
  - builds task graph
  - executes entity and relationship tasks
  - sends data through `SlsDataSender`

## Verification Common Loader
- `devops_data_generator/scripts/cms_script_common.py`
- role:
  - unify CMS verification scripts on the repository config loader

## Visibility Check
- command:
  - `python3 devops_data_generator/scripts/query_cms_devops.py --config devops_data_generator/config`
- role:
  - query whether `devops.*` entities are visible in the CMS workspace

## Field Check
- command:
  - `python3 devops_data_generator/scripts/verify_devops_details.py --config devops_data_generator/config`
- role:
  - inspect key fields on code repository, release, image, and registry entities

## Diagnose
- command:
  - `python3 devops_data_generator/scripts/diagnose_cms_entity_store.py --config devops_data_generator/config`
- role:
  - inspect workspace metadata, entity type surface, and devops presence

## Historical Note
- The repository previously had a historical GitLab wrapper directory.
- It has been removed during repository cleanup.
- First-wave skills depend only on shared docs and canonical Python entries under `devops_data_generator/`.
