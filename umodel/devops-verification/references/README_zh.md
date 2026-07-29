# 验证参考层

本目录包含所有验证 Skill 共享的规则和契约。

- `prerequisites.md` — 前置条件（必需资源 / 文件 / 凭据）
- `workflow-stages.md` — 6 个验证阶段定义
- `config-contract.md` — 配置契约（app_config.yaml 结构）
- `receipt-contract.md` — 验证结果输出格式
- `failure-diagnosis.md` — 失败路由规则
- `non-portable-values.md` — 不可硬编码的环境值清单
- `script-map.md` — 脚本入口映射

Skill 入口在 `../SKILL.md`，不在本目录。本目录是 `devops-verification` skill 读取的契约真相源，不包含运行时数据或密钥。
