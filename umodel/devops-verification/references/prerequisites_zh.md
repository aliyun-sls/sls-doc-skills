# 前置条件

## 必需资源
- 已存在的 git 平台仓库（GitLab 项目或 Codeup 仓库，取决于 `git_provider.type`）
- 如需镜像相关实体，需已存在 ACR 实例和命名空间
- 如需 K8s/镜像关系，需已存在 ACK 部署或 Pod
- 已存在的 CMS Workspace
- 包含 `app_config.yaml` 及相关映射文件的 config 目录

## 必需配置文件
- `devops_data_generator/config/app_config.yaml`
- `devops_data_generator/config/data_mapping.yaml`
- `devops_data_generator/config/repo_image_mapping.yaml`
- `devops_data_generator/config/static_topo.yaml`

## 必需运行时输入
- Git 平台凭据：
  - GitLab Access Token（`git_provider.type = gitlab` 时），或
  - 阿里云 RAM AK/SK + Codeup Organization ID（`git_provider.type = codeup` 时）
- CMS/SLS/ACR 路径所需的阿里云凭据
- 如涉及 Pod 检查，需 kubeconfig 或 CMS Pod 数据源配置

## 阻断条件
以下情况返回 `blocked`：
- CMS Workspace 不存在
- 必需配置文件缺失
- 对应阶段所需的外部资源不存在
