# Failure Diagnosis Routing

## Principle
Diagnose only after the cheaper and more deterministic checks have already run.

## Route 1 - Missing Resource
Symptoms:
- workspace missing
- repo missing
- deployment missing

Action:
- return `blocked`
- do not run refresh or verification as if the environment were ready

## Route 2 - Misaligned Workspace Target
Symptoms:
- refresh seems to run but data does not appear in CMS workspace
- configured `sls.project` is not the workspace backing SLS project
- logstore mapping does not point to the workspace entity/topo logstores

Action:
- stop and fix alignment first
- use workspace diagnosis only to confirm the backing project/logstores

## Route 3 - Refresh Failed
Symptoms:
- `main.py --mode single` returns task failures or critical git tasks (repository / user / release, regardless of provider) are skipped/failed

Action:
- treat refresh as failed
- do not trust downstream visibility checks as proof that the refresh path worked

## Route 4 - Refresh Succeeded But Visibility Failed
Symptoms:
- refresh ran successfully enough to be meaningful
- `query_cms_devops.py` still cannot find expected devops entities

Action:
- run `diagnose_cms_entity_store.py`
- inspect workspace metadata, entity types, and devops presence

## Route 5 - Visibility Passed But Field Check Failed
Symptoms:
- entities are visible
- key fields are missing or wrong

Action:
- inspect config mappings and task-specific generation logic
- do not treat this as a workspace-alignment problem by default
