"""客制化/专项报告模板（report_type=custom）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
from constants import SCENARIO_CN  # noqa: E402


def fmt_int(v):
    return f'{v:,.0f}' if v is not None else '-'


def fmt_float(v, n=2):
    return f'{v:,.{n}f}' if v is not None else '-'


def build_custom_report_data(extracted, analysis, insights, intent, charts_dir_rel='charts'):
    meta = extracted['meta']
    custom_cfg = intent.get('custom_config') or {}
    focus = custom_cfg.get('focus_dimension', '通用分析')

    cover = {
        'title': f'{focus} 专项报告',
        'subtitle': '数据库性能客制化分析',
        'date': '2026-06-16',
        'version': 'v1.0',
    }

    sections = []

    # === 第 1 章 分析目标 ===
    focus_desc = {
        'buffer_pool': '分析不同 Buffer Pool 配置下的性能差异',
        'numa': '分析 NUMA 绑定/未绑定对性能的影响',
        '高并发': '分析高并发场景下的性能瓶颈和极限 QPS',
        '表数量': '分析不同表数量下的性能衰减趋势',
    }
    desc = focus_desc.get(focus, f'针对 {focus} 维度的深度分析')
    if intent.get('other_info'):
        desc += f'。用户补充需求：{intent["other_info"]}'

    sections.append({
        'id': 'ch1', 'title': '第 1 章 分析目标', 'blocks': [], 'subsections': [
            {'id': 'ch1_1', 'title': '1.1 分析说明', 'blocks': [
                {'type': 'paragraph', 'text': desc},
            ]},
            {'id': 'ch1_2', 'title': '1.2 数据范围', 'blocks': [
                {'type': 'table', 'headers': ['项', '值'], 'rows': [
                    ['产品', '、'.join(meta.get('products', []))],
                    ['场景', '、'.join(SCENARIO_CN.get(s, s) for s in meta.get('scenarios', []))],
                    ['记录数', f'{len(extracted.get("records", []))} 条'],
                    ['数据来源', meta.get('source_info', {}).get('value', '-')],
                ]},
            ]},
        ],
    })

    # === 第 2 章 深度分析 ===
    custom = analysis.get('custom') or {}
    buckets = custom.get('buckets') or []

    bucket_rows = []
    for b in buckets:
        bucket_rows.append([
            b.get('label', '-'),
            fmt_int(b.get('avg_qps')),
            fmt_float(b.get('avg_p95_ms')),
            str(b.get('sample_size', '-')),
        ])

    ch2_blocks = [
        {'type': 'paragraph',
         'text': f'按 {focus} 分桶后，各桶平均性能如下：'},
        {'type': 'table',
         'headers': ['分桶', '平均 QPS', '平均 P95 (ms)', '样本数'],
         'rows': bucket_rows},
        {'type': 'image', 'path': f'{charts_dir_rel}/custom_main.png',
         'caption': f'{focus} 维度与平均 QPS'},
        {'type': 'image', 'path': f'{charts_dir_rel}/custom_compare.png',
         'caption': f'{focus} QPS vs P95 对比'},
    ]

    # 附加洞察
    insight_items = insights.get('items', [])
    for ins in insight_items:
        ch2_blocks.append({
            'type': 'insight', 'level': ins.get('level', 'L2'),
            'text': ins.get('text', ''), 'source': ins.get('source', ''),
        })

    sections.append({
        'id': 'ch2', 'title': '第 2 章 深度分析', 'blocks': [], 'subsections': [
            {'id': 'ch2_1', 'title': f'2.1 {focus} 分桶分析', 'blocks': ch2_blocks},
        ],
    })

    # === 第 3 章 结论与建议 ===
    finding = custom.get('main_finding', '分析完成，详见分桶数据。')
    sections.append({
        'id': 'ch3', 'title': '第 3 章 结论与建议', 'blocks': [], 'subsections': [
            {'id': 'ch3_1', 'title': '3.1 核心发现', 'blocks': [
                {'type': 'insight', 'level': 'L2',
                 'text': finding, 'source': 'analysis_results.custom'},
            ]},
            {'id': 'ch3_2', 'title': '3.2 建议与后续', 'blocks': [
                {'type': 'bullet', 'items': [
                    f'本报告聚焦 {focus} 维度，建议结合实际业务场景做进一步验证。',
                    '如需扩展分析维度，可在门控①阶段补充需求。',
                    '数据可能存在采集条件差异，请在结论中标注不确定性。',
                ]},
            ]},
        ],
    })

    return {'cover': cover, 'sections': sections}
