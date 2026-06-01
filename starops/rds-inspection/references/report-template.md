# RDS 数据库实例健康巡检报告

## 报告头部

| 字段 | 值 |
|---|---|
| 报告类型 | RDS 数据库实例健康巡检 |
| 生成时间 | {{timestamp}} |
| 时间范围 | {{time_range}} |
| Region | {{region}} |
| Project | {{project}} |
| MetricStore | {{metricstore}} |

---

## 健康状态总览

| 指标 | 数量 |
|---|---|
| 总巡检项 | {{total_cases}} |
| 通过 (pass) | {{passed}} |
| 发现问题 (find_problem) | {{find_problem_cases}} |
| 错误 (error) | {{errors}} |
| 无数据 (no_problem_found) | {{no_problem_found}} |
| **整体状态** | {{has_find_problem ? "⚠️ 发现问题" : "✅ 全部通过"}} |

---

## 异常项汇总

### P1 - 严重

| 巡检项 | 异常实例数 | 详情 |
|---|---|---|
{{#each p1_find_problem}}
| {{item}} | {{abnormal_count}} | {{abnormal_resources[0].entity_id}}: {{abnormal_resources[0].metric_value}} (阈值: {{abnormal_resources[0].threshold}}) |
{{/each}}

### P2 - 警告

| 巡检项 | 异常实例数 | 详情 |
|---|---|---|
{{#each p2_find_problem}}
| {{item}} | {{abnormal_count}} | {{abnormal_resources[0].entity_id}}: {{abnormal_resources[0].metric_value}} (阈值: {{abnormal_resources[0].threshold}}) |
{{/each}}

### P3 - 提示

| 巡检项 | 异常实例数 | 详情 |
|---|---|---|
{{#each p3_find_problem}}
| {{item}} | {{abnormal_count}} | {{abnormal_resources[0].entity_id}}: {{abnormal_resources[0].metric_value}} (阈值: {{abnormal_resources[0].threshold}}) |
{{/each}}

---

## 分维度详情

### 核心指标

{{#each core_results}}
#### {{item}} ({{severity}})

- **状态**: {{status}}
- **总实体数**: {{total_entities}}
- **异常数**: {{abnormal_count}}
- **查询**: `{{raw_query}}`
{{#if error}}
- **错误**: {{error}}
{{/if}}
{{#each abnormal_resources}}
- **异常实例**: {{entity_id}}
  - 指标值: {{metric_value}}
  - 阈值: {{threshold}}
  - 原始采样（最近 N 条）:
    ```
    {{#each raw_samples}}
    - ts={{ts}}, value={{value}}
    {{/each}}
    ```
  - 影响的上下游:
    - 上游: {{#each topology.upstream}}{{entity_id}} ({{type}}){{/each}}
    - 下游: {{#each topology.downstream}}{{entity_id}} ({{type}}){{/each}}
{{/each}}
{{/each}}

### 性能

{{#each performance_results}}
#### {{item}} ({{severity}})

- **状态**: {{status}}
- **总实体数**: {{total_entities}}
- **异常数**: {{abnormal_count}}
- **查询**: `{{raw_query}}`
{{#if error}}
- **错误**: {{error}}
{{/if}}
{{#each abnormal_resources}}
- **异常实例**: {{entity_id}}
  - 指标值: {{metric_value}}
  - 阈值: {{threshold}}
  - 原始采样（最近 N 条）:
    ```
    {{#each raw_samples}}
    - ts={{ts}}, value={{value}}
    {{/each}}
    ```
  - 影响的上下游:
    - 上游: {{#each topology.upstream}}{{entity_id}} ({{type}}){{/each}}
    - 下游: {{#each topology.downstream}}{{entity_id}} ({{type}}){{/each}}
{{/each}}
{{/each}}

### 安全

{{#each security_results}}
#### {{item}} ({{severity}})

- **状态**: {{status}}
- **总实体数**: {{total_entities}}
- **异常数**: {{abnormal_count}}
- **查询**: `{{raw_query}}`
{{#if error}}
- **错误**: {{error}}
{{/if}}
{{#each abnormal_resources}}
- **异常实例**: {{entity_id}}
  - 指标值: {{metric_value}}
  - 阈值: {{threshold}}
  - 原始采样（最近 N 条）:
    ```
    {{#each raw_samples}}
    - ts={{ts}}, value={{value}}
    {{/each}}
    ```
  - 影响的上下游:
    - 上游: {{#each topology.upstream}}{{entity_id}} ({{type}}){{/each}}
    - 下游: {{#each topology.downstream}}{{entity_id}} ({{type}}){{/each}}
{{/each}}
{{/each}}

### 关联日志

{{#each logs_results}}
#### {{item}} ({{severity}})

- **状态**: {{status}}
- **总实体数**: {{total_entities}}
- **异常数**: {{abnormal_count}}
- **查询**: `{{raw_query}}`
{{#if error}}
- **错误**: {{error}}
{{/if}}
{{#each abnormal_resources}}
- **异常实例**: {{entity_id}}
  - 指标值: {{metric_value}}
  - 阈值: {{threshold}}
  - 原始采样（最近 N 条脱敏日志）:
    ```
    {{#each raw_samples}}
    - {{json this}}
    {{/each}}
    ```
  - 影响的上下游:
    - 上游: {{#each topology.upstream}}{{entity_id}} ({{type}}){{/each}}
    - 下游: {{#each topology.downstream}}{{entity_id}} ({{type}}){{/each}}
{{/each}}
{{/each}}

---

## 修复建议优先级

### 立即处理（P1）

{{#each p1_find_problem}}
- **{{item}}**: {{description}}
  - 影响实例: {{#each abnormal_resources}}{{entity_id}} {{/each}}
  - 建议: {{suggestion}}
{{/each}}

### 24 小时内处理（P2）

{{#each p2_find_problem}}
- **{{item}}**: {{description}}
  - 影响实例: {{#each abnormal_resources}}{{entity_id}} {{/each}}
  - 建议: {{suggestion}}
{{/each}}

### 纳入优化计划（P3）

{{#each p3_find_problem}}
- **{{item}}**: {{description}}
  - 影响实例: {{#each abnormal_resources}}{{entity_id}} {{/each}}
  - 建议: {{suggestion}}
{{/each}}

---

## 附录

### 巡检脚本信息

| 脚本 | 巡检项数 | 维度 |
|---|---|---|
| `rds-core-inspection.py` | 7 | 核心指标 |
| `rds-performance-inspection.py` | 6 | 性能 |
| `rds-security-inspection.py` | 6 | 安全 |
| `rds-logs-inspection.py` | 2 | 关联日志 |
| **总计** | **21** | - |

### 原始数据

完整 JSON 输出见巡检脚本执行结果。

### 确定性验证

本 Skill 遵循确定性设计原则：同输入同输出。`raw_samples` 与 `topology` 为外部状态依赖字段，确定性验证时须剥离后对比。
