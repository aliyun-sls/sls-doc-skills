# sls-doc-skills

Agent Skills SSOT for the [sls-doc](https://github.com/aliyun-sls/sls-doc) STAROps best-practices subsite. Each Skill is distributed via two channels:

1. **Local Agent users** (Claude Code / Cursor / Copilot): `npx skills add aliyun-sls/sls-doc-skills --skill <name>`
2. **STAROps digital-employee users**: download the OSS tar.gz and upload via console「技能管理」

This repo is the SSOT; OSS tar.gz must be repacked from here on every change.

## Layout

```
.
├── README.md
├── pack.sh                     # Manual packer
└── <subsite>/                  # Namespace by subsite (currently only starops)
    └── <skill-name>/
        ├── SKILL.md            # Required, with YAML frontmatter
        ├── scripts/            # Optional
        └── references/         # Optional
```

`<skill-name>` MUST match the `name:` field inside SKILL.md (npx skills filters by `name:`, not directory name).

## SKILL.md frontmatter

```yaml
---
name: my-skill              # lowercase + hyphens, matches directory name
description: One sentence: what it does + when it triggers
---
```

Note: avoid colons `:` inside description — known YAML parsing bug.

## Pack + upload to OSS (manual)

After every Skill change, repack and reupload — otherwise STAROps users keep getting the old version.

```bash
# From repo root
./pack.sh starops rds-inspection

# Output: dist/rds-inspection.tar.gz
# Upload to: starops/demo/starops-best-practice/<doc-path>/<skill>.tar.gz
```

OSS upload requires Aliyun credentials; this repo holds none. Use ossutil or OSS Browser.

## Current Skills

| Skill | Referenced by | OSS path |
|---|---|---|
| `starops/rds-inspection` | [RDS 周期性自动巡检](https://sls.aliyun.com/doc/starops/practices/rds-inspection-via-script/article.html) | `starops/demo/starops-best-practice/rds-inspection-via-script/docs/rds-inspection.tar.gz` |
| `starops/rds-inspection-via-script-sop` | [RDS 周期性自动巡检](https://sls.aliyun.com/doc/starops/practices/rds-inspection-via-script/article.html) | `starops/demo/starops-best-practice/rds-inspection-via-script/docs/rds-inspection-via-script-sop.tar.gz` |
| `starops/service-reliability-flow-sop` | [业务服务可靠性巡检](https://sls.aliyun.com/doc/starops/practices/business-reliability-flow/article.html) | `starops/demo/starops-best-practice/business-reliability-flow/docs/service-reliability-flow-sop.tar.gz` |
