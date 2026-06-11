# 容量风险预测报告模板

## 报告头部

```
容量风险预测报告
====================
生成时间: {timestamp}
Region: {region}
时间范围: {time_range}
```

## 风险状态总览

```
风险总览
--------
总巡检项: {total_cases}
Critical: {critical_cases}
Warning:  {warning_cases}
Normal:   {normal_cases}
Error:    {errors}
无数据:   {no_problem_found}
```

## 按域分组详情

### acs 基础资源

| case_id | 实体 | 当前值 | 策略 | 风险等级 | 预测值 | 剩余天数 | 建议 |
|---|---|---|---|---|---|---|---|
| {case_id} | {entity_name} | {current_value} | {strategy} | {risk_level} | {predicted_value} | {days_to_warning} | {action} |

### k8s 集群资源

| case_id | 实体 | 当前值 | 策略 | 风险等级 | 预测值 | 剩余天数 | 建议 |
|---|---|---|---|---|---|---|---|
| {case_id} | {entity_name} | {current_value} | {strategy} | {risk_level} | {predicted_value} | {days_to_warning} | {action} |

### apm 业务服务

| case_id | 实体 | 当前值 | 策略 | 风险等级 | 偏离比 | 超标幅度 | 建议 |
|---|---|---|---|---|---|---|---|
| {case_id} | {entity_name} | {current_value} | {strategy} | {risk_level} | {deviation_ratio} | {exceed_percent} | {action} |

### log 日志衍生时序

| case_id | 实体 | 当前值 | 策略 | 风险等级 | 预测值 | 异常比例 | 建议 |
|---|---|---|---|---|---|---|---|
| {case_id} | {entity_name} | {current_value} | {strategy} | {risk_level} | {arima_predicted_value} | {anomaly_ratio} | {action} |

## 整体建议

### Critical 项

- **立即处理**：{critical_items}
- 建议操作：扩容、优化代码、增加资源配额

### Warning 项

- **24 小时内处理**：{warning_items}
- 建议操作：制定扩容计划、优化资源使用

### Normal 项

- 持续观察，无需立即操作

## 建议行动矩阵

| 风险等级 | 剩余天数 | 建议行动 |
|---|---|---|
| Critical | < 1 天 | 立即扩容或降级 |
| Warning | 1-7 天 | 制定扩容计划 |
| Warning | 7-30 天 | 纳入容量规划 |
| Normal | > 30 天 | 持续观察 |
