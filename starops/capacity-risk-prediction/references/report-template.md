# 容量风险预测报告模板

## 使用说明

Step 9 生成报告时，使用以下模板渲染 Markdown 报告。将 JSON 报告中的数据填入对应位置。

---

## 模板

```markdown
# 容量风险预测报告

**Profile**: {{profile_id}}
**执行时间**: {{execution_time}}
**时间窗口**: {{time_range}}
**Region**: {{region}}

---

## 总览

| 指标 | 数量 |
|------|:----:|
| 预测对象总数 | {{summary.total_targets}} |
| Critical | {{summary.critical}} |
| Warning | {{summary.warning}} |
| Normal | {{summary.normal}} |
| 错误 | {{summary.errors}} |
| 共振事件 | {{summary.resonance_events}} |

---

## 风险项列表

{{#each risk_items}}
### {{risk_level | upper}} - {{object_name}} / {{signal_id}}

| 属性 | 值 |
|------|-----|
| 对象 | {{object_name}} ({{object_ref.domain}}/{{object_ref.type}}) |
| 信号 | {{signal_id}} |
| 风险等级 | **{{risk_level}}** |
| 当前值 | {{current_value}} |
| 预测最大值 | {{predicted_max}} |
| Warning 阈值 | {{warning_threshold}} |
| Critical 阈值 | {{critical_threshold}} |
| 预计触阈时间 | {{threshold_breach_time}} |
| 置信度 | {{confidence}} |

**预测趋势**:
- 预测值范围: [{{predicted_min}}, {{predicted_max}}]
- 上界（最新）: {{upper_bound_last}}
- 下界（最新）: {{lower_bound_last}}

**序列特征**:
{{#each segments}}
- Segment {{@index}}: {{shape}} (confidence: {{confidence}})
{{/each}}

{{#if transitions.length}}
**转换点**:
{{#each transitions}}
- {{type}} (confidence: {{confidence}})
{{/each}}
{{/if}}

**数据质量**: actual={{data_quality.actual_points}}, missing={{data_quality.missing_points}}

**证据**: {{evidence}}

**反证**: {{counter_evidence}}

**缺口**: {{gaps}}

---
{{/each}}

## 共振事件

{{#if resonance_events.length}}
{{#each resonance_events}}
### {{type}} - {{group}}

- **涉及对象**: {{targets | join ", "}}
- **严重程度**: {{severity}}
- **描述**: {{description}}

{{/each}}
{{else}}
无共振事件。
{{/if}}

---

## 方法论说明

- **预测函数**: series_forecast（SLS SPL 管道函数）
- **统计描述**: series_describe（SLS SPL 管道函数）
- **数据源**: 见各风险项的数据源类型
- **阈值来源**: Mission Profile 注入
- **共振检测**: 多信号同向恶化 + 时间窗口对齐
```
