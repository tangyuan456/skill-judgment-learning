"""客制化/专项报告模板（report_type=custom）。

由 intent.custom_config.focus_dimension 驱动，输出深度分析报告。
"""
import os
import sys

SKILL_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(SKILL_BASE, 'tdsql-b-whitepaper', 'scripts'))
from constants import SCENARIO_CN, SCENARIOS as STD_SCENARIOS  # noqa: E402


def fmt_int(v):
    return f'{v:,.0f}' if v is not None else '-'


def fmt_float(v, n=2):
    return f'{v:,.{n}f}' if v is not None else '-'


def build_custom_report_data(extracted, analysis, insights, intent, charts_dir_rel='charts'):
    meta = extracted['meta']
    custom_cfg = intent.get('custom_config') or {}
    focus = custom_cfg.get('focus_dimension') or '通用'
    questions = custom_cfg.get('extra_questions') or []

    cover = {
        'title': f'数据库性能专项分析报告',
        'subtitle': f'专项维度：{focus}',
        'date': '2026-04-28',
        'version': 'v1.0',
    }

    sections = []

    # === 第 1 章 分析目标 ===
    sections.append({
        'id': 'ch1', 'title': '第 1 章 分析目标', 'blocks': [], 'subsections': [
            {'id': 'ch1_1', 'title': '1.1 用户需求',
             'blocks': [{'type': 'bullet',
                         'items': questions or [f'对 {focus} 维度进行深度分析']}]},
            {'id': 'ch1_2', 'title': '1.2 关键发现',
             'blocks': [
                 {'type': 'insight', 'level': 'L2',
                  'text': analysis.get('custom', {}).get('main_finding', '基于本次数据样本的主要发现见第 3 章。'),
                  'source': 'analysis_results.custom'},
             ]},
        ],
    })

    # === 第 2 章 数据范围 ===
    sections.append({
        'id': 'ch2', 'title': '第 2 章 数据范围与假设', 'blocks': [], 'subsections': [
            {'id': 'ch2_1', 'title': '2.1 数据来源',
             'blocks': [{'type': 'paragraph',
                         'text': f"数据源：{meta.get('source_info', {}).get('type', '-')} "
                                 f"({meta.get('source_info', {}).get('value', '-')})，"
                                 f"共 {len(extracted['records'])} 条记录。"}]},
            {'id': 'ch2_2', 'title': '2.2 假设前提',
             'blocks': [{'type': 'bullet', 'items': [
                 f'专项分析维度：{focus}（其他变量假设保持一致）',
                 '样本量足以支持当前结论；如样本不足，第 4 章会披露不确定性。',
             ]}]},
        ],
    })

    # === 第 3 章 深度分析（按 focus_dimension）===
    custom = analysis.get('custom') or {}
    buckets = custom.get('buckets') or []
    bucket_rows = [[b.get('label', '-'), fmt_int(b.get('avg_qps')),
                    fmt_float(b.get('avg_p95_ms')), str(b.get('sample_size', 0))]
                   for b in buckets]
    sections.append({
        'id': 'ch3', 'title': f'第 3 章 {focus} 维度深度分析', 'blocks': [
            {'type': 'paragraph', 'text': f'按 {focus} 维度对样本分桶，输出 QPS / P95 / 样本量对比：'},
            {'type': 'table',
             'headers': [focus, '平均 QPS', '平均 P95 (ms)', '样本数'],
             'rows': bucket_rows or [['（无数据）', '-', '-', '0']]},
            {'type': 'image', 'path': f'{charts_dir_rel}/custom_main.png',
             'caption': f'{focus} 与 QPS 关系主图'},
            {'type': 'image', 'path': f'{charts_dir_rel}/custom_compare.png',
             'caption': f'{focus} 不同档位对比'},
        ], 'subsections': [],
    })

    # === 第 4 章 结论与建议 ===
    sections.append({
        'id': 'ch4', 'title': '第 4 章 结论与建议', 'blocks': [], 'subsections': [
            {'id': 'ch4_1', 'title': '4.1 主要发现',
             'blocks': [{'type': 'insight', 'level': 'L1',
                         'text': custom.get('main_finding', '基于样本数据，主要发现见上方表格与图表。'),
                         'source': 'analysis_results.custom'}]},
            {'id': 'ch4_2', 'title': '4.2 不确定性披露',
             'blocks': [{'type': 'bullet', 'items': [
                 f'样本量：{len(extracted["records"])} 条；样本量较小时，结论置信度有限。',
                 f'仅 {focus} 维度变化，其他变量假设保持一致；如其他变量也变化，需在生产复现验证。',
             ]}]},
            {'id': 'ch4_3', 'title': '4.3 后续测试建议',
             'blocks': [{'type': 'bullet', 'items': [
                 f'扩大 {focus} 维度的取值范围，覆盖更多档位。',
                 '在生产典型负载下复现关键发现。',
             ]}]},
        ],
    })

    return {'cover': cover, 'sections': sections}
