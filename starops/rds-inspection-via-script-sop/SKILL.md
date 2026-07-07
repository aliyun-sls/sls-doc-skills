---
name: rds-inspection-via-script-sop
description: RDS 巡检最佳实践的 Guide Skill。加载后 Agent 按 5 步 SOP 协助用户在 STAROps 内走完全流程配置：准备 meta skill 包、建数字员工、建长期任务、配通知、闭环验证，最终客户周期性收到结构化巡检报告。
---

# RDS 周期性自动巡检 Guide Skill

> **类型**：Guide Skill（与 [人读版实践文档](https://sls.aliyun.com/doc/starops/practices/rds-inspection-via-script/article.html) 一一对应、二者俱在）。教 Agent 怎么协助用户走完 5 步 SOP，最终落地一个活跃的 RDS 周期性巡检闭环。
>
> **不是** RDS 巡检本身的业务 Skill。业务 Skill 是 `rds-inspection`（同仓兄弟 skill），安装命令：`npx skills add aliyun-sls/sls-doc-skills --skill rds-inspection`，或下载 [rds-inspection.tar.gz](https://starops-demo.oss-cn-beijing.aliyuncs.com/starops/demo/starops-best-practice/rds-inspection-via-script/docs/rds-inspection.tar.gz)。

## 能力边界

Agent **能做**：
- 引导用户获取 meta skill 包（Path A 直接安装 `rds-inspection` 业务 skill；Path B 引用 [Replay Prompt 附录](https://sls.aliyun.com/doc/starops/practices/rds-inspection-via-script/article.html#附录-path-b-replay-prompt)）
- 校验 meta skill 包文件结构、Python 语法、`--list-cases` 输出
- 把 [Replay Prompt 附录](https://sls.aliyun.com/doc/starops/practices/rds-inspection-via-script/article.html#附录-path-b-replay-prompt) 整段交给用户（用户去 STAROps 智能运维助手粘贴）
- 给用户在 STAROps 控制台操作时所需的精确话术、命名建议、任务输入模板
- 解析任务执行输出的结构化 JSON

Agent **不能做**：
- 替用户在 STAROps 控制台 GUI 里点按钮（建数字员工 / 建长期任务 / 配通知 / 触发任务都必须用户去控制台操作）
- 替用户接收通知（用户必须回报"已收到"才能闭环）

所以本流程的每一步分两类动作：**Agent 在本地完成的**（拷文件、校验、生成话术）+ **由用户在 STAROps 完成、Agent 给出指引和验收清单的**。

## SOP 概览（对应 [实践文档 推荐落地形态段](https://sls.aliyun.com/doc/starops/practices/rds-inspection-via-script/article.html)）

| # | 步骤 | Agent 角色 | 用户角色 |
|---|---|---|---|
| 1 | 准备 RDS 巡检 meta skill 包 | 拷文件 + 校验 / 或 抽 Prompt | 控制台粘 Prompt（仅 Path B） |
| 2 | 创建数字员工并绑定 Skill | 给命名 + 步骤话术 | 控制台操作 |
| 3 | 创建长期任务并引用 Skill | 给任务输入模板 | 控制台操作 |
| 4 | 配置通知对象 | 提醒先测后用 | 控制台操作 + 发测试消息 |
| 5 | 等待执行 + 闭环验证 | 给 4 件事 checklist | 控制台 + 回报送达 |

> 5 步全部完成才算闭环；任一步未通过完成判据，不要推进下一步。

---

## 步骤 1：准备 RDS 巡检 meta skill 包

> 对应 [实践文档 推荐落地形态段](https://sls.aliyun.com/doc/starops/practices/rds-inspection-via-script/article.html)。

### Agent 决策：选 Path A 还是 Path B

**默认走 Path A（直接复用现成样品）**，除非用户明确说"要为我的自家场景演进 meta skill"或"现有样品不满足 X 需求"，才转 Path B。

### Path A：复用现成的 `rds-inspection` 业务 skill 包

让用户在工作目录执行二选一：

```bash
# 方式 1：npx 安装到 <用户工作目录>/.claude/skills/rds-inspection/ 等
npx skills add aliyun-sls/sls-doc-skills --skill rds-inspection

# 方式 2：直接下载 tar.gz 并展开
curl -L -o /tmp/rds-inspection.tar.gz https://starops-demo.oss-cn-beijing.aliyuncs.com/starops/demo/starops-best-practice/rds-inspection-via-script/docs/rds-inspection.tar.gz
tar -xzf /tmp/rds-inspection.tar.gz -C <用户工作目录>/
```

校验产物（必须全过）：

1. 文件总数恰好 14 个：1 SKILL.md + 6 scripts/*.py + 7 references/*.md
2. `python3 -m py_compile <用户工作目录>/rds-inspection/scripts/*.py` 六个脚本无语法错误
3. 五个子脚本 `--list-cases` 累计输出 27 项（核心 7 + 性能 6 + 安全 6 + 关联日志 2 + 趋势检测 6）：

```bash
python3 <用户工作目录>/rds-inspection/scripts/rds-core-inspection.py --list-cases --region test --project test --metricstore test
python3 <用户工作目录>/rds-inspection/scripts/rds-performance-inspection.py --list-cases --region test --project test --metricstore test
python3 <用户工作目录>/rds-inspection/scripts/rds-security-inspection.py --list-cases --region test --project test --metricstore test
python3 <用户工作目录>/rds-inspection/scripts/rds-logs-inspection.py --list-cases --region test --project test --metricstore test --audit-logstore test
python3 <用户工作目录>/rds-inspection/scripts/rds-trend-inspection.py --list-cases --region test --project test --metricstore test
```

任一校验失败 → 不要继续步骤 2，回报用户"样品损坏，需要回滚或转 Path B"。

### Path B：用 [Replay Prompt 附录](https://sls.aliyun.com/doc/starops/practices/rds-inspection-via-script/article.html#附录-path-b-replay-prompt) 在 STAROps 智能运维助手现场生成

Agent 执行：

1. 打开实践文档的 [附录：Path B Replay Prompt](https://sls.aliyun.com/doc/starops/practices/rds-inspection-via-script/article.html#附录-path-b-replay-prompt)，取`重放 Prompt`围栏内的全部内容
2. 完整复制给用户（不要截断、不要改写要素）
3. 告诉用户："打开 STAROps 智能运维助手 → 新建对话 → 整段粘贴 → 等待生成 → 把产物拷到 `<用户工作目录>/rds-inspection/`"
4. 用户拷回后，对生成的目录跑一遍 Path A 同款的 3 项校验

### 完成判据

- `<用户工作目录>/rds-inspection/` 存在
- 文件结构 14 个、Python 全过、`--list-cases` 27 项

判据满足 → 进步骤 2。

---

## 步骤 2：创建数字员工并绑定 Skill

> 对应 [实践文档 推荐落地形态段](https://sls.aliyun.com/doc/starops/practices/rds-inspection-via-script/article.html)。本步骤 Agent 不直接操作 STAROps；提供精确话术，由用户在控制台执行。

### Agent 给用户的指引

> 请在 STAROps 控制台执行以下三步：
>
> 1. `数字员工` → `新建` → 名称建议 `rds-inspection`（一个数字员工只承载一类巡检；不要混入其他业务）
> 2. 进入该数字员工详情页 → `技能管理` → `添加技能` → 上传 `<用户工作目录>/rds-inspection/` 整个目录作为 Skill 包
> 3. 上传完成后点击`启用`（**仅"存在"不算启用，必须点击启用按钮**）

### 完成判据（必须用户回报）

让用户回答两个问题：

1. 该数字员工的技能管理页能否看到 RDS 巡检 Skill？
2. Skill 状态是否显示`已启用`（不是`未启用`、不是仅`存在`）？

两问都`是` → 进步骤 3。任一`否` → 提示用户回控制台核实，常见原因是没点启用按钮、或上传时报 frontmatter 错误（回到步骤 1 校验）。

---

## 步骤 3：创建长期任务并引用 Skill

> 对应 [实践文档 推荐落地形态段](https://sls.aliyun.com/doc/starops/practices/rds-inspection-via-script/article.html)。

### Agent 给用户的任务输入模板

> 在 STAROps 控制台 → `长期任务` → `新建` → 填写：
>
> - 任务名：`RDS 数据库实例健康巡检计划`（一眼能看出用途）
> - 执行周期：建议 1h（按用户实际需求可调，但避免低于 5min）
> - **任务输入（必须显式引用 Skill 名）**：
>
>   ```
>   使用 /aliyun rds 巡检 skill 对 [实例范围] 执行健康巡检，窗口 last_1h。
>   要求：覆盖核心指标 / 性能 / 安全 / 关联日志 / 趋势检测五个维度共 27 项；输出结构化 JSON；按 P1/P2/P3 分级；每个异常项附带原始采样（raw_samples，≤10 条）、上下游影响（topology）、追因提示（investigation_hints）、证据来源（evidence_sources）和置信度（confidence）；不执行任何变更；不访问数据库执行 SQL。
>   ```
>
>   （把 [实例范围] 替换成用户实际要巡检的 RDS 实例、业务线或标签。数据源参数由 STAROps 运行时按巡检对象自动解析，用户无需配置。若实例未接入审计日志，日志维度 2 项会返回明确 error，其他 25 项不受影响）

Agent 主动询问用户要巡检的实例范围和窗口，把模板填实后再交给用户复制。

### 反例提醒

> ❌ 不要用"帮我巡检 RDS"这种自然语言当任务输入，执行时会偏离既定流程或反复要求补上下文。任务输入必须**显式引用 `/aliyun rds 巡检 skill`**。

### 完成判据（必须用户回报）

1. 任务列表里能看到这个任务、状态`活跃`
2. 任务详情页能看到下次执行时间、所引用 Skill 名、（暂时还没配的）通知配置占位

两条都`是` → 进步骤 4。

---

## 步骤 4：配置通知对象

> 对应 [实践文档 推荐落地形态段](https://sls.aliyun.com/doc/starops/practices/rds-inspection-via-script/article.html)。

### Agent 给用户的指引

> 在长期任务的`通知`配置里选一个通道：联系人邮箱 / 钉钉机器人 / 飞书机器人 / 自定义 Webhook 任一。
>
> 如果通知对象还不存在，先去`通知管理`新增。
>
> 配完之后必须先发一条测试消息确认通道可达，通道不通则后续闭环不成立。

Agent 主动询问用户："打算用哪种通知通道？我可以根据通道类型给你不同的检查清单。"

### 完成判据（必须用户回报）

1. 任务详情页能看到已绑定的通知对象
2. 用户在该通道收到了测试消息

两条都`是` → 进步骤 5。任一`否` → 不要进步骤 5（巡检会跑成功但用户收不到，等于没做）。

---

## 步骤 5：等待执行 + 闭环验证

> 对应 [实践文档 推荐落地形态与验证方式段](https://sls.aliyun.com/doc/starops/practices/rds-inspection-via-script/article.html)。

### Agent 给用户的指引

> 两条路任选其一：
>
> - **等一个自然周期**（若设 1h 就等 1 小时）
> - **手动触发一次**：在长期任务详情页点`立即执行`

### 闭环验证（4 件事 checklist，全部通过才算闭环）

Agent 逐条问用户：

| # | 判据 | 用户回答 |
|---|---|---|
| 1 | Skill 已生成并启用 | ☐ 是 ☐ 否 |
| 2 | 数字员工已绑定该 Skill | ☐ 是 ☐ 否 |
| 3 | 长期任务已引用该 Skill 并完成至少一次执行 | ☐ 是 ☐ 否 |
| 4 | 巡检结果已成功送达通知通道，且用户能看到结构化报告 | ☐ 是 ☐ 否 |

**4 件事全是`是` → 闭环成立**，可以告诉用户"这条 SOP 跑完了，后续每周期会自动收到报告"。

任一`否` → 不要轻易结束，按下方对照表回到对应步骤复查。

---

## 失败与回滚（按步骤定位）

| 现象 | 回到哪步 | 典型原因 |
|---|---|---|
| `SKILL.md frontmatter must be a YAML mapping` | 步骤 1 | 首尾 `---` 漏了 / 不是合法 mapping；Path B 生成的 SKILL.md 不合规 |
| `--list-cases` 不足 27 项 | 步骤 1 | meta skill 包损坏或残缺；重新拷贝 / 重新生成 |
| Skill 列表里有但状态不是`已启用` | 步骤 2 | 用户没点启用按钮；让用户回控制台显式启用 |
| 长期任务执行时反复要求补上下文 | 步骤 3 | 任务输入用了自然语言，没显式引用 `/aliyun rds 巡检 skill` |
| 任务执行成功但收不到通知 | 步骤 4 | 通知通道未真正配置 / 通道不可达；先回去发测试消息 |
| 4 件事 checklist 有`否` | 对应步骤 | 缺一件即不闭环；逐项回查 |

何时**升级让人介入**：

- 步骤 1 Path B 重试 2 次仍生成出 frontmatter 不合法的 SKILL.md（提示用户切回 Path A，直接安装 `rds-inspection` 业务 skill）
- 步骤 2-4 用户回报"控制台找不到对应按钮 / 入口"（不是 SOP 范畴的 STAROps 平台问题，让用户提工单或联系产品同学）

---

## 召回 Routing

**应**路由到本 Guide Skill：

- "我想给我的 RDS 实例配置周期性自动巡检"
- "STAROps 里怎么搭一个 RDS 巡检的长期任务"
- "RDS 巡检从开通到收到报告全流程怎么走"
- "按最佳实践帮我配 RDS 健康巡检"

**不应**路由到本 Guide Skill：

- "我的 RDS 实例现在 CPU 高，帮我查一下" → 路由到 `rds-inspection` 业务 skill，做单次巡检即可，不需要走完整 SOP
- "我要写一个新的 RDS 业务 Skill" → 路由到 [Replay Prompt 附录](https://sls.aliyun.com/doc/starops/practices/rds-inspection-via-script/article.html#附录-path-b-replay-prompt) + STAROps 智能运维助手

## 相关入口

- [人读版实践文档](https://sls.aliyun.com/doc/starops/practices/rds-inspection-via-script/article.html)：章节一一对应
- [Replay Prompt 附录](https://sls.aliyun.com/doc/starops/practices/rds-inspection-via-script/article.html#附录-path-b-replay-prompt)：步骤 1 Path B 使用
- 兄弟 skill `rds-inspection`：业务 skill 样品，Path A 直接安装即可
