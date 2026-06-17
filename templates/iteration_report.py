"""迭代演进报告模板（report_type=iteration）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
from constants import SCENARIO_CN, SCENARIOS as STD_SCENARIOS  # noqa: E402


def fmt_int(v):
    return f'{v:,.0f}' if v is not None else '-'


def fmt_pct(v):
    return f'{v:+.1f}%' if v is not None else '-'


def build_iteration_report_data(extracted, analysis, insights, intent, charts_dir_rel='charts'):
    meta = extracted['meta']
    scenarios = [s for s in STD_SCENARIOS if s in meta['scenarios']] + \
                [s for s in meta['scenarios'] if s not in STD_SCENARIOS]

    iteration = analysis.get('iteration') or {}
    versions = iteration.get('version_order') or meta['products']
    trend = iteration.get('trend', {})
    cumulative = iteration.get('cumulative_change', {})
    regressions = iteration.get('regression_points', [])

    cover = {
        'title': '数据库版本迭代演进报告',
        'subtitle': f'{versions[0]} → {versions[-1]} 共 {len(versions)} 个版本',
        'date': '2026-06-16',
        'version': 'v1.0',
    }

    sections = []

    # === 第 1 章 演进结论 ===
    cum_rows = [
        [SCENARIO_CN.get(s, s),
         fmt_int((trend.get(s, [{}])[0].get('peak_qps')) if trend.get(s) else None),
         fmt_int((trend.get(s, [{}])[-1].get('peak_qps')) if trend.get(s) else None),
         fmt_pct(cumulative.get(s))]
        for s in scenarios
    ]
    summary_text = (
        f'本报告覆盖 {len(versions)} 个版本（{versions[0]} → {versions[-1]}）的 '
        f'{len(scenarios)} 个 sysbench 场景峰值 QPS 演进。'
        + (f'已检出 {len(regressions)} 个性能回归点。' if regressions else '未检出性能回归。')
    )
    sections.append({
        'id': 'ch1', 'title': '第 1 章 演进结论', 'blocks': [], 'subsections': [
            {'id': 'ch1_1', 'title': '1.1 演进摘要',
             'blocks': [{'type': 'paragraph', 'text': summary_text}]},
            {'id': 'ch1_2', 'title': '1.2 累计变化', 'blocks': [
                {'type': 'table',
                 'headers': ['场景', f'首版 ({versions[0]})', f'末版 ({versions[-1]})', '累计变化'],
                 'rows': cum_rows},
                {'type': 'image', 'path': f'{charts_dir_rel}/iter_cumulative.png',
                 'caption': '场景累计变化柱状图'},
            ]},
            {'id': 'ch1_3', 'title': '1.3 关键发现', 'blocks': [
                {'type': 'insight', 'level': 'L1',
                 'text': summary_text, 'source': 'analysis_results.iteration'},
            ] + ([
                {'type': 'insight', 'level': 'L2',
                 'text': f'回归点：{r["version"]} 在 {SCENARIO_CN.get(r["scenario"], r["scenario"])} 场景峰值下降 {abs(r["delta_pct"]):.1f}%',
                 'source': f'analysis_results.iteration.regression_points'} for r in regressions[:5]
            ]),
            },
        ],
    })

    # === 第 2 章 版本与环境 ===
    sections.append({
        'id': 'ch2', 'title': '第 2 章 版本清单与环境', 'blocks': [], 'subsections': [
            {'id': 'ch2_1', 'title': '2.1 版本清单',
             'blocks': [{'type': 'table', 'headers': ['版本'], 'rows': [[v] for v in versions]}]},
            {'id': 'ch2_2', 'title': '2.2 数据来源',
             'blocks': [{'type': 'paragraph',
                         'text': f"数据源：{meta.get('source_info', {}).get('type', '-')} "
                                 f"({meta.get('source_info', {}).get('value', '-')})，"
                                 f"共 {meta.get('source_info', {}).get('rows_fetched', 0)} 条记录。"}]},
        ],
    })

    # === 第 3 章 各版本数据 ===
    ch3_subs = []
    records = extracted['records']
    for i, v in enumerate(versions, 1):
        rows = []
        for s in scenarios:
            srs = sorted([r for r in records if r['product'] == v and r['scenario'] == s],
                         key=lambda r: r['threads'])
            for r in srs:
                rows.append([SCENARIO_CN.get(s, s), str(r['threads']),
                             fmt_int(r['tps']), fmt_int(r['qps']),
                             f"{r['p95_ms']:.2f}" if r.get('p95_ms') else '-',
                             f"{r['p99_ms']:.2f}" if r.get('p99_ms') else '-'])
        ch3_subs.append({
            'id': f'ch3_{i}', 'title': f'3.{i} {v}',
            'blocks': [{'type': 'table',
                        'headers': ['场景', '并发', 'TPS', 'QPS', 'P95 (ms)', 'P99 (ms)'],
                        'rows': rows}]
        })
    sections.append({
        'id': 'ch3', 'title': '第 3 章 全版本性能数据', 'blocks': [], 'subsections': ch3_subs,
    })

    # === 第 4 章 演进分析 ===
    ch4_subs = []
    for i, s in enumerate(scenarios, 1):
        rows = trend.get(s, [])
        tbl = [[r.get('version'), fmt_int(r.get('peak_qps')), fmt_pct(r.get('delta_pct'))]
               for r in rows]
        ch4_subs.append({
            'id': f'ch4_1_{i}', 'title': f'4.1.{i} {SCENARIO_CN.get(s, s)}演进',
            'blocks': [
                {'type': 'table',
                 'headers': ['版本', '峰值 QPS', '相对前版本'],
                 'rows': tbl},
                {'type': 'image', 'path': f'{charts_dir_rel}/iter_trend_qps_{s}.png',
                 'caption': f'{SCENARIO_CN.get(s, s)} 峰值演进趋势'},
                {'type': 'image', 'path': f'{charts_dir_rel}/iter_trend_p95_{s}.png',
                 'caption': f'{SCENARIO_CN.get(s, s)} P95 演进趋势'},
            ],
        })
    if regressions:
        ch4_subs.append({
            'id': 'ch4_2', 'title': '4.2 回归点详情',
            'blocks': [{'type': 'table',
                        'headers': ['版本', '场景', '峰值 QPS', '相对前版本'],
                        'rows': [[r['version'], SCENARIO_CN.get(r['scenario'], r['scenario']),
                                  fmt_int(r.get('peak_qps')), fmt_pct(r.get('delta_pct'))]
                                 for r in regressions]},
                       {'type': 'image', 'path': f'{charts_dir_rel}/iter_regression.png',
                        'caption': '回归点散点图'}],
        })
    sections.append({
        'id': 'ch4', 'title': '第 4 章 演进分析', 'blocks': [], 'subsections': ch4_subs,
    })

    # === 第 5 章 优化建议 ===
    advice = []
    if regressions:
        advice.append(f'重点排查 {len(regressions)} 个回归点，优先恢复峰值跌幅最大的场景。')
    advance_scenarios = [s for s, c in cumulative.items() if c and c > 5]
    if advance_scenarios:
        advice.append(f'持续优化方向：{"、".join(SCENARIO_CN.get(s, s) for s in advance_scenarios)} 场景累计提升显著，可作为后续宣传重点。')
    advice.append('对未测试的高并发段进行抽样验证，确认演进趋势在生产并发下成立。')

    sections.append({
        'id': 'ch5', 'title': '第 5 章 优化建议', 'blocks': [], 'subsections': [
            {'id': 'ch5_1', 'title': '5.1 持续优化方向',
             'blocks': [{'type': 'bullet', 'items': advice}]},
            {'id': 'ch5_2', 'title': '5.2 测试边界',
             'blocks': [{'type': 'bullet', 'items': [
                 '硬件环境应保持一致；本报告假设 N 个版本测试硬件相同。',
                 '回归阈值默认 5%，可在 intent.iteration_config.regression_threshold_pct 调整。',
             ]}]},
        ],
    })

    return {'cover': cover, 'sections': sections}
