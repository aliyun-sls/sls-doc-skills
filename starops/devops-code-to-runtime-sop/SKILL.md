---
name: devops-code-to-runtime-sop
description: DevOps 多源数据建立代码到运行时跨域关联模型的 SOP Skill，覆盖 schema 理解、环境准备、数据接入、跨域关联建立和端到端验证 7 个步骤
---

# DevOps 代码到运行时跨域关联建模 SOP Skill

## 步骤 1：理解建模架构

1. 向用户确认是否了解 UModel DevOps 域的 5 实体 + 12 关系设计
2. 如不了解，讲解三域串联逻辑：代码域（code_repository / developer / code_release）→ 制品域（image_registry / image）→ 运行时域（kubernetes_pod）
3. 说明当前建模粒度为 release 级，不采集 commit 历史
4. 说明关键跨域关系链：developer → code_repository → code_release → image → kubernetes_pod

确认点：用户理解 5 实体 12 关系的设计意图和三域串联逻辑

## 步骤 2：准备环境与凭据

1. 确认 Git provider 选型（GitLab / Codeup）
2. 如选 GitLab：确认 PAT 已获取（scope: read_api）
3. 如选 Codeup：确认 AK/SK 已获取；询问是否需要 PAT 模式（可见范围更广）
4. 确认 CMS workspace 名称（格式：`default-cms-<主账号ID>-<region>`）
5. 确认 SLS project 名称（通常与 workspace 同名）
6. 确认 ACR 实例 ID 和 region
7. 确认 K8s cluster ID

确认点：所有凭据和环境参数已收集齐全

## 步骤 3：配置数据接入引擎

1. 克隆参考实现仓库：`git clone https://github.com/aliyun-sls/umodel-devops-reference.git`
2. 复制配置样例为实际配置：`cp config/app_config.<provider>.yaml.sample config/app_config.yaml`
3. 按步骤 2 收集的参数填写 `app_config.yaml`
4. 确认 `git_provider.type` 设置正确
5. 确认 `tasks.enabled` 列表包含全部 12 个 task
6. 安装依赖：`pip install -r requirements.txt`

确认点：`python3 -m py_compile` 通过所有 .py 文件，import 链无断裂

## 步骤 4：接入代码域数据

1. 运行接入引擎：`python3 devops_data_generator/main.py --mode single --config devops_data_generator/config`
2. 检查输出日志中 `code_repository`、`developer`、`code_release` 三个 task 状态
3. 如 Codeup 仓库数量少于预期，检查 `auth_mode` 配置（ram vs pat）
4. 如 code_release 为 0，确认仓库是否有 git tag

确认点：代码域 3 个 task 状态为 success，实体数量符合预期

## 步骤 5：接入制品域与运行时域数据

1. 确认 ACR 配置（instance_id / region / AK/SK）正确
2. 确认 CMS workspace 和 K8s cluster_id 正确
3. 运行接入引擎（同步骤 4 命令，12 个 task 一次性执行）
4. 检查 `image_registry`、`image`、`kubernetes_pod` task 状态
5. 如 image 数量明显不足，检查分页是否生效
6. 如 kubernetes_pod 报 404，核实 CMS workspace 名称

确认点：制品域和运行时域 task 状态为 success，数据量级合理

## 步骤 6：建立跨域关联

1. 编辑 `repo_image_mapping.yaml`：为每个需要关联的代码仓库配置对应的 ACR 镜像仓库 ID
2. 编辑 `manage_mapping.yaml`：为每个需要关联的开发者配置负责的代码仓库路径
3. 重新运行接入引擎，确认 `image_sourced_from_code_release` 和 `developer_manages_code_repository` task 不再为 0
4. 如 `image_sourced_from_code_release` 仍为 0，检查 Release tag 与 image tag 是否字面一致

确认点：跨域关系 task 数量 > 0，mapping 配置生效

## 步骤 7：端到端验证

1. 按顺序执行 6 个 verification skill（resource-readiness → workspace-alignment → workspace-refresh → cms-visibility → cms-field-check）
2. 确认所有 stage 结果为 PASS
3. 在 STAROps 中使用数字员工执行 4 层查询：
   - L1：查询 workspace 中 devops 域实体类型和数量
   - L2：列出所有代码仓库及 git_provider
   - L3：查询某仓库关联的开发者
   - L4：查询哪些 Pod 使用了特定镜像
4. 执行 L5 告警追因：从一条告警追溯到关联的代码仓库
5. 如任一层验证失败，回到对应步骤排查

确认点：6 stage 全部 PASS + STAROps L5 告警追因查询成功

## 失败与回滚

| 失败场景 | 回滚方式 |
|---|---|
| API 凭据错误（401/403） | 重新获取凭据，修改 app_config.yaml |
| CMS workspace 不存在（404） | 在 CMS 控制台确认准确名称 |
| ACR 限流 | 分离 task 职责到不同实例 |
| 分页缺失导致数据不全 | 确认使用包含分页修复的版本 |
| mapping 配置错误 | 修改 mapping 文件后重新运行 |

## 召回 Routing

- 用户问"怎么接入 GitLab / Codeup 数据" → 本 Skill
- 用户问"怎么建立代码和镜像的关联" → 本 Skill 步骤 6
- 用户问"怎么验证跨域查询" → 本 Skill 步骤 7
- 用户问"怎么配置数据持续刷新" → practice 常见问题

详细图文操作参考：https://sls.aliyun.com/doc/starops/practices/devops-code-to-runtime/article.html
