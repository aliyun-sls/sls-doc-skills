# Verification Reference Layer

## Purpose
- `references/` is the contract layer for the `devops-verification` skill (one skill, not a per-runtime copy).
- It exists so the skill has one set of workflow rules instead of duplicating them per stage.

## Scope
- workflow stages
- prerequisites
- config contract
- receipt contract
- failure diagnosis routing
- script mapping
- non-portable values

## Non-goals
- not a Python runtime package
- not a replacement for `devops_data_generator/shared`
- not a place to store environment instance values or secrets
- not the place to define runtime-specific wrappers

## Canonical Rule
- refresh data into CMS workspace first
- verify visibility second
- diagnose only when refresh or verification does not produce the expected result

## Consumers
- the `devops-verification` skill (`../SKILL.md` + `workflow.yaml`)
- maintainers reading the repository workflow directly
