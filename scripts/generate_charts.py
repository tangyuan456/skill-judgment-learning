#!/usr/bin/env python3
"""
generate_charts.py — 按 report_type 生成图表（自包含版本）
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from constants import SCENARIO_CN, SCENARIO_COLORS, PRODUCT_COLORS, MATPLOTLIB_CN_FONTS  # noqa: E402

import matplotlib
matplotlib.rcParams['font.sans-serif'] = MATPLOTLIB_CN_FONTS
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['figure.dpi'] = 120
matplotlib.rcParams['savefig.dpi'] = 180
matplotlib.rcParams['savefig.bbox'] = 'tight'
import matplotlib.pyplot as plt  # noqa: E402


def safe_name(s):
    return re.sub(r'[^a-zA-Z0-9_-]', '_', s)


# ============== single ==============
def gen_single(extracted, analysis, charts_dir):
    records = extracted['records']
    scenarios = extracted['meta']['scenarios']
    main_product = extracted['meta']['products'][0]

    for s in scenarios:
        rows = sorted([r for r in records if r['product'] == main_product and r['scenario'] == s],
                      key=lambda r: r['threads'])
        if not rows:
            continue
        ts = [r['threads'] for r in rows]
        # QPS 曲线
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(ts, [r['qps'] for r in rows], marker='o', linewidth=2.2, markersize=8,
                color=SCENARIO_COLORS.get(s, '#1f77b4'))
        ax.set_xscale('log', base=2)
        ax.set_xticks(ts); ax.set_xticklabels([str(t) for t in ts])
        ax.set_title(f'{SCENARIO_CN.get(s, s)} 并发-QPS 曲线', fontsize=14, fontweight='bold')
        ax.set_xlabel('并发数（threads）'); ax.set_ylabel('QPS')
        ax.grid(True, alpha=0.3, linestyle='--')
        plt.tight_layout()
        plt.savefig(os.path.join(charts_dir, f'single_qps_{s}.png'))
        plt.close()

        # P95 曲线
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(ts, [r['p95_ms'] for r in rows], marker='s', linewidth=2.2, markersize=7,
                color=SCENARIO_COLORS.get(s, '#1f77b4'))
        ax.set_xscale('log', base=2)
        ax.set_xticks(ts); ax.set_xticklabels([str(t) for t in ts])
        ax.set_title(f'{SCENARIO_CN.get(s, s)} 并发-P95 曲线', fontsize=14, fontweight='bold')
        ax.set_xlabel('并发数（threads）'); ax.set_ylabel('P95 (ms)')
        ax.grid(True, alpha=0.3, linestyle='--')
        plt.tight_layout()
        plt.savefig(os.path.join(charts_dir, f'single_p95_{s}.png'))
        plt.close()

    # 峰值汇总
    sp = analysis.get('single_product', {}).get(main_product, {})
    peak_summary = sp.get('peak_summary', [])
    if peak_summary:
        labels = [SCENARIO_CN.get(p['scenario'], p['scenario']) for p in peak_summary]
        values = [p['peak_qps'] for p in peak_summary]
        fig, ax = plt.subplots(figsize=(9, 5.5))
        bars = ax.bar(labels, values, color=[SCENARIO_COLORS.get(p['scenario'], '#888') for p in peak_summary])
        for b, v in zip(bars, values):
            ax.text(b.get_x() + b.get_width()/2, b.get_height(),
                    f'{v:,.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
        ax.set_title(f'{main_product} 场景峰值 QPS 汇总', fontsize=14, fontweight='bold')
        ax.set_ylabel('峰值 QPS'); ax.grid(True, alpha=0.3, axis='y', linestyle='--')
        plt.tight_layout()
        plt.savefig(os.path.join(charts_dir, 'single_peak_summary.png'))
        plt.close()


# ============== comparison ==============
def _peak_for_product(analysis, product, scenario):
    sp = analysis.get('single_product', {}).get(product, {})
    for p in sp.get('peak_summary', []):
        if p['scenario'] == scenario:
            return p
    return None


def gen_comparison(extracted, analysis, charts_dir):
    records = extracted['records']
    scenarios = extracted['meta']['scenarios']
    products = extracted['meta']['products']

    for s in scenarios:
        # 峰值对比
        fig, ax = plt.subplots(figsize=(9, 5.5))
        labels = []
        values = []
        colors = []
        for i, p in enumerate(products):
            peak = _peak_for_product(analysis, p, s)
            if peak:
                labels.append(p)
                values.append(peak['peak_qps'])
                colors.append(PRODUCT_COLORS[i % len(PRODUCT_COLORS)])
        if labels:
            bars = ax.bar(labels, values, color=colors)
            for b, v in zip(bars, values):
                ax.text(b.get_x() + b.get_width()/2, b.get_height(),
                        f'{v:,.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
            ax.set_title(f'{SCENARIO_CN.get(s, s)} 峰值 QPS 对比', fontsize=14, fontweight='bold')
            ax.set_ylabel('峰值 QPS'); ax.grid(True, alpha=0.3, axis='y', linestyle='--')
            plt.tight_layout()
            plt.savefig(os.path.join(charts_dir, f'comparison_peak_{s}.png'))
            plt.close()

        # 并发-QPS 曲线对比
        fig, ax = plt.subplots(figsize=(9, 5.5))
        for i, p in enumerate(products):
            rows = sorted([r for r in records if r['product'] == p and r['scenario'] == s],
                          key=lambda r: r['threads'])
            if rows:
                ts = [r['threads'] for r in rows]
                qs = [r['qps'] for r in rows]
                ax.plot(ts, qs, marker='o', linewidth=2, markersize=7,
                        color=PRODUCT_COLORS[i % len(PRODUCT_COLORS)], label=p)
        ax.set_xscale('log', base=2)
        ax.set_title(f'{SCENARIO_CN.get(s, s)} 并发-QPS 对比', fontsize=14, fontweight='bold')
        ax.set_xlabel('并发数（threads）'); ax.set_ylabel('QPS')
        ax.legend(); ax.grid(True, alpha=0.3, linestyle='--')
        plt.tight_layout()
        plt.savefig(os.path.join(charts_dir, f'comparison_qps_{s}.png'))
        plt.close()

        # 并发-P95 对比
        fig, ax = plt.subplots(figsize=(9, 5.5))
        for i, p in enumerate(products):
            rows = sorted([r for r in records if r['product'] == p and r['scenario'] == s],
                          key=lambda r: r['threads'])
            if rows:
                ts = [r['threads'] for r in rows]
                ps = [r['p95_ms'] for r in rows]
                ax.plot(ts, ps, marker='s', linewidth=2, markersize=6,
                        color=PRODUCT_COLORS[i % len(PRODUCT_COLORS)], label=p)
        ax.set_xscale('log', base=2)
        ax.set_title(f'{SCENARIO_CN.get(s, s)} 并发-P95 对比', fontsize=14, fontweight='bold')
        ax.set_xlabel('并发数（threads）'); ax.set_ylabel('P95 (ms)')
        ax.legend(); ax.grid(True, alpha=0.3, linestyle='--')
        plt.tight_layout()
        plt.savefig(os.path.join(charts_dir, f'comparison_p95_{s}.png'))
        plt.close()

    # 雷达图
    if len(products) >= 2:
        _gen_radar(analysis, products, scenarios, charts_dir)

    # 天梯图
    _gen_ladder(analysis, products, scenarios, charts_dir)


def _gen_radar(analysis, products, scenarios, charts_dir):
    import numpy as np
    labels = [SCENARIO_CN.get(s, s) for s in scenarios]
    n = len(labels)
    if n < 3:
        return

    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    for i, p in enumerate(products):
        values = []
        for s in scenarios:
            peak = _peak_for_product(analysis, p, s)
            values.append(peak['peak_qps'] if peak else 0)
        # 归一化到最大值的百分比
        max_val = max(values) if max(values) > 0 else 1
        pct = [v / max_val * 100 for v in values]
        pct += pct[:1]
        ax.fill(angles, pct, alpha=0.15, color=PRODUCT_COLORS[i % len(PRODUCT_COLORS)])
        ax.plot(angles, pct, 'o-', linewidth=2, color=PRODUCT_COLORS[i % len(PRODUCT_COLORS)], label=p)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_title('场景峰值 QPS 雷达图（归一化）', fontsize=14, fontweight='bold', pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
    plt.tight_layout()
    plt.savefig(os.path.join(charts_dir, 'comparison_radar.png'))
    plt.close()


def _gen_ladder(analysis, products, scenarios, charts_dir):
    fig, ax = plt.subplots(figsize=(max(8, len(products) * 2), 6))
    x = list(range(len(scenarios)))
    width = 0.8 / len(products)
    for i, p in enumerate(products):
        values = []
        for s in scenarios:
            peak = _peak_for_product(analysis, p, s)
            values.append(peak['peak_qps'] if peak and peak['peak_qps'] else 0)
        offset = (i - len(products)/2 + 0.5) * width
        ax.bar([xi + offset for xi in x], values, width, color=PRODUCT_COLORS[i % len(PRODUCT_COLORS)], label=p)
    ax.set_xticks(x)
    ax.set_xticklabels([SCENARIO_CN.get(s, s) for s in scenarios])
    ax.set_title('各场景峰值 QPS 天梯对比', fontsize=14, fontweight='bold')
    ax.set_ylabel('峰值 QPS'); ax.legend(); ax.grid(True, alpha=0.3, axis='y', linestyle='--')
    plt.tight_layout()
    plt.savefig(os.path.join(charts_dir, 'comparison_ladder.png'))
    plt.close()


# ============== iteration ==============
def gen_iteration(extracted, analysis, charts_dir):
    iteration = analysis.get('iteration') or {}
    versions = iteration.get('version_order') or extracted['meta']['products']
    trend = iteration.get('trend', {})
    cumulative = iteration.get('cumulative_change', {})
    regressions = iteration.get('regression_points', [])
    scenarios = extracted['meta']['scenarios']

    for s in scenarios:
        rows = trend.get(s, [])
        if not rows:
            continue
        labels = [r['version'] for r in rows]
        qps = [r['peak_qps'] for r in rows]
        p95_vals = [r.get('p95_ms') for r in rows]

        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(labels, qps, marker='o', linewidth=2.4, markersize=10,
                color=SCENARIO_COLORS.get(s, '#1f77b4'))
        for i, v in enumerate(qps):
            ax.text(i, v, f'{v:,.0f}', ha='center', va='bottom', fontsize=9)
        ax.set_title(f'{SCENARIO_CN.get(s, s)} 峰值 QPS 演进', fontsize=14, fontweight='bold')
        ax.set_xlabel('版本'); ax.set_ylabel('峰值 QPS')
        ax.grid(True, alpha=0.3, linestyle='--')
        plt.xticks(rotation=15)
        plt.tight_layout()
        plt.savefig(os.path.join(charts_dir, f'iter_trend_qps_{s}.png'))
        plt.close()

        if any(p is not None for p in p95_vals):
            fig, ax = plt.subplots(figsize=(9, 5))
            ax.plot(labels, p95_vals, marker='s', linewidth=2.4, markersize=8,
                    color=SCENARIO_COLORS.get(s, '#d62728'))
            ax.set_title(f'{SCENARIO_CN.get(s, s)} P95 延迟演进', fontsize=14, fontweight='bold')
            ax.set_xlabel('版本'); ax.set_ylabel('P95 (ms)')
            ax.grid(True, alpha=0.3, linestyle='--')
            plt.xticks(rotation=15)
            plt.tight_layout()
            plt.savefig(os.path.join(charts_dir, f'iter_trend_p95_{s}.png'))
            plt.close()

    # 累计变化柱状图
    if cumulative:
        labels = [SCENARIO_CN.get(s, s) for s in cumulative.keys()]
        vals = list(cumulative.values())
        colors = ['#2ca02c' if v > 0 else '#d62728' for v in vals]
        fig, ax = plt.subplots(figsize=(9, 5))
        bars = ax.bar(labels, vals, color=colors)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width()/2, b.get_height(),
                    f'{v:+.1f}%', ha='center',
                    va='bottom' if v > 0 else 'top', fontsize=10, fontweight='bold')
        ax.axhline(0, color='black', linewidth=0.8)
        ax.set_title('场景累计变化（首版 → 末版）', fontsize=14, fontweight='bold')
        ax.set_ylabel('累计变化 %'); ax.grid(True, alpha=0.3, axis='y', linestyle='--')
        plt.tight_layout()
        plt.savefig(os.path.join(charts_dir, 'iter_cumulative.png'))
        plt.close()

    # 回归点散点图
    if regressions:
        fig, ax = plt.subplots(figsize=(9, 5))
        for r in regressions:
            ax.scatter(r['version'], r['delta_pct'], s=120,
                       color='#d62728', edgecolors='white', linewidth=1.5)
        ax.axhline(0, color='black', linewidth=0.5)
        ax.set_title('回归点散点图', fontsize=14, fontweight='bold')
        ax.set_xlabel('版本'); ax.set_ylabel('相对前版本变化 %')
        ax.grid(True, alpha=0.3, linestyle='--')
        plt.xticks(rotation=15)
        plt.tight_layout()
        plt.savefig(os.path.join(charts_dir, 'iter_regression.png'))
        plt.close()


# ============== custom ==============
def gen_custom(extracted, analysis, charts_dir):
    custom = analysis.get('custom') or {}
    buckets = custom.get('buckets') or []
    if not buckets:
        return

    labels = [b.get('label', '-') for b in buckets]
    qps_vals = [b.get('avg_qps') or 0 for b in buckets]
    p95_vals = [b.get('avg_p95_ms') or 0 for b in buckets]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(labels, qps_vals, color='#1f77b4')
    for b, v in zip(bars, qps_vals):
        ax.text(b.get_x() + b.get_width()/2, b.get_height(),
                f'{v:,.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    ax.set_title(f'{custom.get("focus_dimension", "")} 维度与平均 QPS', fontsize=14, fontweight='bold')
    ax.set_ylabel('平均 QPS'); ax.grid(True, alpha=0.3, axis='y', linestyle='--')
    plt.tight_layout()
    plt.savefig(os.path.join(charts_dir, 'custom_main.png'))
    plt.close()

    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax2 = ax1.twinx()
    ax1.bar(labels, qps_vals, color='#1f77b4', alpha=0.7, label='平均 QPS')
    ax2.plot(labels, p95_vals, color='#d62728', marker='o', linewidth=2.4, label='平均 P95 (ms)')
    ax1.set_ylabel('平均 QPS', color='#1f77b4')
    ax2.set_ylabel('平均 P95 (ms)', color='#d62728')
    ax1.set_title(f'{custom.get("focus_dimension", "")} QPS vs P95 对比', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y', linestyle='--')
    plt.tight_layout()
    plt.savefig(os.path.join(charts_dir, 'custom_compare.png'))
    plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--extracted', required=True)
    ap.add_argument('--analysis', required=True)
    ap.add_argument('--charts-dir', required=True)
    ap.add_argument('--report-type', required=True, choices=['single', 'comparison', 'iteration', 'custom'])
    args = ap.parse_args()

    with open(args.extracted, encoding='utf-8') as f:
        extracted = json.load(f)
    with open(args.analysis, encoding='utf-8') as f:
        analysis = json.load(f)
    os.makedirs(args.charts_dir, exist_ok=True)

    if args.report_type == 'comparison':
        gen_comparison(extracted, analysis, args.charts_dir)
    elif args.report_type == 'single':
        gen_single(extracted, analysis, args.charts_dir)
    elif args.report_type == 'iteration':
        gen_iteration(extracted, analysis, args.charts_dir)
    elif args.report_type == 'custom':
        gen_custom(extracted, analysis, args.charts_dir)

    pngs = sorted([f for f in os.listdir(args.charts_dir) if f.endswith('.png')])
    print(f'\n生成 {len(pngs)} 张图表（report_type={args.report_type}）')
    for p in pngs:
        print(f'   - {p}')


if __name__ == '__main__':
    main()
