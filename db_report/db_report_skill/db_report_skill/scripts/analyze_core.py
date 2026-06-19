#!/usr/bin/env python3
"""
analyze_core.py — 自包含分析逻辑，不依赖上游 skill。

提供：
  - analyze(): 主分析入口，返回 analysis_results + insights
  - peak_for(): 查找某产品某场景的峰值 QPS 记录
  - scenario_records(): 获取某产品某场景的所有记录
"""
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


def scenario_records(records: List[Dict], product: str, scenario: str) -> List[Dict]:
    """获取某产品某场景的所有记录，按 threads 排序。"""
    return sorted(
        [r for r in records if r['product'] == product and r['scenario'] == scenario],
        key=lambda r: r['threads'],
    )


def peak_for(records: List[Dict], product: str, scenario: str) -> Optional[Dict]:
    """查找某产品某场景的峰值 QPS 记录（含对应 threads 和 p95_ms）。"""
    srs = [r for r in records if r['product'] == product and r['scenario'] == scenario]
    if not srs:
        return None
    peak = max(srs, key=lambda r: r.get('qps', 0))
    return {
        'scenario': scenario,
        'peak_qps': peak['qps'],
        'peak_tps': peak.get('tps'),
        'peak_threads': peak['threads'],
        'peak_p95_ms': peak.get('p95_ms'),
    }


def _single_product_analysis(records: List[Dict], meta: Dict) -> Dict:
    """单产品分析：峰值汇总 + 并发扩展性。"""
    products = meta.get('products', [])
    scenarios = meta.get('scenarios', [])

    single = {}
    for p in products:
        peak_summary = []
        scalability = {}
        for s in scenarios:
            peak = peak_for(records, p, s)
            if peak:
                peak_summary.append(peak)

            srs = scenario_records(records, p, s)
            if srs:
                scalability[s] = {
                    'threads': [r['threads'] for r in srs],
                    'qps': [r['qps'] for r in srs],
                    'tps': [r.get('tps') for r in srs],
                    'p95_ms': [r.get('p95_ms') for r in srs],
                    'p99_ms': [r.get('p99_ms') for r in srs],
                }

        single[p] = {
            'peak_summary': peak_summary,
            'scalability': scalability,
        }

    return single


def _product_compare_analysis(records: List[Dict], meta: Dict) -> Dict:
    """多产品对比分析。"""
    products = meta.get('products', [])
    scenarios = meta.get('scenarios', [])

    # 公平性检查
    fairness = _check_fairness(records, meta)

    compare = {}
    for p in products:
        peak_summary = []
        for s in scenarios:
            peak = peak_for(records, p, s)
            if peak:
                peak_summary.append(peak)
        compare[p] = {'peak_summary': peak_summary}

    # 性能比值矩阵（以第一个产品为 baseline）
    baseline = products[0] if products else None
    ratio_matrix = {}
    if baseline and len(products) >= 2:
        for s in scenarios:
            base_peak = peak_for(records, baseline, s)
            if not base_peak:
                continue
            base_qps = base_peak['peak_qps']
            if not base_qps:
                continue
            row = {baseline: 1.0}
            for p in products[1:]:
                peak = peak_for(records, p, s)
                if peak and peak['peak_qps']:
                    row[p] = peak['peak_qps'] / base_qps
            ratio_matrix[s] = row

    return {
        'products': products,
        'scenarios': scenarios,
        'single_product': compare,
        'ratio_matrix': ratio_matrix,
        'fairness': fairness,
    }


def _check_fairness(records: List[Dict], meta: Dict) -> Dict:
    """公平性检查：并发档、场景覆盖是否一致。"""
    products = meta.get('products', [])
    if len(products) < 2:
        return {'passed': True, 'issues': []}

    issues = []

    # 检查并发档
    conc_by_product = {}
    for p in products:
        threads = sorted({r['threads'] for r in records if r['product'] == p})
        conc_by_product[p] = threads

    ref = conc_by_product[products[0]]
    for p in products[1:]:
        if conc_by_product[p] != ref:
            issues.append(f'并发档不一致：{products[0]}={ref} vs {p}={conc_by_product[p]}')

    # 检查场景覆盖
    scen_by_product = {}
    for p in products:
        scenarios = sorted({r['scenario'] for r in records if r['product'] == p})
        scen_by_product[p] = scenarios

    ref_scen = scen_by_product[products[0]]
    for p in products[1:]:
        if scen_by_product[p] != ref_scen:
            issues.append(f'场景覆盖不一致：{products[0]}={ref_scen} vs {p}={scen_by_product[p]}')

    return {
        'passed': len(issues) == 0,
        'issues': issues,
        'concurrencies': conc_by_product,
        'scenarios': scen_by_product,
    }


def _generate_insights(analysis: Dict, report_type: str) -> List[Dict]:
    """从分析结果生成分级洞察（L1/L2）。"""
    insights: List[Dict] = []
    single = analysis.get('single_product', {})

    for product, data in single.items():
        peak_summary = data.get('peak_summary', [])
        if not peak_summary:
            continue

        # L1: 峰值 QPS 最高/最低场景
        max_ps = max(peak_summary, key=lambda x: x['peak_qps'])
        min_ps = min(peak_summary, key=lambda x: x['peak_qps'])
        insights.append({
            'level': 'L1',
            'text': f'{product} 峰值 QPS 最高出现在 {max_ps["scenario"]}（{max_ps["peak_qps"]:,.0f} @ {max_ps["peak_threads"]} 并发）',
            'source': f'single_product.{product}.peak_summary',
            'scenario': max_ps['scenario'],
        })
        insights.append({
            'level': 'L1',
            'text': f'{product} 峰值 QPS 最低出现在 {min_ps["scenario"]}（{min_ps["peak_qps"]:,.0f} @ {min_ps["peak_threads"]} 并发）',
            'source': f'single_product.{product}.peak_summary',
            'scenario': min_ps['scenario'],
        })

        # L1: 并发扩展性
        scalability = data.get('scalability', {})
        for s, sc in scalability.items():
            if len(sc['qps']) >= 2:
                growth = (sc['qps'][-1] - sc['qps'][0]) / sc['qps'][0] * 100
                insights.append({
                    'level': 'L1',
                    'text': f'{s} 并发扩展率 {growth:+.1f}%（{sc["threads"][0]}→{sc["threads"][-1]} threads）',
                    'source': f'single_product.{product}.scalability.{s}',
                    'scenario': s,
                })

    # 对比报告额外洞察
    if report_type == 'comparison' and 'ratio_matrix' in analysis:
        ratio = analysis['ratio_matrix']
        for s, row in ratio.items():
            products = list(row.keys())
            if len(products) >= 2:
                winner = max(row, key=row.get)
                loser = min(row, key=row.get)
                if row[winner] > 1.01:
                    insights.append({
                        'level': 'L1',
                        'text': f'{s}：{winner} 比 {loser} 快 {row[winner]-1:.1%}',
                        'source': f'ratio_matrix.{s}',
                        'scenario': s,
                    })

        fairness = analysis.get('fairness', {})
        if not fairness.get('passed'):
            for issue in fairness.get('issues', []):
                insights.append({
                    'level': 'L2',
                    'text': f'⚠️ 公平性警告：{issue}',
                    'source': 'fairness',
                    'scenario': 'all',
                })

    return insights


def analyze(extracted: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    主分析入口。

    返回 (analysis_results, insights)。
    """
    meta = extracted.get('meta', {})
    records = extracted.get('records', [])

    if not records:
        return {'single_product': {}, 'error': '无数据'}, []

    single = _single_product_analysis(records, meta)
    compare = _product_compare_analysis(records, meta)

    results = {
        'single_product': single,
        'product_compare': compare,
    }

    insights = _generate_insights(results, 'single')

    return results, insights
