"""对比报告模板（report_type=comparison）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
from constants import SCENARIO_CN, SCENARIOS as STD_SCENARIOS  # noqa: E402


def fmt_int(v):
    return f'{v:,.0f}' if v is not None else '-'


def fmt_float(v, n=2):
    return f'{v:,.{n}f}' if v is not None else '-'


def build_comparison_report_data(extracted, analysis, insights, intent, charts_dir_rel='charts'):
    meta = extracted['meta']
    records = extracted['records']
    products = meta['products']
    scenarios = [s for s in STD_SCENARIOS if s in meta['scenarios']] + \
                [s for s in meta['scenarios'] if s not in STD_SCENARIOS]

    cover = {
        'title': '数据库性能对比报告',
        'subtitle': f'{" vs ".join(products)} sysbench OLTP 对比',
        'date': '2026-06-16',
        'version': 'v1.0',
    }

    sections = []

    # === 第 1 章 对比结论 ===
    compare = analysis.get('product_compare', {})
    ratio_matrix = compare.get('ratio_matrix', {})
    fairness = compare.get('fairness', {})

    summary_parts = [f'本报告对比 {len(products)} 个产品：{"、".join(products)}，覆盖 {len(scenarios)} 个 sysbench 场景。']
    if not fairness.get('passed'):
        summary_parts.append('⚠️ 公平性检查未完全通过，请注意数据采集条件可能存在差异。')

    summary_text = ' '.join(summary_parts)

    ch1_blocks = [{'type': 'paragraph', 'text': summary_text}]

    # 性能比值表
    if ratio_matrix:
        ratio_headers = ['场景'] + products
        ratio_rows = []
        for s in scenarios:
            row = ratio_matrix.get(s, {})
            if row:
                ratio_rows.append([SCENARIO_CN.get(s, s)] + [
                    f'{row.get(p, "-"):.2f}x' if isinstance(row.get(p), (int, float)) else '-'
                    for p in products
                ])
        ch1_blocks.append({'type': 'paragraph', 'text': f'以 {products[0]} 为基准（1.00x）的性能比值矩阵：'})
        ch1_blocks.append({'type': 'table', 'headers': ratio_headers, 'rows': ratio_rows})

    # 洞察
    insight_items = insights.get('items', [])
    for ins in insight_items:
        ch1_blocks.append({
            'type': 'insight', 'level': ins.get('level', 'L1'),
            'text': ins.get('text', ''), 'source': ins.get('source', ''),
        })

    sections.append({
        'id': 'ch1', 'title': '第 1 章 对比结论', 'blocks': [], 'subsections': [
            {'id': 'ch1_1', 'title': '1.1 对比摘要', 'blocks': ch1_blocks},
        ],
    })

    # === 第 2 章 测试环境 ===
    sections.append({
        'id': 'ch2', 'title': '第 2 章 测试环境', 'blocks': [], 'subsections': [
            {'id': 'ch2_1', 'title': '2.1 产品列表', 'blocks': [
                {'type': 'table', 'headers': ['产品'], 'rows': [[p] for p in products]},
            ]},
            {'id': 'ch2_2', 'title': '2.2 公平性检查', 'blocks': [
                {'type': 'paragraph',
                 'text': '通过' if fairness.get('passed') else '⚠️ 未完全通过，以下为发现问题：'},
            ] + ([
                {'type': 'bullet', 'items': fairness.get('issues', ['-'])}
            ] if not fairness.get('passed') else [])},
        ],
    })

    # === 第 3 章 全量数据 ===
    ch3_subs = []
    for p in products:
        rows = []
        for s in scenarios:
            srs = sorted([r for r in records if r['product'] == p and r['scenario'] == s],
                         key=lambda r: r['threads'])
            for r in srs:
                rows.append([SCENARIO_CN.get(s, s), str(r['threads']),
                             fmt_float(r['tps']), fmt_float(r['qps']),
                             fmt_float(r['p95_ms']),
                             fmt_float(r['p99_ms']) if r.get('p99_ms') is not None else '-'])
        ch3_subs.append({
            'id': f'ch3_{products.index(p)+1}', 'title': f'3.{products.index(p)+1} {p}',
            'blocks': [{'type': 'table',
                        'headers': ['场景', '并发', 'TPS', 'QPS', 'P95 (ms)', 'P99 (ms)'],
                        'rows': rows}],
        })
    sections.append({
        'id': 'ch3', 'title': '第 3 章 全量性能数据', 'blocks': [], 'subsections': ch3_subs,
    })

    # === 第 4 章 性能对比 ===
    ch4_subs = []
    for i, s in enumerate(scenarios, 1):
        sp = compare.get('single_product', {})
        peak_rows = []
        for p in products:
            pdata = sp.get(p, {}).get('peak_summary', [])
            for pp in pdata:
                if pp['scenario'] == s:
                    peak_rows.append([
                        p, str(pp['peak_threads']),
                        fmt_int(pp['peak_qps']), fmt_float(pp.get('peak_p95_ms', 0)),
                    ])
                    break

        ch4_subs.append({
            'id': f'ch4_{i}', 'title': f'4.{i} {SCENARIO_CN.get(s, s)}对比',
            'blocks': [
                {'type': 'table',
                 'headers': ['产品', '峰值并发', '峰值 QPS', 'P95 (ms)'],
                 'rows': peak_rows},
                {'type': 'image',
                 'path': f'{charts_dir_rel}/comparison_peak_{s}.png',
                 'caption': f'{SCENARIO_CN.get(s, s)} 峰值 QPS 对比'},
                {'type': 'image',
                 'path': f'{charts_dir_rel}/comparison_qps_{s}.png',
                 'caption': f'{SCENARIO_CN.get(s, s)} 并发-QPS 曲线对比'},
                {'type': 'image',
                 'path': f'{charts_dir_rel}/comparison_p95_{s}.png',
                 'caption': f'{SCENARIO_CN.get(s, s)} 并发-P95 曲线对比'},
            ],
        })

    # 综合对比图
    ch4_subs.append({
        'id': 'ch4_radar', 'title': f'4.{len(scenarios)+1} 综合对比',
        'blocks': [
            {'type': 'image',
             'path': f'{charts_dir_rel}/comparison_radar.png',
             'caption': '各场景峰值 QPS 雷达图'},
            {'type': 'image',
             'path': f'{charts_dir_rel}/comparison_ladder.png',
             'caption': '各场景峰值 QPS 天梯对比'},
        ],
    })

    sections.append({
        'id': 'ch4', 'title': '第 4 章 性能对比分析', 'blocks': [], 'subsections': ch4_subs,
    })

    # === 第 5 章 结论与建议 ===
    sections.append({
        'id': 'ch5', 'title': '第 5 章 结论与建议', 'blocks': [], 'subsections': [
            {'id': 'ch5_1', 'title': '5.1 选型建议', 'blocks': [
                {'type': 'bullet', 'items': [
                    '以上对比数据基于 sysbench OLTP 基准测试，实际生产表现可能因业务特征而有所不同。',
                    '建议结合业务最频繁的查询模式（read_only/read_write/point_select）做加权决策。',
                    '若需 OLAP 对比，请补充 TPC-H 测试数据。',
                ]},
            ]},
            {'id': 'ch5_2', 'title': '5.2 测试公平性说明', 'blocks': [
                {'type': 'paragraph',
                 'text': '通过' if fairness.get('passed') else f'⚠️ 以下问题可能影响对比公平性：{"；".join(fairness.get("issues", []))}'},
            ]},
        ],
    })

    return {'cover': cover, 'sections': sections}
