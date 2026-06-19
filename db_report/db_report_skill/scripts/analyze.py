#!/usr/bin/env python3
"""
analyze.py — 按 report_type 分发到不同分析模块（自包含版本）

输入：data/extracted_data.json + data/intent.json
输出：data/analysis_results.json + data/insights.json
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_core import analyze as core_analyze, peak_for, scenario_records  # noqa: E402


def analyze_iteration(extracted: Dict[str, Any], intent: Dict[str, Any]) -> Dict[str, Any]:
    """迭代报告的额外分析：版本演进趋势 + 累计变化 + 回归点。"""
    meta = extracted['meta']
    records = extracted['records']
    threshold = (intent.get('iteration_config') or {}).get('regression_threshold_pct', 5)
    versions = (intent.get('iteration_config') or {}).get('version_range') or meta['products']

    trend = {}
    cumulative = {}
    regressions = []
    for s in meta['scenarios']:
        rows = []
        prev_peak = None
        for v in versions:
            peak = peak_for(records, v, s)
            if not peak:
                continue
            delta_pct = None
            if prev_peak and prev_peak > 0:
                delta_pct = (peak['peak_qps'] - prev_peak) / prev_peak * 100
                if delta_pct < -threshold:
                    regressions.append({
                        'version': v, 'scenario': s,
                        'peak_qps': peak['peak_qps'], 'delta_pct': delta_pct,
                    })
            rows.append({
                'version': v, 'peak_qps': peak['peak_qps'],
                'peak_threads': peak['peak_threads'], 'p95_ms': peak.get('peak_p95_ms'),
                'delta_pct': delta_pct,
            })
            prev_peak = peak['peak_qps']
        trend[s] = rows
        if len(rows) >= 2 and rows[0]['peak_qps'] and rows[0]['peak_qps'] > 0:
            cumulative[s] = (rows[-1]['peak_qps'] - rows[0]['peak_qps']) / rows[0]['peak_qps'] * 100

    return {
        'version_order': versions,
        'trend': trend,
        'cumulative_change': cumulative,
        'regression_points': regressions,
        'regression_threshold_pct': threshold,
    }


def analyze_custom(extracted: Dict[str, Any], intent: Dict[str, Any]) -> Dict[str, Any]:
    """客制化分析：按 focus_dimension 分桶。"""
    custom_cfg = intent.get('custom_config') or {}
    focus = custom_cfg.get('focus_dimension')
    records = extracted['records']

    if focus == '高并发':
        threads_min = 256
        rkf = intent.get('results_key_filters') or {}
        if rkf.get('threads') and rkf['threads'].startswith('>'):
            try:
                threads_min = int(rkf['threads'].lstrip('>'))
            except ValueError:
                pass
        high = [r for r in records if r['threads'] >= threads_min]
        low = [r for r in records if r['threads'] < threads_min]
        buckets = [
            {'label': f'高并发 (≥{threads_min})',
             'avg_qps': _avg([r['qps'] for r in high]),
             'avg_p95_ms': _avg([r['p95_ms'] for r in high]),
             'sample_size': len(high)},
            {'label': f'中低并发 (<{threads_min})',
             'avg_qps': _avg([r['qps'] for r in low]),
             'avg_p95_ms': _avg([r['p95_ms'] for r in low]),
             'sample_size': len(low)},
        ]
        return {
            'focus_dimension': '高并发',
            'buckets': buckets,
            'main_finding': f'高并发段平均 QPS={_fmt(buckets[0]["avg_qps"])}，中低并发段平均 QPS={_fmt(buckets[1]["avg_qps"])}',
        }

    # 通用：按产品分桶
    buckets_by_product = defaultdict(list)
    for r in records:
        buckets_by_product[r['product']].append(r)
    buckets = [
        {'label': p,
         'avg_qps': _avg([r['qps'] for r in rs]),
         'avg_p95_ms': _avg([r['p95_ms'] for r in rs]),
         'sample_size': len(rs)}
        for p, rs in buckets_by_product.items()
    ]
    return {
        'focus_dimension': focus or '通用',
        'buckets': buckets,
        'main_finding': '已按产品分桶输出平均 QPS / P95，详见分析章节。',
    }


def _avg(values):
    vs = [v for v in values if v is not None]
    if not vs:
        return None
    return sum(vs) / len(vs)


def _fmt(v):
    return f'{v:,.0f}' if v is not None else '-'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--extracted', required=True)
    ap.add_argument('--intent', required=True)
    ap.add_argument('--out-analysis', required=True)
    ap.add_argument('--out-insights', required=True)
    args = ap.parse_args()

    with open(args.extracted, encoding='utf-8') as f:
        extracted = json.load(f)
    with open(args.intent, encoding='utf-8') as f:
        intent = json.load(f)

    report_type = intent.get('report_type', 'single')

    # 核心分析
    results, insights_list = core_analyze(extracted)

    # 按 report_type 增补
    if report_type == 'iteration':
        results['iteration'] = analyze_iteration(extracted, intent)
        iteration = results['iteration']
        insights_list.append({
            'level': 'L1',
            'text': f'共覆盖 {len(iteration.get("version_order", []))} 个版本的演进分析',
            'source': 'analysis_results.iteration',
            'scenario': 'all',
        })
        for r in iteration.get('regression_points', []):
            insights_list.append({
                'level': 'L2',
                'text': f'回归：{r["version"]} 在 {r["scenario"]} 场景峰值下降 {abs(r["delta_pct"]):.1f}%',
                'source': 'analysis_results.iteration.regression_points',
                'scenario': r['scenario'],
            })

    elif report_type == 'custom':
        results['custom'] = analyze_custom(extracted, intent)
        insights_list.append({
            'level': 'L2',
            'text': results['custom'].get('main_finding', ''),
            'source': 'analysis_results.custom',
            'scenario': 'all',
        })

    results['report_type'] = report_type
    insights = {'items': insights_list, 'report_type': report_type}

    os.makedirs(os.path.dirname(args.out_analysis) or '.', exist_ok=True)
    with open(args.out_analysis, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    with open(args.out_insights, 'w', encoding='utf-8') as f:
        json.dump(insights, f, ensure_ascii=False, indent=2)

    print(f'\n=== 分析完成（report_type={report_type}）===')
    print(f'analysis_results.json 已保存: {args.out_analysis}')
    print(f'insights.json 已保存: {args.out_insights}')
    print(f'洞察数量: {len(insights_list)}')


if __name__ == '__main__':
    main()
