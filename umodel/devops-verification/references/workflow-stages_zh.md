# 验证阶段

## 阶段 1 — 资源就绪
确认外部资源已存在：git 平台仓库（GitLab 或 Codeup）、ACR 实例、ACK 部署、CMS Workspace。

## 阶段 2 — Workspace 对齐
确认 `sls.project` 指向 CMS Workspace 对应的 SLS Project，entity/topo logstore 映射正确。

## 阶段 3 — Workspace 刷新
执行数据采集：`python3 devops_data_generator/main.py --mode single --config devops_data_generator/config`

## 阶段 4 — CMS 可见性
查询 CMS Workspace，确认 `devops.*` 实体可见。

## 阶段 5 — CMS 字段检查
验证关键实体字段值正确（按 `git_provider.type` 断言 `data_source=gitlab` 或 `data_source=codeup`）。

## 阶段 6 — CMS/SLS 诊断
仅在刷新或可见性失败时进入，诊断 Workspace 与 SLS 对齐问题。
