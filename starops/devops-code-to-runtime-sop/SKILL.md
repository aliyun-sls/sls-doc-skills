---
name: devops-code-to-runtime-sop
description: 告警追因到代码变更：DevOps 数据接入与建模 Guide Skill，指导用户理解 17/36 参考模型、接入代码域和制品域、建立跨域关系，并完成分阶段验证。
---

# 告警追因到代码变更：DevOps 数据接入与建模 Guide Skill

## 使用场景

当用户希望把 Git 平台、制品库、CI/CD 或组织系统中的 DevOps 数据接入 UModel，并让 STAROps 能从告警和运行时对象追到镜像、发布、代码仓库和责任人时，使用本 Skill。

本 Skill 是 Guide Skill，用于指导接入、配置和验证流程，不作为长期运行的 STAROps Runtime Skill。

## 前置条件

执行前先确认以下事实：

1. 目标 STAROps workspace 已存在，并具备写入 UModel 实体和关系的权限。
2. workspace 中已有应用服务、Pod、K8s 或云资源等运行时对象。
3. 用户已选择 Git provider，当前参考实现覆盖 GitLab 和 Codeup。
4. 用户已准备镜像仓库数据源，当前参考实现以 ACR 为主要来源。
5. 用户理解 17 个 EntitySet 和 36 个 EntitySetLink 是参考模型范围，其中当前有 producer 支撑的对象是用户、代码仓库、发布、Pull Request、构建产物和容器镜像。
6. 组织、项目、工作项、里程碑、流水线、流水线运行、Helm Chart、二进制包、NPM 包、单测用例和部署记录属于 schema-only，需要额外 adapter 后才能作为生产追因证据。

## 执行流程

### 1. 明确追因目标

先和用户确认本次要追到哪一层。最小可用链路是：

服务 / Pod → 镜像 → 构建产物 → 发布 → 代码仓库 → 开发者或负责人。

如果用户要求追到工作项、流水线、部署记录、审批信息或 commit 级明细，应标记为扩展模型，并单独确认数据源和 adapter 是否已经具备。

### 2. 准备接入信息

收集以下信息：

| 类型 | 需要确认的内容 |
|---|---|
| workspace | STAROps workspace、对应 SLS project、实体和关系写入面 |
| Git provider | GitLab 或 Codeup、认证方式、可见仓库范围 |
| 镜像仓库 | ACR 实例、region、镜像仓库和 tag 规则 |
| 运行时对象 | K8s cluster、Pod、应用服务或云资源是否已在 workspace 中可见 |
| 映射规则 | 仓库、发布、镜像、Pod 和负责人之间的显式映射或命名规则 |

只读采集优先。不要引导用户执行生产变更、删除资源或修改业务配置。

### 3. 接入代码域

指导用户使用参考实现接入 Git provider。接入完成后，需要能获得代码仓库、开发者、发布和 Pull Request 等对象。

检查点：

- Git provider 类型与认证方式正确。
- 可见仓库范围符合用户预期。
- 发布对象来自真实 tag 或 release 数据。
- Pull Request 和开发者信息可被稳定采集。
- 不把不可见仓库解释为不存在仓库，应先检查权限范围。

### 4. 接入制品域

指导用户接入容器镜像仓库和构建产物数据。当前参考实现以 ACR 为主要来源。

检查点：

- 镜像、镜像 tag 和构建产物可采集。
- 发布与镜像的关系来自真实版本规则或显式映射。
- 镜像 tag 和 release tag 不一致时，要求用户提供映射规则。
- 同一镜像仓库存在多个访问端点或别名时（例如 VPC 端点与公网或特定端点），应在接入阶段完成归一化，避免 Pod 侧镜像和制品侧镜像因 host 不同无法对齐。
- 测试 tag、分支 tag 或临时构建镜像可能没有对应 release 记录，追因应停在构建产物到发布这一段缺口，不要把测试 tag 硬连到某个发布版本冒充闭环。
- 不通过自然语言猜测拼接发布和镜像关系。

### 5. 建立跨域关系

优先建立核心追因链所需关系：

| 关系 | 检查点 |
|---|---|
| 代码仓库 → 发布 | 发布能回到代码仓库 |
| 发布 → 构建产物 / 镜像 | 发布能关联制品 |
| Pod → 镜像 | 运行时对象能回到镜像 |
| 开发者 / 负责人 → 仓库 | 责任归属来自成员、owner 或显式配置 |
| 应用服务 / Pod → DevOps 对象 | 告警能进入代码变更追因链 |

缺少任一关系时，在输出中标记缺失段，并给出补接入建议。不要把缺数据写成没有风险。

### 6. 执行分阶段验证

按顺序执行 staged verification，不跳过失败阶段。

| 阶段 | 目标 | 失败时处理 |
|---|---|---|
| resource-readiness | 确认 Git provider、镜像仓库、workspace 和运行时数据可访问 | 停止刷新，补权限或资源 |
| workspace-alignment | 确认数据会写入目标 workspace | 修正 workspace 和数据写入配置 |
| workspace-refresh | 执行真实刷新路径 | 记录失败 task 和原因 |
| cms-visibility | 确认 DevOps 实体在 CMS workspace 可见 | 检查刷新、写入面和可见性 |
| cms-field-check | 检查关键字段和 provider 差异 | 修正 adapter 或映射 |
| cms-sls-diagnose | 在刷新或可见性异常时定位问题 | 输出 workspace、权限或数据源缺口 |

`meta-skill-sample/` 中的验证 Skills 只用于上述分阶段验证，不代表长期 Runtime Skill。

### 7. 进行 STAROps 查询验证

验证通过后，引导用户在 STAROps 中检查以下问题：

1. workspace 中能看到哪些 DevOps 域实体。
2. 代码仓库列表和 Git provider 是否符合预期。
3. 某个仓库能否关联开发者或负责人。
4. 某个 Pod 使用了哪些镜像。
5. 给定告警或运行时对象，是否能沿服务 / Pod / 镜像 / 构建产物 / 发布 / 仓库 / 开发者链路输出追因证据。

查询 `entity neighbor` 时必须指定 `--relation-type`（如 `uses` / `same_as` / `contains` / `tags` / `owns`），不带 filter 默认返回 0，会被误判为关系缺失。

如果 L5 追因失败，回到缺失关系所在阶段，不继续声称端到端可用。

## 输出结构

每次执行本 Skill 后，输出以下内容：

| 模块 | 内容 |
|---|---|
| 范围确认 | 本次覆盖的 Git provider、镜像仓库、workspace、运行时对象 |
| 模型边界 | 17/36 参考模型、当前 producer 覆盖、schema-only 对象 |
| 接入结果 | 代码域、制品域和跨域关系的完成情况 |
| 验证结果 | 6 个 staged verification 阶段的通过、阻塞或降级原因 |
| STAROps 查询 | L1 到 L5 查询验证结果 |
| 缺口清单 | 缺少的数据源、字段、关系、权限或 adapter |
| 后续建议 | 需要补接入、补映射、补 adapter 或进入人工复核的事项 |

## 升级条件

出现以下情况时，不继续按当前流程推进，应升级为开放调查或回到设计阶段：

- 用户要求追到 schema-only 对象，但没有对应 adapter。
- commit 级追溯、Jenkins、GitHub Actions、Argo、Tekton、工作项或部署记录尚未接入。
- Git provider 权限导致仓库范围明显不完整。
- 镜像与发布缺少真实映射规则。
- workspace 中缺少运行时对象或 DevOps 实体不可见。
- STAROps 查询结果和用户认知冲突，需要补证据或反证。

## 边界

- 本 Skill 只指导只读接入、验证和追因，不执行生产变更。
- 17/36 是参考模型范围，生产可用范围以 producer 覆盖和验证证据为准。
- schema-only 对象不能写成已采集对象。
- 当前主线是 release 级追因，commit 级追溯属于扩展方向。
- 验证 Skill 只用于分阶段检查数据完整性。
- CMS 图引擎按保活模型运行，DevOps 实体和关系需要持续刷新；producer 不持续刷新时实体过期出图、边悬空，追因可能在中间节点停止。
- 涉及 Token、Secret、账号、私有仓库、IP 或业务敏感数据时，公开输出只保留脱敏摘要。

## 召回 Routing

- 用户问如何接入 GitLab / Codeup 数据 → 使用本 Skill。
- 用户问如何建立代码、发布、镜像和 Pod 的关联 → 使用本 Skill 的跨域关系步骤。
- 用户问如何验证 DevOps 数据是否进入 workspace → 使用本 Skill 的 staged verification 步骤。
- 用户问如何把 MR、pipeline、job log 作为一次性补证 → 建议评估 MCP 接入。
- 用户问如何接入 Jenkins、GitHub Actions、Argo、Tekton、工作项或部署记录 → 说明当前属于扩展模型，需要先补 adapter 和验证。

详细图文操作参考：https://sls.aliyun.com/doc/starops/practices/devops-code-to-runtime/article.html
