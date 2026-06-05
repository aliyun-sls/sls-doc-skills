---
name: dingtalk-integration-sop
description: 为 STAROps 数字员工接入钉钉的 SOP Skill，引导用户完成钉钉应用创建、AppFlow 连接流配置和机器人发布
---

# 为 STAROps 数字员工接入钉钉 SOP Skill

## SOP 概览

1. 在钉钉开放平台创建应用，获取 Client ID / Client Secret
2. 在 AppFlow 创建连接流并完成双凭证授权，获取 WebhookUrl
3. 在钉钉应用中配置机器人并发布
4. 验证集成：在钉钉中与数字员工对话

## 步骤 1：在钉钉开放平台创建应用

引导用户完成以下操作：

1. 登录钉钉开发者平台 https://open-dev.dingtalk.com/
2. 选择目标企业组织
3. 进入**应用开发 > 钉钉应用 > 创建应用**
4. 填写应用名称、描述和图标
5. 在**凭证与基础信息**中记录 Client ID 和 Client Secret

确认点：用户已获得 Client ID 和 Client Secret。

## 步骤 2：通过 AppFlow 创建连接流

引导用户完成以下操作：

1. 登录阿里云 AppFlow 控制台
2. 使用「钉钉 X 智能运维助手」模板
3. 在**账户授权**阶段创建两个凭证：
   a. **钉钉应用机器人凭证**：填入 Client ID、Client Secret 和 IP 白名单
   b. **智能运维助手凭证**：创建新角色，填写角色名称和描述
4. 在**执行动作**中填写 Region、Workspace，选择数字员工
5. 填写连接流名称和描述，单击**发布**
6. 复制页面上的 **WebhookUrl**

确认点：连接流发布成功，WebhookUrl 已复制。

## 步骤 3：配置钉钉应用机器人

引导用户完成以下操作：

1. 在钉钉应用详情页，**添加应用能力 > 机器人**
2. 填写机器人名称、头像、描述
3. 消息接收模式选择 **HTTP 模式**，粘贴 WebhookUrl
4. 在**权限管理**中添加 `qyapi_robot_sendmsg` 权限（必须）
5. 按需添加 `Card.Instance.Write`（交互式卡片）和 `Card.Streaming.Write`（流式卡片）
6. **版本管理与发布**中创建版本，配置使用范围后发布

确认点：应用状态变为「已上线」。

## 步骤 4：验证集成

引导用户完成以下操作：

1. 在钉钉中搜索机器人名称
2. 发起单聊，发送一条查询消息（例如「查询当前 workspace 下 K8s Pod 列表」）
3. 确认数字员工正确响应，返回结果中包含 RequestID

确认点：数字员工在钉钉中成功响应查询。

## 输出与交付

SOP 跑完后用户获得：

- 一个已上线的钉钉企业内部应用，集成了 STAROps 数字员工
- 可在钉钉单聊或群内通过 @机器人与数字员工对话
- WebhookUrl 配置完成，消息链路贯通

## 失败与回滚

| 失败步骤 | 现象 | 处置 |
|---|---|---|
| 步骤 2 凭证创建 | Client ID/Secret 填写错误 | 删除凭证重新创建 |
| 步骤 2 发布 | 连接流发布失败 | 检查两个凭证是否均已授权，检查 Region/Workspace 是否正确 |
| 步骤 4 验证 | 发送消息无响应 | 检查连接流是否已发布；检查 WebhookUrl 是否正确；查看 AppFlow 执行日志 |

## 召回 Routing

以下提问应路由到本 SOP Skill：

- 「怎么把 STAROps 接入钉钉」
- 「配置钉钉机器人」
- 「钉钉里怎么用数字员工」
- 「AppFlow 连接流怎么配」

详细图文操作参考：https://sls.aliyun.com/doc/starops/practices/dingtalk-integration/article.html
