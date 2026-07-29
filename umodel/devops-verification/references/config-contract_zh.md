# 配置契约

## 配置来源
所有运行时行为必须从仓库配置文件读取，不得使用散落的硬编码值。

主配置：`devops_data_generator/config/app_config.yaml`

## 活动 Git 平台
- `git_provider.type` 选择活动平台：`gitlab` 或 `codeup`
- 只有对应平台的配置块需要填写真实值

## 核心配置段

### `gitlab`（`git_provider.type = gitlab` 时）
- 仓库 URL、Access Token、group/project 标识、release tag

### `codeup`（`git_provider.type = codeup` 时）
- Organization ID、AK/SK、auth_mode（ram/pat）、access_token、endpoint

### `acr`
- 实例 ID、区域、凭据

### `cms`
- 端点、Workspace、命名空间过滤、凭据

### `sls`
- 端点、凭据、Project、entity/topo logstore 映射

### `tasks`
- 启用任务列表、依赖顺序、共享数据 TTL
