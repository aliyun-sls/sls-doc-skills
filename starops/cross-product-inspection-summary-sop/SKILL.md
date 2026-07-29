---
name: cross-product-inspection-summary-sop
description: Guide users and Agents through building product inspection Missions and a cross-product summary Mission that consumes their reports into a unified report.
---

# 跨产品巡检汇总报告 SOP

本 Skill 指导用户或 Agent 从零构建一套跨产品巡检汇总机制：先建立单产品巡检 Mission，再建立汇总 Mission 消费它们的报告。首期以 ECS 主机、Kubernetes 集群和 RDS 数据库为例。

## 使用场景

- 已有多个单产品巡检任务，但结果分散，缺少跨产品统一视图。
- 希望减少分散通知，统一风险排序，持续复核巡检结果。
- 需要可归档、可复核的汇总报告。

## 前置条件

- 已接入 STAROps，有数字员工和 workspace。
- 已有或愿意创建 ECS 主机巡检、Kubernetes 集群巡检、RDS 巡检三个长期任务 Mission。
- 各巡检 Mission 能产出当日 artifacts 报告。
- 数字员工对同 workspace 下其他 Mission 的 artifacts 目录有读取权限。

## 执行流程

### 1. 确认产品巡检 Mission

对每个要纳入汇总的产品，确认或创建一个独立巡检 Mission：

- 绑定本产品巡检对象和数据范围。
- 调用本产品巡检 Skill，按固定口径取数、计算、判定和追因。
- 配置独立调度（如工作日 06:00）和重试。
- 确认产物路径遵循 `artifacts/<YYYY-MM>/<MM-DD>/` 目录约定。

记录每个产品 Mission 的 ID、Skill、cron、报告命名模式和通知配置。

### 2. 设计汇总 Mission 的允许列表

汇总 Mission 通过显式允许列表确定本轮应参与汇总的产品 Mission。允许列表写入 Mission 的任务描述：

- 产品名 → Mission ID 的映射。
- 每个产品的报告命名模式（用于 ls 当日目录找 .md）。
- 预期覆盖范围（哪些产品应检）。

允许列表是首选发现方式，便于审计。自动枚举只能作为辅助，不能让未知报告静默进入正式汇总。

### 3. 配置汇总 Mission

汇总 Mission 配置：

- **触发时机**：定在所有产品巡检 Mission 之后（如工作日 06:30，错后于 06:00）。
- **读取方式**：显式 Mission ID + ls 当日目录找 .md，不依赖文件名。提取报告内容里的概览表和等级摘要表，转成内部 JSON 再归并。
- **归并逻辑**：优先使用产品报告中的实体、设备和关系证据归并同一风险；需要补充业务影响面或共享依赖时查询 UModel，无关系证据时保留分列。
- **输出**：7 部分汇总报告（覆盖与新鲜度/总体风险/跨产品风险事件/产品异常明细/数据与证据缺口/行动与复核/原始报告索引），Markdown + HTML 双格式。
- **通知**：有 P0/P1 异常时通知，全 Normal 时归档。
- **缺失处理**：某产品当日报告读不到时显式标"数据缺失"，不静默跳过。

### 4. 执行一次测试汇总

触发汇总 Mission 执行一次，确认：

- 能按允许列表读取所有产品当日报告。
- 跨产品归并能识别同一实体或同一业务链路上的关联异常。
- 汇总报告包含覆盖、风险、归并、明细、缺口、行动和索引。
- 缺失或过期的产品在报告里显式标注。
- Markdown 和 HTML 都生成，归档到 artifacts 目录。

### 5. 验收

检查汇总报告是否满足：

- 三份产品结果都通过覆盖校验，记录来源和批次。
- 至少一组跨产品异常能形成风险事件（或有明确无关系结论保持分列）。
- 缺失、过期、部分失败时不产生虚假健康结论。
- 全程只读，未执行资源或配置变更。

## 边界

- 汇总 Mission 只读取和归并，不重新实现产品检查项。
- 跨 Mission 消费只读取允许列表中的报告产物。
- 不自动扩缩容、不修改阈值、不重启资源、不执行产品配置变更。
- 报告进入通知和归档前清理敏感信息。

## 升级条件

以下情况需要人工介入或扩大调查：

- 多个产品异常时间接近，但现有关系无法判断是否同源。
- 产品报告结论冲突，需要扩大证据范围。
- 关键关系缺失，需要规划补哪些指标、日志、调用或变更数据。
- 异常形态超出已有产品 Skill 和汇总规则。

## 相关入口

- 产品巡检 Skill：ECS 主机巡检、Kubernetes 集群巡检、RDS 数据库巡检（平台内置或 employee）。
- 汇总 Mission 配置参考：本实践 `verification.md` 记录了真实 Mission ID 和配置。
- 汇总报告样本：`assets/sample-summary-report.{html,md}`。
