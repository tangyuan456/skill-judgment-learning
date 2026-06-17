#!/usr/bin/env python3
"""
analyze.py — 按 report_type 分发到不同分析模块

输入：data/extracted_data.json + data/intent.json
输出：data/analysis_results.json + data/insights.json
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List

# ⚠️ 重要：本脚本与上游 tdsql-b-whitepaper/scripts/analyze.py 重名。
# 只把上游目录加入 path 是不够的（仍会先找到自己）。
# 上游 analyze.upstream_analyze / peak_for / scenario_records 用 _load_upstream_analyze() 懒加载。

_UPSTREAM_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 'tdsql-b-whitepaper', 'scripts'),
    os.path.join(os.getcwd(), 'tdsql-b-whitepaper', 'scripts'),
    os.path.join(os.getcwd(), '..', 'tdsql-b-whitepaper', 'scripts'),
]


def _load_upstream_analyze():
    """通过 importlib.util 从文件路径加载上游 analyze 模块（避免与本文件重名的循环）。"""
    import importlib.util
    for cand in _UPSTREAM_CANDIDATES:
        cand = os.path.abspath(cand)
        path = os.path.join(cand, 'analyze.py')
        if os.path.exists(path):
            if cand not in sys.path:
                sys.path.insert(0, cand)
            spec = importlib.util.spec_from_file_location('upstream_analyze_mod', path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.analyze, mod.peak_for, mod.scenario_records
    raise RuntimeError('未找到 tdsql-b-whitepaper/scripts/analyze.py')


def _load_scenario_cn():
    import importlib.util
    for cand in _UPSTREAM_CANDIDATES:
        cand = os.path.abspath(cand)
        path = os.path.join(cand, 'constants.py')
        if os.path.exists(path):
            if cand not in sys.path:
                sys.path.insert(0, cand)
            from constants import SCENARIO_CN  # type: ignore
            return SCENARIO_CN
    return {}


def analyze_iteration(extracted: Dict[str, Any], intent: Dict[str, Any]) -> Dict[str, Any]:
    """迭代报告的额外分析：版本演进趋势 + 累计变化 + 回归点。"""
    _, peak_for, _ = _load_upstream_analyze()
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
            if prev_peak:
                delta_pct = (peak['qps'] - prev_peak) / prev_peak * 100
                if delta_pct < -threshold:
                    regressions.append({
                        'version': v, 'scenario': s,
                        'peak_qps': peak['qps'], 'delta_pct': delta_pct,
                    })
            rows.append({
                'version': v, 'peak_qps': peak['qps'],
                'peak_threads': peak['threads'], 'p95_ms': peak['p95_ms'],
                'delta_pct': delta_pct,
            })
            prev_peak = peak['qps']
        trend[s] = rows
        if len(rows) >= 2 and rows[0]['peak_qps']:
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
        threads_min = 256  # 默认阈值
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
            'main_finding': f'高并发段平均 QPS={_fmt(buckets[0]["avg_qps"])}，'
                           f'中低并发段平均 QPS={_fmt(buckets[1]["avg_qps"])}',
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
        'main_finding': '已按产品分桶输出平均 QPS / P95，详见第 3 章。',
    }


def _avg(values):
    vs = [v for v in values if v is not None]
    return sum(vs) / len(vs) if vs else None


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
    data_kind = extracted.get('meta', {}).get('data_kind', 'sysbench_oltp')

    # TPC-DS 分支：走独立分析，跳过 sysbench 专用的 upstream_analyze
    if data_kind == 'tpcds_duration':
        from analyze_tpcds import analyze_tpcds
        results, insights = analyze_tpcds(extracted)
        results['report_type'] = report_type
        os.makedirs(os.path.dirname(args.out_analysis) or '.', exist_ok=True)
        with open(args.out_analysis, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        with open(args.out_insights, 'w', encoding='utf-8') as f:
            json.dump(insights, f, ensure_ascii=False, indent=2)
        print(f'\n=== CHECKPOINT③（TPC-DS duration, report_type={report_type}）===')
        print(f'✅ analysis_results.json 已保存: {args.out_analysis}')
        print(f'✅ insights.json 已保存: {args.out_insights}')
        return

    # 通用分析（single_product + product_compare 都生成；某些 report_type 用不到）
    upstream_analyze, _, _ = _load_upstream_analyze()
    SCENARIO_CN = _load_scenario_cn()
    results, insights = upstream_analyze(extracted)

    # 按 report_type 增补
    if report_type == 'iteration':
        results['iteration'] = analyze_iteration(extracted, intent)
        insights.setdefault('iteration_insights', [])
        # 加入 L1 累计变化结论
        for s, c in results['iteration']['cumulative_change'].items():
            insights['iteration_insights'].append({
                'level': 'L1',
                'text': f"{SCENARIO_CN.get(s, s)}：累计变化 {c:+.1f}%",
                'source': f'analysis_results.iteration.cumulative_change.{s}',
                'scenario': s,
            })
        # 回归点 L2
        for r in results['iteration']['regression_points']:
            insights['iteration_insights'].append({
                'level': 'L2',
                'text': f"回归：{r['version']} 在 {SCENARIO_CN.get(r['scenario'], r['scenario'])} 峰值下降 {abs(r['delta_pct']):.1f}%",
                'source': 'analysis_results.iteration.regression_points',
                'scenario': r['scenario'],
            })

    elif report_type == 'custom':
        results['custom'] = analyze_custom(extracted, intent)
        insights.setdefault('custom_insights', [])
        insights['custom_insights'].append({
            'level': 'L2',
            'text': results['custom'].get('main_finding', ''),
            'source': 'analysis_results.custom',
            'scenario': 'all',
        })

    results['report_type'] = report_type

    os.makedirs(os.path.dirname(args.out_analysis) or '.', exist_ok=True)
    with open(args.out_analysis, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    with open(args.out_insights, 'w', encoding='utf-8') as f:
        json.dump(insights, f, ensure_ascii=False, indent=2)

    # CHECKPOINT③
    print(f'\n=== CHECKPOINT③（report_type={report_type}）===')
    assert os.path.exists(args.out_analysis)
    assert os.path.exists(args.out_insights)
    if report_type == 'iteration':
        assert 'iteration' in results, '缺少 iteration 字段'
    if report_type == 'custom':
        assert 'custom' in results, '缺少 custom 字段'
    print(f'✅ analysis_results.json 已保存: {args.out_analysis}')
    print(f'✅ insights.json 已保存: {args.out_insights}')


if __name__ == '__main__':
    main()
