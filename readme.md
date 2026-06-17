# 考题：为目标 Skill 构建评估用例集

给定目标 Skill，为其构建一套完整的评估用例集，使得该用例集能够系统性地检验 Skill 的质量。每个 Skill 都提供了相应参考示例，帮助理解理想态规范、测试用例与评分规则的写法。最终交付物以 YAML 打包的压缩包格式提交。

## 提供材料

本次提供两个目标 Skill （都必须完成，不是二选一）：

- `db_report`：数据库性能报告 Skill，重点是基于本地性能测试数据生成 single / comparison / iteration / custom 等报告，并检验数据可信、场景覆盖、报告结构和交付质量。
- `tracingclaw_finance`：金融验真 Skill，重点是基于 `westock-data` 和 `mx-finance-search` 做金融事实核查，并检验数据来源、口径一致性、真实性评分和修正答案质量。

## 要求

a. 熟悉该 Skill，并定义该 Skill 的理想态规范。
b. 设计评分规则 Rubrics，定义评分维度及各维度权重。
c. 编写测试用例集（核心交付物）：每个 Skill 不少于 5 条用例，不设上限，鼓励用更少用例覆盖更多场景，输出测试报告。
d. 设计编写 Meta-Testcase 自检方案。
