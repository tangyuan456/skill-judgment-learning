# Changelog — db-report-skill

## 2026-06-12 — 学生版离线化

### 变更

- 移除通过 `task_id` / `plan_id` / `report_id` 查询 `yunyu_test_results` 的说明、流程和示例。
- 移除 YunYu HTTP API、PostgreSQL 直连、SQL 模板和 UUID 探测相关文件。
- 将数据源限定为本地 `.log` / `.xlsx` / `.json` / `.csv` 文件或用户粘贴 JSON。
- 新增 `missing_data` 数据源类型：缺少本地数据时阻断并要求补充文件。
- 更新 reference 文档和最小交付标准，使学生可以在无内部权限环境下使用。

### 可用测试资源

- `../test-resource/mock_tdsqlb_v22_7_2.log`
- `../test-resource/mock_tdsqlb_v22_7_3.log`
- `../test-resource/mock_records_aggregation.json`
- `../test-resource/mock_iteration_history.json`
