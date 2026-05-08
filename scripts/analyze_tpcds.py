#!/usr/bin/env python3
"""TPC-DS 数据分析（duration_s 指标）。

输入：data_kind=tpcds_duration 的 extracted_data.json
输出：analysis_results（按 duration 排序、总耗时、TopN 慢查询等）+ insights
"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple


def _sort_key_by_q(label: str) -> Tuple[int, str]:
    if label.startswith('Q'):
        try:
            return (int(label[1:]), label)
        except ValueError:
            return (99999, label)
    return (99999, label)


def analyze_tpcds(extracted: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
    records = extracted['records']
    main_product = (extracted['meta']['products'] or ['unknown'])[0]

    query_rows = [r for r in records if not r.get('is_load')]
    load_rows = [r for r in records if r.get('is_load')]

    # 按 duration 排序
    sorted_desc = sorted(query_rows, key=lambda r: (r['duration_s'] or 0), reverse=True)
    sorted_asc = sorted(query_rows, key=lambda r: (r['duration_s'] or 0))

    durations = [r['duration_s'] for r in query_rows if r['duration_s'] is not None]
    total = sum(durations) if durations else 0
    avg = (total / len(durations)) if durations else 0
    mx = max(durations) if durations else 0
    mn = min(durations) if durations else 0
    # 中位数
    if durations:
        s = sorted(durations)
        n = len(s)
        median = s[n // 2] if n % 2 == 1 else (s[n // 2 - 1] + s[n // 2]) / 2
    else:
        median = 0
    # P95 / P99
    def _pct(arr, p):
        if not arr:
            return 0.0
        s2 = sorted(arr)
        k = int(round((p / 100.0) * (len(s2) - 1)))
        return s2[k]
    p95 = _pct(durations, 95)
    p99 = _pct(durations, 99)

    # 按查询号排序的完整表
    by_q = sorted(query_rows, key=lambda r: _sort_key_by_q(r.get('query_label', '')))

    top10_slow = [
        {'query_label': r['query_label'], 'duration_s': r['duration_s'],
         'test_name': r.get('test_name')}
        for r in sorted_desc[:10]
    ]
    top10_fast = [
        {'query_label': r['query_label'], 'duration_s': r['duration_s'],
         'test_name': r.get('test_name')}
        for r in sorted_asc[:10]
    ]

    analysis = {
        'report_type': 'single',
        'data_kind': 'tpcds_duration',
        'main_product': main_product,
        'tpcds_stats': {
            'query_count': len(query_rows),
            'load_count': len(load_rows),
            'total_duration_s': round(total, 3),
            'avg_duration_s': round(avg, 3),
            'median_duration_s': round(median, 3),
            'min_duration_s': round(mn, 3),
            'max_duration_s': round(mx, 3),
            'p95_duration_s': round(p95, 3),
            'p99_duration_s': round(p99, 3),
        },
        'tpcds_top10_slow': top10_slow,
        'tpcds_top10_fast': top10_fast,
        'tpcds_full_table': [
            {'query_label': r['query_label'], 'duration_s': r['duration_s'],
             'test_name': r.get('test_name')}
            for r in by_q
        ],
        'tpcds_load': [
            {'query_label': r['query_label'], 'duration_s': r['duration_s'],
             'test_name': r.get('test_name')}
            for r in load_rows
        ],
    }

    insights = {'tpcds_insights': []}
    insights['tpcds_insights'].append({
        'level': 'L1',
        'text': (
            f"TPC-DS 共完成 {len(query_rows)} 个查询（{main_product}），"
            f"总耗时 {analysis['tpcds_stats']['total_duration_s']:.2f}s，"
            f"平均 {analysis['tpcds_stats']['avg_duration_s']:.3f}s，"
            f"中位数 {analysis['tpcds_stats']['median_duration_s']:.3f}s，"
            f"最慢 {analysis['tpcds_stats']['max_duration_s']:.2f}s，"
            f"最快 {analysis['tpcds_stats']['min_duration_s']:.3f}s。"
        ),
        'source': 'analysis_results.tpcds_stats',
        'scenario': 'all',
    })
    if top10_slow:
        slow_label = top10_slow[0]['query_label']
        slow_dur = top10_slow[0]['duration_s']
        insights['tpcds_insights'].append({
            'level': 'L2',
            'text': f"最耗时查询：{slow_label}（{slow_dur:.2f}s），超过平均耗时 {(slow_dur/avg if avg else 0):.1f}x",
            'source': 'analysis_results.tpcds_top10_slow[0]',
            'scenario': slow_label,
        })

    return analysis, insights


if __name__ == '__main__':
    import argparse, json, os
    ap = argparse.ArgumentParser()
    ap.add_argument('--extracted', required=True)
    ap.add_argument('--out-analysis', required=True)
    ap.add_argument('--out-insights', required=True)
    args = ap.parse_args()

    with open(args.extracted, encoding='utf-8') as f:
        extracted = json.load(f)
    a, i = analyze_tpcds(extracted)
    os.makedirs(os.path.dirname(args.out_analysis) or '.', exist_ok=True)
    with open(args.out_analysis, 'w', encoding='utf-8') as f:
        json.dump(a, f, ensure_ascii=False, indent=2)
    with open(args.out_insights, 'w', encoding='utf-8') as f:
        json.dump(i, f, ensure_ascii=False, indent=2)
    print(f'✅ TPC-DS analysis 已生成')
