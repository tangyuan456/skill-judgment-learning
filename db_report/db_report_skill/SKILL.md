---
name: db-report-skill
description: "数据库性能测试报告生成技能。仅支持文本输入和本地数据文件（.log/.xlsx/.json/.csv）。支持四种报告类型：single（单次测试报告）/ comparison（性能对比报告）/ iteration（项目迭代报告）/ custom（客制化/专项报告）。输出 md + docx + html 三格式。自包含运行，不依赖任何外部服务或上游 skill。触发词：测试报告、性能报告、对比报告、迭代报告、客制化报告、sysbench 报告。"
---

# 数据库性能测试报告生成技能

## 概述

本 Skill 是自包含的报告生成工具，**仅支持文本和本地文件输入**，不依赖任何外部服务或 API。

| 数据源 | 触发条件 | 处理方式 |
|--------|---------|---------|
| **本地数据文件** | 用户提供 `.log` / `.xlsx` / `.json` / `.csv` 路径 | 解析为标准 records 结构 |
| **粘贴数据** | 用户直接粘贴 JSON 性能数据 | 解析为标准 records 结构 |

| 报告类型 | report_type | 触发关键词 | 输出特征 |
|---------|-------------|-----------|---------|
| **单次测试报告** | `single` | 默认（无特殊关键词） | 1 份测试数据 + 场景指标分析 |
| **性能对比报告** | `comparison` | 对比 / 比较 / vs / 差异 / 哪个更好 | ≥ 2 份测试数据横向对比 |
| **项目迭代报告** | `iteration` | 迭代 / 版本演进 / 历史趋势 | ≥ 3 个版本/时间点的演进趋势 |
| **客制化报告** | `custom` | 客制化 / 专项 / 定制 / 深度分析 | 用户指定分析维度的深度报告 |

> ⚠️ **强制约束**：每次调用本 Skill 时，必须完整遵守本文件及所有 reference 文件中的规范。

---

## 核心原则（强制）

1. **数据源识别先行**：`scripts/detect_input.py` 自动识别用户输入是「本地文件路径」还是「粘贴数据」。
2. **意图解析**：自然语言 → JSON（按 `references/意图解析规范.md` 提取 `report_type / dimension_filters`）。
3. **数据铁律**：所有报告数据必须来自本地原始文件或用户粘贴的数据。**禁止 AI 推断、估算、硬编码数据。**
4. **场景分离**：分析章节按 sysbench 场景（point_select / read_only / write_only / read_write / update_index 等）独立输出，禁止合并均值。
5. **洞察分级**：

| 等级 | 标识 | 含义 | 写入规则 |
|------|------|------|---------|
| L1 | ✅ | Python 计算的客观事实 | 写入正文 |
| L2 | 📊 | 跨维度统计发现 | 写入正文 |
| L3 | 💡 | 数据模式推测 | 仅第 5 章选型与调优建议，标注 `[待确认]` |

---

## 快速开始

### 安装依赖

```bash
pip install "openpyxl>=3.1.0" "matplotlib>=3.7.0" "numpy>=1.24.0" \
            "python-docx>=0.8.11" "pandas>=2.0.0" "pyyaml>=6.0"
```

### 命令行运行

```bash
# 从 sysbench 日志生成单次报告
python scripts/run_pipeline.py --text "/path/to/sysbench.log" --out output

# 用自然语言描述需求
python scripts/run_pipeline.py --text "对 test.log 和 test2.log 做性能对比报告" --out output

# 从已有 intent.json 运行
python scripts/run_pipeline.py --intent data/intent.json --out output
```

---

## References 索引

> ⚠️ **强制读取规则**：进入每个阶段前必须先读取对应 Reference 文件。

| 阶段 | 必读文件 | 时机 |
|------|---------|------|
| 阶段1 | `references/意图解析规范.md` | 解析用户输入前 |
| 阶段2 | `references/数据源接入规范.md` | 数据接入前 |
| 阶段3 | `references/分析方法论.md` | 编写分析脚本前 |
| 阶段4 | `references/报告类型模板规范.md` | 编写报告模板前 |
| 阶段5 | `references/三格式输出规范.md` + `references/最小交付标准.md` | 渲染前 + 交付前 |

---

## 执行流程（5 阶段）

```
阶段1: 输入解析 → 识别数据源类型 + 报告类型 → 生成 intent.json
        ↓
阶段2: 数据接入
        └─ 本地数据：log/xlsx/json/csv → 标准 records.json
        ↓
阶段3: 分析（按 report_type 分流）
        ├─ single:      单次分析（场景峰值/扩展/P95）
        ├─ comparison:  横向对比（产品/版本/配置 ≥ 2）
        ├─ iteration:   纵向演进（≥ 3 时间点）
        └─ custom:      用户指定维度深度分析
        ↓
阶段4: 图表生成（按 report_type 选择图表组合）
        ↓
阶段5: 报告组装 → md/docx/html
```

---

## 阶段 1：输入解析

### Step 1.1 数据源类型自动识别

`scripts/detect_input.py` 按下表判定：

| 输入特征 | 数据源类型 | 示例 |
|---------|-----------|------|
| 含 .log / .xlsx / .json / .csv 文件路径（存在） | `local_file` | `/path/to/test.log` |
| 含 JSON 性能数据（粘贴） | `local_data` | `{"product":"...","scenario":"oltp_..."}` |
| 上述均不匹配 | `keyword_only` | 提示用户提供文件 |

### Step 1.2 报告类型识别

```
if /对比|比较|vs|差异|哪个更好/ → comparison
elif /迭代|版本演进|历史趋势/    → iteration
elif /客制化|专项|定制|深度分析/  → custom
else                            → single
```

### Step 1.3 场景关键词中英映射

| 用户输入 | 英文关键词 |
|---------|-----------|
| 只读 | read_only |
| 写入 / 写 | write_only |
| 读写 / 混合读写 | read_write |
| 更新索引 | update_index |
| 更新非索引 | update_non_index |
| 点查 / 点选 | point_select |
| tpcc | tpmC |

---

## 阶段 2：数据接入

### 支持的本地文件格式

- `.log`：sysbench 标准日志（自包含解析器）
- `.xlsx`：按约定表头读取（scenario/threads/tps/qps/p95_ms/p99_ms）
- `.json`：标准 `{meta, records}` 格式或 JSON 数组
- `.csv`：标准 CSV 格式

### 标准化输出

```json
{
  "meta": {
    "products": ["Product-A v1.0"],
    "scenarios": ["oltp_point_select", "oltp_read_only", ...],
    "concurrencies": [32, 64, 128],
    "source_info": {"type": "local_file", "value": "/path/to/test.log"}
  },
  "records": [{"product": "...", "scenario": "...", "threads": 64, "tps": ..., "qps": ..., "p95_ms": ...}]
}
```

---

## 阶段 3-5：分析 → 图表 → 渲染

详见对应 Reference 文件。

---

## 脚本依赖

```
openpyxl      >= 3.1.0    # Excel 读取
matplotlib    >= 3.7.0    # 图表生成
numpy         >= 1.24.0   # 数值计算
python-docx   >= 0.8.11   # Word 文档生成
pandas        >= 2.0.0    # 数据处理
pyyaml        >= 6.0      # 配置读取
```

---

## 内置脚本

| 脚本 | 用途 | 阶段 |
|------|------|------|
| `scripts/detect_input.py` | 输入类型自动识别 | 阶段1 |
| `scripts/parse_intent.py` | 自然语言→intent.json | 阶段1 |
| `scripts/data_source_adapter.py` | 统一数据接入（本地文件） | 阶段2 |
| `scripts/log_parser.py` | sysbench 日志解析器 | 阶段2 |
| `scripts/analyze.py` | 分析分发 | 阶段3 |
| `scripts/analyze_core.py` | 核心分析逻辑 | 阶段3 |
| `scripts/generate_charts.py` | 图表生成 | 阶段4 |
| `scripts/render_all.py` | 三格式渲染调度 | 阶段5 |
| `scripts/render_core.py` | md/docx/html 渲染器 | 阶段5 |
| `scripts/constants.py` | 共享常量 | 全局 |
| `scripts/run_pipeline.py` | 一键流水线 | 入口 |
| `templates/*.py` | 4 类报告 build_report_data | 阶段5 |

---

## 强制约束

### 必须做到
- 所有数据来自本地文件或用户粘贴；禁止 AI 推断
- 每阶段开始前读取对应 Reference
- 三格式独立生成（禁止 pandoc 转换）
- 报告交付前通过最小交付核查

### 禁止事项
- 把中文业务术语原样写入（必须映射为英文字段）
- L3 推测性洞察混入第 1/2/3/4 章正文
- 仅生成一个格式后用工具批量转换其他格式
