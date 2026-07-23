# 失败诊断路由

## 路由 1 — 资源缺失
症状：Workspace / 仓库 / 部署不存在。返回 `blocked`。

## 路由 2 — Workspace 未对齐
症状：refresh 似乎运行但数据未出现在 CMS。检查 `sls.project` 和 logstore 映射。

## 路由 3 — Refresh 失败
症状：`main.py --mode single` 返回 task 失败或关键 git task 被跳过/失败。

## 路由 4 — Refresh 成功但可见性失败
症状：refresh 成功但 `query_cms_devops.py` 找不到 `devops.*` 实体。运行 `diagnose_cms_entity_store.py`。

## 路由 5 — 可见性通过但字段检查失败
症状：实体可见但关键字段缺失或错误。检查配置映射和 task 生成逻辑。
