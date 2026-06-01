# skills/

本目录是 sls-doc 仓库内所有 Agent Skill 的 SSOT。每个 Skill 通过两条路径分发：

1. **本地 Agent 用户**（Claude Code / Cursor / Copilot）：`npx skills add aliyun-sls/sls-doc --skill <name>`
2. **STAROps 数字员工用户**：下载 OSS 上的 tar.gz 包，在控制台「技能管理」上传

仓库内是 SSOT；OSS 上的 tar.gz 必须由本目录手动打包后上传保持同步。

## 目录约定

```
skills/
├── README.md                    # 本文件
├── pack.sh                      # 手动打包脚本
└── <subsite>/                   # 按子站划分命名空间，当前仅 starops
    └── <skill-name>/
        ├── SKILL.md             # 必需，带 YAML frontmatter
        ├── scripts/             # 可选
        └── references/          # 可选
```

`<skill-name>` 必须与 SKILL.md 内的 `name:` 字段一致（npx skills 用 `name:` 字段匹配 `--skill` 过滤参数，不看目录名）。

## SKILL.md frontmatter 要求

```yaml
---
name: my-skill              # 小写 + 连字符，与目录名一致
description: 一句话说清楚 skill 做什么、什么时候触发
---
```

注意：description 内**不要出现冒号** `:`，已知会触发 YAML 解析 bug。

## 打包并上传 OSS（手动）

每次修改 Skill 后需要重新打包并上传 OSS，否则 STAROps 用户拿到的还是旧版本。

```bash
# 从仓库根目录执行
./skills/pack.sh starops rds-inspection

# 产物：dist/rds-inspection.tar.gz
# 上传到 OSS：starops/demo/starops-best-practice/<original-doc-path>/<skill>.tar.gz
```

OSS 上传需要阿里云访问凭证，本仓库不维护凭证；自行用 ossutil 或 OSS Browser 上传。

## 当前 Skill 清单

| Skill | 引用文章 | OSS 路径 |
|---|---|---|
| `starops/rds-inspection` | RDS 周期性自动巡检 | `starops/demo/starops-best-practice/rds-inspection-via-script/docs/rds-inspection.tar.gz` |
| `starops/rds-inspection-via-script-sop` | RDS 周期性自动巡检 | `starops/demo/starops-best-practice/rds-inspection-via-script/docs/rds-inspection-via-script-sop.tar.gz` |
| `starops/service-reliability-flow-sop` | 业务服务可靠性巡检 | `starops/demo/starops-best-practice/business-reliability-flow/docs/service-reliability-flow-sop.tar.gz` |
