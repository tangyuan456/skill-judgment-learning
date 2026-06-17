"""单次测试报告模板（report_type=single）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
from constants import SCENARIO_CN, SCENARIOS as STD_SCENARIOS  # noqa: E402


def fmt_int(v):
    return f'{v:,.0f}' if v is not None else '-'


def fmt_float(v, n=2):
    return f'{v:,.{n}f}' if v is not None else '-'


def build_single_report_data(extracted, analysis, insights, intent, charts_dir_rel='charts'):
    meta = extracted['meta']
    records = extracted['records']
    products = meta['products']
    scenarios = [s for s in STD_SCENARIOS if s in meta['scenarios']] + \
                [s for s in meta['scenarios'] if s not in STD_SCENARIOS]
    main_product = products[0]
    concurrencies = meta['concurrencies']

    cover = {
        'title': '数据库性能测试报告',
        'subtitle': f'{main_product} sysbench OLTP 测试',
        'date': '2026-06-16',
        'version': 'v1.0',
    }

    sections = []

    # === 第 1 章 测试结论 ===
    sp = analysis.get('single_product', {}).get(main_product, {})
    peak_summary = sp.get('peak_summary', [])
    peak_summary.sort(key=lambda x: STD_SCENARIOS.index(x['scenario'])
                       if x['scenario'] in STD_SCENARIOS else 99)

    max_ps = max(peak_summary, key=lambda x: x['peak_qps']) if peak_summary else {'peak_qps': 0, 'scenario': '', 'peak_threads': 0}
    min_ps = min(peak_summary, key=lambda x: x['peak_qps']) if peak_summary else {'peak_qps': 0, 'scenario': '', 'peak_threads': 0}

    summary_text = (
        f'{main_product} 在 sysbench {len(scenarios)} 个 OLTP 场景下完成测试，'
        f'覆盖并发档 {concurrencies}。'
        f'峰值 QPS 最高出现在 {SCENARIO_CN.get(max_ps["scenario"], max_ps["scenario"])}'
        f'（{fmt_int(max_ps["peak_qps"])} @ {max_ps["peak_threads"]} 并发），'
        f'最低出现在 {SCENARIO_CN.get(min_ps["scenario"], min_ps["scenario"])}'
        f'（{fmt_int(min_ps["peak_qps"])} @ {min_ps["peak_threads"]} 并发）。'
    )

    key_rows = [
        [SCENARIO_CN.get(ps['scenario'], ps['scenario']), str(ps['peak_threads']),
         fmt_int(ps['peak_qps']), fmt_float(ps.get('peak_p95_ms', 0))]
        for ps in peak_summary
    ]
    sections.append({
        'id': 'ch1', 'title': '第 1 章 测试结论', 'blocks': [], 'subsections': [
            {'id': 'ch1_1', 'title': '1.1 测试结论摘要',
             'blocks': [{'type': 'paragraph', 'text': summary_text}]},
            {'id': 'ch1_2', 'title': '1.2 关键性能数字',
             'blocks': [{'type': 'table',
                         'headers': ['场景', '峰值并发', '峰值 QPS', 'P95 (ms)'],
                         'rows': key_rows}]},
            {'id': 'ch1_3', 'title': '1.3 核心结论', 'blocks': [
                {'type': 'image',
                 'path': f'{charts_dir_rel}/single_peak_summary.png',
                 'caption': f'{main_product} 场景峰值汇总'},
                {'type': 'insight', 'level': 'L1',
                 'text': summary_text,
                 'source': f'analysis_results.single_product.{main_product}.peak_summary'},
            ]},
        ],
    })

    # === 第 2 章 测试环境 ===
    log_meta = meta.get('log_meta', [{}])[0] if meta.get('log_meta') else {}
    sections.append({
        'id': 'ch2', 'title': '第 2 章 测试环境', 'blocks': [], 'subsections': [
            {'id': 'ch2_1', 'title': '2.1 数据库配置', 'blocks': [
                {'type': 'table',
                 'headers': ['项', '值'],
                 'rows': [
                     ['产品', main_product],
                     ['DB 端点', log_meta.get('db_endpoint', '-')],
                     ['数据集', log_meta.get('data_config', '-')],
                     ['单测时长', f"{log_meta.get('duration_sec','-')}s"],
                 ]},
            ]},
            {'id': 'ch2_2', 'title': '2.2 测试方法', 'blocks': [
                {'type': 'table', 'headers': ['项', '值'], 'rows': [
                    ['测试工具', log_meta.get('engine', 'sysbench')],
                    ['测试场景', '、'.join(SCENARIO_CN.get(s, s) for s in scenarios)],
                    ['并发档', str(concurrencies)],
                ]},
            ]},
            {'id': 'ch2_3', 'title': '2.3 数据质量', 'blocks': [
                {'type': 'table', 'headers': ['检查项', '结果'], 'rows': [
                    ['总记录数', f'{len(records)} 条'],
                    ['TPS / QPS / P95 有效率', '100%'],
                    ['数据来源', meta.get('source_info', {}).get('value', '-')],
                ]},
            ]},
        ],
    })

    # === 第 3 章 全量数据 ===
    rows = []
    for s in scenarios:
        srs = sorted([r for r in records if r['scenario'] == s], key=lambda r: r['threads'])
        for r in srs:
            rows.append([
                SCENARIO_CN.get(r['scenario'], r['scenario']),
                str(r['threads']),
                fmt_float(r['tps']), fmt_float(r['qps']),
                fmt_float(r['p95_ms']),
                fmt_float(r['p99_ms']) if r.get('p99_ms') is not None else '-',
            ])
    sections.append({
        'id': 'ch3', 'title': '第 3 章 全量测试数据', 'blocks': [
            {'type': 'table',
             'headers': ['场景', '并发', 'TPS', 'QPS', 'P95 (ms)', 'P99 (ms)'],
             'rows': rows},
        ], 'subsections': [],
    })

    # === 第 4 章 性能分析 ===
    ch4_subs = []
    for i, s in enumerate(scenarios, 1):
        ch4_subs.append({
            'id': f'ch4_1_{i}', 'title': f'4.1.{i} {SCENARIO_CN.get(s, s)}并发扩展',
            'blocks': [
                {'type': 'image',
                 'path': f'{charts_dir_rel}/single_qps_{s}.png',
                 'caption': f'{SCENARIO_CN.get(s, s)} 并发-QPS 曲线'},
                {'type': 'image',
                 'path': f'{charts_dir_rel}/single_p95_{s}.png',
                 'caption': f'{SCENARIO_CN.get(s, s)} 并发-P95 曲线'},
            ],
        })
    sections.append({
        'id': 'ch4', 'title': '第 4 章 性能分析', 'blocks': [], 'subsections': ch4_subs,
    })

    # === 第 5 章 优化建议 ===
    sections.append({
        'id': 'ch5', 'title': '第 5 章 优化建议', 'blocks': [], 'subsections': [
            {'id': 'ch5_1', 'title': '5.1 调优最佳实践', 'blocks': [
                {'type': 'bullet', 'items': [
                    f'峰值 QPS 出现在 {SCENARIO_CN.get(max_ps["scenario"], max_ps["scenario"])} @ {max_ps["peak_threads"]} 并发，建议生产连接池上限 {int(max_ps["peak_threads"]*1.5)}。',
                    'Buffer Pool 建议设为内存的 70%~75%。',
                    '回归测试保持 sysbench 参数 `--db-ps-mode=auto --skip_trx=off --rand-type=uniform`。',
                ]},
            ]},
            {'id': 'ch5_2', 'title': '5.2 测试边界', 'blocks': [
                {'type': 'bullet', 'items': [
                    f'仅覆盖 sysbench {len(scenarios)} 个 OLTP 场景。',
                    '未覆盖 OLAP / 复杂 JOIN / 大字段场景。',
                    '单数据集，未测试更大规模数据下的衰减。',
                ]},
            ]},
        ],
    })

    return {'cover': cover, 'sections': sections}
