# 不可移植值

## 禁止在共享 Skill 中硬编码
- GitLab Access Token
- Codeup Organization ID
- 阿里云 AK/SK
- CMS Workspace 名
- SLS Project 名
- ACR 实例 ID / 镜像仓库 ID
- ACK 集群 ID
- kubeconfig 内容
- 环境特定的仓库-镜像映射值

## 可共享的规则
- 配置来自 `app_config.yaml` 和映射文件
- refresh 在 visibility 和 diagnose 之前
- Workspace 缺失 = `blocked`
- 共享文档是仓库根资产，不是 Python 运行时包资产
