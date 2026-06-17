"""TPC-DS 单次测试报告模板（data_kind=tpcds_duration）。"""
from __future__ import annotations
from datetime import date


def _fmt(v, n=3):
    return f'{v:,.{n}f}' if isinstance(v, (int, float)) else '-'


def build_tpcds_single_report_data(extracted, analysis, insights, intent, charts_dir_rel='charts'):
    meta = extracted['meta']
    records = extracted['records']
    env = meta.get('test_env') or {}
    main_product = analysis.get('main_product') or (meta['products'] or ['unknown'])[0]
    stats = analysis.get('tpcds_stats', {})
    top_slow = analysis.get('tpcds_top10_slow', [])
    top_fast = analysis.get('tpcds_top10_fast', [])
    full_table = analysis.get('tpcds_full_table', [])
    load = analysis.get('tpcds_load', [])
    ins = insights.get('tpcds_insights', [])
    source = meta.get('source_info', {})

    cover = {
        'title': f'{main_product} TPC-DS 性能测试报告',
        'subtitle': f'数据源: {source.get("value","-")}（共 {stats.get("query_count",0)} 个查询）',
        'date': date.today().isoformat(),
        'version': 'v1.0',
    }

    sections = []

    # === 第 1 章 测试结论 ===
    l1 = ins[0]['text'] if ins else f'{main_product} 共完成 {stats.get("query_count",0)} 个 TPC-DS 查询。'

    key_table = [
        ['查询数', str(stats.get('query_count', 0))],
        ['总耗时', f'{_fmt(stats.get("total_duration_s"),2)} s'],
        ['平均耗时', f'{_fmt(stats.get("avg_duration_s"))} s'],
        ['中位数耗时', f'{_fmt(stats.get("median_duration_s"))} s'],
        ['最大耗时', f'{_fmt(stats.get("max_duration_s"),2)} s'],
        ['最小耗时', f'{_fmt(stats.get("min_duration_s"))} s'],
        ['P95 耗时', f'{_fmt(stats.get("p95_duration_s"),2)} s'],
        ['P99 耗时', f'{_fmt(stats.get("p99_duration_s"),2)} s'],
    ]

    ch1_blocks = [
        {'type': 'paragraph', 'text': l1},
        {'type': 'table', 'headers': ['指标', '值'], 'rows': key_table},
        {'type': 'image', 'path': f'{charts_dir_rel}/tpcds_duration_dist.png',
         'caption': 'TPC-DS 查询耗时分布'},
    ]
    for item in ins:
        ch1_blocks.append({'type': 'insight', 'level': item.get('level', 'L1'),
                           'text': item.get('text', ''), 'source': item.get('source', '')})

    sections.append({
        'id': 'ch1', 'title': '第 1 章 测试结论', 'blocks': ch1_blocks, 'subsections': [],
    })

    # === 第 2 章 测试环境 ===
    env_rows = []
    for k, label in [
        ('product_type', '产品类型'), ('deploy_arch', '部署架构'),
        ('env_tag', '环境标签'), ('cn_version', 'CN 版本'),
        ('dn_version', 'DN 版本'), ('cvm_cpu', 'CPU 核数'),
        ('cvm_memory', '内存'), ('cpu_arch', 'CPU 架构'),
        ('machine_type', '机器类型'), ('machine_model', '机器型号'),
        ('cpu_performance_mode', 'CPU 性能模式'),
        ('node_config', '节点配置'), ('network_type', '网络类型'),
        ('kernel_config', '内核配置'), ('requirement_type', '需求类型'),
        ('test_category', '测试类型'),
    ]:
        v = env.get(k)
        if v is None or v == '' or str(v).upper() == 'N/A':
            v = '-'
        env_rows.append([label, str(v)])

    source_rows = [
        ['数据源', f'{source.get("type","-")} / {source.get("value","-")}'],
        ['总返回行数', str(source.get('total_rows_in_source', source.get('rows_fetched', 0)))],
        ['有效查询行数', str(source.get('rows_fetched', 0))],
        ['测试工具', 'mrthree (TPC-DS)'],
    ]

    sections.append({
        'id': 'ch2', 'title': '第 2 章 测试环境', 'blocks': [], 'subsections': [
            {'id': 'ch2_1', 'title': '2.1 数据库与硬件环境',
             'blocks': [{'type': 'table', 'headers': ['项', '值'], 'rows': env_rows}]},
            {'id': 'ch2_2', 'title': '2.2 数据来源',
             'blocks': [{'type': 'table', 'headers': ['项', '值'], 'rows': source_rows}]},
        ],
    })

    # === 第 3 章 全量查询耗时 ===
    # 分页：优先放 Top 10 慢 / 快，然后全量
    slow_rows = [[x['query_label'], _fmt(x['duration_s'], 2)] for x in top_slow]
    fast_rows = [[x['query_label'], _fmt(x['duration_s'], 3)] for x in top_fast]
    full_rows = [[x['query_label'], _fmt(x['duration_s'], 3), x.get('test_name', '-')] for x in full_table]
    load_rows = [[x['query_label'], _fmt(x['duration_s'], 2), x.get('test_name', '-')] for x in load]

    ch3_subs = [
        {'id': 'ch3_1', 'title': '3.1 Top 10 最慢查询',
         'blocks': [
             {'type': 'image', 'path': f'{charts_dir_rel}/tpcds_top10_slow.png',
              'caption': 'Top 10 最慢查询耗时'},
             {'type': 'table', 'headers': ['查询', '耗时 (s)'], 'rows': slow_rows},
         ]},
        {'id': 'ch3_2', 'title': '3.2 Top 10 最快查询',
         'blocks': [{'type': 'table', 'headers': ['查询', '耗时 (s)'], 'rows': fast_rows}]},
        {'id': 'ch3_3', 'title': f'3.3 全量 {len(full_rows)} 查询耗时',
         'blocks': [
             {'type': 'image', 'path': f'{charts_dir_rel}/tpcds_all_queries.png',
              'caption': '全量 TPC-DS 查询耗时（红色=超过 P95）'},
             {'type': 'table', 'headers': ['查询', '耗时 (s)', 'test_name'], 'rows': full_rows},
         ]},
    ]
    if load_rows:
        ch3_subs.append({
            'id': 'ch3_4', 'title': '3.4 数据加载耗时',
            'blocks': [{'type': 'table', 'headers': ['步骤', '耗时 (s)', 'test_name'], 'rows': load_rows}],
        })
    sections.append({
        'id': 'ch3', 'title': '第 3 章 全量查询耗时', 'blocks': [], 'subsections': ch3_subs,
    })

    # === 第 4 章 结论与后续建议 ===
    avg = stats.get('avg_duration_s') or 0
    slowest_label = top_slow[0]['query_label'] if top_slow else '-'
    slowest_dur = top_slow[0]['duration_s'] if top_slow else 0
    slow_ratio = (slowest_dur / avg) if avg else 0

    sections.append({
        'id': 'ch4', 'title': '第 4 章 结论与建议', 'blocks': [], 'subsections': [
            {'id': 'ch4_1', 'title': '4.1 核心结论',
             'blocks': [{'type': 'bullet', 'items': [
                 f'本次执行覆盖 {stats.get("query_count",0)} 个 TPC-DS 查询，总耗时 {_fmt(stats.get("total_duration_s"),2)}s。',
                 f'最慢查询为 {slowest_label}（{_fmt(slowest_dur,2)}s），为平均耗时的 {slow_ratio:.1f}x。',
                 f'P95 / P99 耗时分别为 {_fmt(stats.get("p95_duration_s"),2)}s / {_fmt(stats.get("p99_duration_s"),2)}s，长尾查询占比较高时需重点关注执行计划。',
             ]}]},
            {'id': 'ch4_2', 'title': '4.2 待确认项',
             'blocks': [{'type': 'insight', 'level': 'L3',
                         'text': '[待确认] TPC-DS 基准耗时受数据规模 SF（scale factor）、并行度与内存配置强相关，建议后续补充 SF=1/10/100 的对比数据。',
                         'source': 'empirical'}]},
            {'id': 'ch4_3', 'title': '4.3 后续测试建议',
             'blocks': [{'type': 'bullet', 'items': [
                 '对最慢 Top 5 查询执行 EXPLAIN (ANALYZE, BUFFERS)，定位瓶颈算子。',
                 '对比不同 work_mem / shared_buffers / max_parallel_workers_per_gather 参数下的耗时。',
                 '建立基线：记录本次结果作为基线，未来版本升级做回归对比。',
             ]}]},
        ],
    })

    return {'cover': cover, 'sections': sections}
