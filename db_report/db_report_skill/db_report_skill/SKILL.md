---
name: db-report-skill
description: "数据库性能测试报告生成技能。仅支持本地数据/数据文件（.log/.xlsx/.json/.csv）直接读取，支持 single（单次测试报告）/ comparison（性能对比报告）/ iteration（项目迭代报告）/ custom（客制化/专项报告）。输出 md + docx + html 三格式。触发词：测试报告、性能报告、对比报告、迭代报告、客制化报告、sysbench 报告、benchmarksql 报告。"
---

# 数据库性能测试报告生成技能

## 概述

本 Skill 统一处理本地性能测试数据，输出 md/docx/html 三格式报告。学生环境不具备线上库查询权限，因此本 Skill **不支持**通过 `task_id` / `plan_id` / `report_id` 查询 `yunyu_test_results`，必须使用本地数据文件或用户粘贴的原始数据。

| 数据源 | 触发条件 | 处理方式 |
|--------|---------|---------|
| 本地 `.log` | 用户提供 sysbench 日志路径 | 解析为标准 records |
| 本地 `.json` | 用户提供标准 records JSON 或导出的原始测试行 JSON | 直接读取或规范化为标准 records |
| 本地 `.xlsx` | 用户提供约定表头的 Excel | 按 Sheet/表头读取 |
| 本地 `.csv` | 用户提供 records 字段一致的 CSV | 按表头读取 |
| 粘贴 JSON | 用户直接粘贴标准 records 或原始测试行 | 解析为标准 records |

| 报告类型 | report_type | 触发关键词 | 输出特征 |
|---------|-------------|-----------|---------|
| 单次测试报告 | `single` | 默认（无特殊关键词） | 1 份测试数据 + 5 场景指标分析 |
| 性能对比报告 | `comparison` | 对比 / 比较 / vs / 差异 / 哪个更好 | ≥ 2 份测试数据横向对比 |
| 项目迭代报告 | `iteration` | 迭代 / 版本演进 / 历史趋势 | ≥ 3 个版本/时间点的演进趋势 |
| 客制化报告 | `custom` | 客制化 / 专项 / 定制 / 深度分析 | 用户指定分析维度的深度报告 |

> 强制约束：每次调用本 Skill 时，必须完整遵守本文件及所有 reference 文件中的规范，不得跳过、简化或选择性执行。

---

## 核心原则（强制）

1. **数据源识别先行**：`scripts/detect_input.py` 只识别可读取的本地数据文件或粘贴 JSON。
2. **意图解析**：自然语言 → JSON，按 `references/意图解析规范.md` 提取 `report_type / dimension_filters / results_key_filters`。
3. **数据铁律**：所有报告数据必须来自本地原始文件或用户粘贴的原始数据。禁止 AI 推断、估算、硬编码数据。
4. **场景分离**：分析章节按 5 个 sysbench 场景（point_select / read_only / write_only / read_write / update_index）独立输出，禁止合并均值。
5. **门控确认**：3 个门控（提案 / 数据 / 报告）必须向用户展示规定内容并获得明确确认。
6. **洞察分级**：

| 等级 | 标识 | 含义 | 写入规则 |
|------|------|------|---------|
| L1 | ✅ | Python 计算的客观事实 | 写入正文 |
| L2 | 📊 | 跨维度统计发现 | 写入正文 |
| L3 | 💡 | 数据模式推测 | 仅第 5 章选型与调优建议，标注 `[待确认]` |

---

## References 索引

进入每个阶段前必须先读取对应 Reference 文件。

| 阶段 | 必读文件 | 时机 |
|------|---------|------|
| 阶段1 | `references/意图解析规范.md` | 解析用户输入前 |
| 阶段2 | `references/数据源接入规范.md` | 数据接入前 |
| 阶段3 | `references/分析方法论.md` | 编写分析脚本前 |
| 阶段4 | `references/报告类型模板规范.md` | 编写报告模板前 |
| 阶段5 | `references/三格式输出规范.md` + `references/最小交付标准.md` | 渲染前 + 交付前 |

---

## 执行流程（5 阶段 + 3 门控）

```text
阶段1: 输入解析 → 识别本地数据源 + 报告类型 → 生成 intent.json
        ↓
        门控①（意图确认）
        ↓
阶段2: 数据接入 → log/xlsx/json/csv/粘贴 JSON → 标准 records.json
        ↓
        门控②（数据确认）
        ↓
阶段3: 分析（按 report_type 分流）
        ├─ single:      单次分析（5 场景峰值/扩展/P95）
        ├─ comparison:  横向对比（产品/版本/配置 ≥ 2）
        ├─ iteration:   纵向演进（≥ 3 时间点）
        └─ custom:      用户指定维度深度分析
        ↓
阶段4: 图表生成（按 report_type 选择图表组合）
        ↓
阶段5: 报告组装 → md/docx/html → 最小交付核查
        ↓
        门控③（交付确认）
```

---

## 阶段 1：输入解析

### Step 1.1 数据源类型自动识别

`scripts/detect_input.py` 按下表判定：

| 输入特征 | 数据源类型 | 示例 |
|---------|-----------|------|
| 含 `.log` / `.xlsx` / `.json` / `.csv` 文件路径（存在） | `local_file` | `/path/to/test.log` |
| 含标准 records JSON 或原始测试行 JSON | `local_data` | `{"meta":{...},"records":[...]}` |
| 上述均不匹配 | `missing_data` | `生成集中式只读场景报告` |

如果识别为 `missing_data`，必须停止并请用户提供本地数据文件，不能尝试线上查询或编造数据。

### Step 1.2 报告类型识别

```text
if /对比|比较|vs|差异|哪个更好/ → comparison
elif /迭代|版本演进|历史趋势/    → iteration
elif /客制化|专项|定制|深度分析/  → custom
else                            → single
```

### Step 1.3 场景关键词中英映射（强制）

| 用户输入 | 标准场景/字段 |
|---------|--------------|
| 只读 | read_only |
| 写入 / 写 | write_only / insert |
| 读写 / 混合读写 | read_write |
| 更新索引 | update_index |
| 更新非索引 | update_non_index |
| 点查 / 点选 | point_select |
| 集中式 | 集中式性能 |
| 分布式 | 分布式性能 |
| tpcc | benchmarksql + tpmC |

### Step 1.4 OR 逻辑识别

| 用户输入 | 正确解析 |
|---------|---------|
| "集中式只读场景和点查场景" | `test_name_keywords_or: [["集中式","read_only"],["集中式","point_select"]]` |
| "集中式的只读场景"（修饰同一场景） | `test_name_keywords: ["集中式","read_only"]` |

详见 `references/意图解析规范.md`。

### 门控① — 意图确认

向用户展示：
- 数据源类型 + 文件路径/粘贴数据摘要
- 报告类型（single/comparison/iteration/custom）
- 提取的筛选条件（场景/版本/参数）
- 输出格式（md+docx+html）

提供选项：`确认` / `修改` / `重新解析`

---

## 阶段 2：数据接入

### Step 2.1 数据源适配（统一抽象）

`scripts/data_source_adapter.py` 暴露统一接口：

```python
def load_records(intent_json) -> StandardRecords:
    """
    根据 intent_json.data_source_type 派发到不同适配器：
      - local_file: 解析 .log/.xlsx/.json/.csv
      - local_data: 解析粘贴的 JSON 文本
    返回统一的 StandardRecords：
      {
        meta: {products, scenarios, concurrencies, test_env, source_info},
        records: [{product, scenario, threads, tps, qps, p95_ms, p99_ms, ...}]
      }
    """
```

### Step 2.2 本地文件解析

- `.log`：复用 `tdsql-b-whitepaper/scripts/log_to_excel.py` 的正则。
- `.xlsx`：按既有约定的 Sheet 表头读取。
- `.json`：优先要求标准 records 结构 `{meta, records}`；也可接收本地导出的原始测试行数组。
- `.csv`：表头匹配标准 records 字段。

### Step 2.3 标准 records 结构

```json
{
  "meta": {
    "products": ["TDSQL-B v22.7.2", "TDSQL-B v22.7.3"],
    "scenarios": ["oltp_point_select", "oltp_read_only"],
    "concurrencies": [32, 64, 128],
    "test_env": {},
    "source_info": {
      "type": "local_file",
      "value": "test-resource/mock_records_aggregation.json",
      "rows_fetched": 60
    }
  },
  "records": []
}
```

### Step 2.4 数据质量门控

- TPS / QPS / P95 任一空值率 > 0% → 停止。
- 并发档/场景缺失 → 警告但继续（在报告中显式标注）。
- 抽检 6 条与原始数据对比。

### 门控② — 数据确认

向用户展示：
- 数据源摘要（来源 + 记录数 + 覆盖范围）
- 空值率
- 抽检结果

---

## 阶段 3：分析（按 report_type 分流）

### Step 3.1 single（单次报告）

按 `references/分析方法论.md` 第 2 章「单产品分析」：
- 5 场景峰值 QPS 汇总
- 并发扩展性（每场景 1 张曲线）
- P95 延迟稳定性

### Step 3.2 comparison（对比报告）

按 `references/分析方法论.md` 第 3 章「横向对比」：
- 公平性自动校验（数据集/并发档/时长/硬件）
- 5 场景每场景独立对比表+图
- 性能比值矩阵（以 baseline 为 1.00）
- 综合评分雷达图

### Step 3.3 iteration（迭代报告）

- 时间序列：N 个版本/时间点的 5 场景峰值演进
- 趋势线（QPS 上升/下降/稳定）
- 回归点检测（QPS 较前版本下降 > 5% 标记为回归）
- 累计提升/下降百分比

### Step 3.4 custom（客制化）

按用户在 `intent.other_info` 字段中的具体需求生成：
- 单维度深挖（如"高并发场景下的性能瓶颈"）
- 跨维度对比（如"buffer pool 大小对 QPS 的影响"）
- 用户在阶段 1 门控①时可补充明确的分析问题

输出统一为：
- `data/analysis_results.json`
- `data/insights.json`（含 L1/L2/L3）

---

## 阶段 4：图表生成（按 report_type 选择）

| report_type | 必需图表 |
|-------------|---------|
| single | 5 场景并发-QPS 曲线 + 5 场景并发-P95 曲线 + 1 张峰值汇总条形图 |
| comparison | 峰值×5 + 并发-QPS×5 + 并发-P95×5 + 雷达 + 天梯 + 单产品×N |
| iteration | 时间趋势线（每场景 1 张）+ 累计变化柱状图 + 回归点散点图 |
| custom | 由 custom 配置驱动 |

详见 `references/报告类型模板规范.md`。

---

## 阶段 5：报告组装与交付

### Step 5.1 模板派发

- `templates/single_report.py` → `build_single_report_data()`
- `templates/comparison_report.py` → `build_comparison_report_data()`
- `templates/iteration_report.py` → `build_iteration_report_data()`
- `templates/custom_report.py` → `build_custom_report_data()`

所有模板返回统一 `report_data` 结构（章节/块/插图），由共用渲染器 `scripts/render_*.py` 输出三格式。

### Step 5.2 三格式输出（强制）

```text
1. report.md  （source of truth，最先生成）
2. report.docx（独立生成，全文微软雅黑，表头浅蓝 #D9E2F3）
3. report.html（独立生成，内联 CSS，含 TOC，浏览器可直接看）
```

禁止用 pandoc 等工具直接 md → docx/html。

### Step 5.3 最小交付核查（A~F）

复用 `tdsql-b-whitepaper/scripts/min_delivery_check.py` 的 A~F 38 项核查，针对 4 类报告分别配置必需图表数量基线（在 `references/最小交付标准.md`）。

### 门控③ — 报告交付确认

向用户展示：
- A~F 核查全通过
- 三格式文件路径与大小
- 核心结论摘要（≤5 条）

---

## 强制约束

### 必须做到

- 所有数据来自原始文件或用户粘贴数据；禁止 AI 推断。
- 每阶段开始前读取对应 Reference 并声明已读。
- 三格式独立生成。
- 报告交付前通过 A~F 全项。

### 禁止事项

- 跳过 Reference 直接执行。
- 把 OR 关系（"和/或"连接不同场景）误识别为 AND。
- 把中文业务术语原样用于筛选（必须映射为标准场景字段）。
- L3 推测性洞察混入第 1/2/3/4 章正文。
- 仅生成一个格式后用工具批量转换其他格式。
- 通过线上接口或数据库查询补数据。

---

## 脚本依赖

```text
openpyxl     >= 3.1.0
matplotlib   >= 3.7.0
numpy        >= 1.24.0
python-docx  >= 0.8.11
seaborn      >= 0.12.0
pandas       >= 2.0.0
markdown     >= 3.5.0
pyyaml       >= 6.0
```

一键安装：

```bash
pip install "openpyxl>=3.1.0" "matplotlib>=3.7.0" "numpy>=1.24.0" \
            "python-docx>=0.8.11" "seaborn>=0.12.0" "pandas>=2.0.0" \
            "markdown>=3.5.0" "pyyaml>=6.0"
```

---

## 内置脚本

| 脚本 | 用途 | 阶段 |
|------|------|------|
| `scripts/detect_input.py` | 输入类型自动识别 | 阶段1 |
| `scripts/parse_intent.py` | 自然语言→intent.json | 阶段1 |
| `scripts/data_source_adapter.py` | 统一本地数据接入 | 阶段2 |
| `scripts/log_to_excel.py` | sysbench log → Excel | 阶段2（复用上游） |
| `scripts/analyze.py` | 单/对比/迭代/客制化分析分发 | 阶段3 |
| `scripts/generate_charts.py` | 图表生成（按 report_type） | 阶段4 |
| `scripts/render_md.py` / `render_docx.py` / `render_html.py` | 三格式渲染 | 阶段5 |
| `scripts/min_delivery_check.py` | A~F 核查 | 阶段5 |
| `templates/*.py` | 4 类报告 build_report_data | 阶段5 |
