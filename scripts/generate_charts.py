#!/usr/bin/env python3
"""
generate_charts.py — 按 report_type 生成图表

- comparison: 复用上游 generate_charts.py（产生 P0+P1 全套）
- single:     5 场景 QPS / P95 曲线 + 1 张峰值汇总
- iteration:  5 场景趋势线 + 累计变化柱状图 + 回归散点
- custom:     主图 + 对比图（≥3 张）
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 动态寻找上游 tdsql-b-whitepaper/scripts
_UPSTREAM_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 'tdsql-b-whitepaper', 'scripts'),
    os.path.join(os.getcwd(), 'tdsql-b-whitepaper', 'scripts'),
    os.path.join(os.getcwd(), '..', 'tdsql-b-whitepaper', 'scripts'),
]
for _c in _UPSTREAM_CANDIDATES:
    _c = os.path.abspath(_c)
    if os.path.exists(os.path.join(_c, 'constants.py')):
        if _c not in sys.path:
            sys.path.insert(0, _c)
        break

try:
    from constants import SCENARIO_CN, SCENARIO_COLORS, PRODUCT_COLORS, MATPLOTLIB_CN_FONTS  # noqa: E402
except ImportError:
    # 上游 constants 不可用时，使用兜底常量（TPC-DS 路径下不需要这些）
    SCENARIO_CN = {}
    SCENARIO_COLORS = {}
    PRODUCT_COLORS = {}
    MATPLOTLIB_CN_FONTS = ['PingFang SC', 'Hiragino Sans GB', 'Arial Unicode MS',
                           'Microsoft YaHei', 'SimHei', 'DejaVu Sans']

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
    peak_summary = analysis['single_product'][main_product]['peak_summary']
    labels = [SCENARIO_CN.get(p['scenario'], p['scenario']) for p in peak_summary]
    values = [p['peak_qps'] for p in peak_summary]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    bars = ax.bar(labels, values, color=[SCENARIO_COLORS.get(p['scenario'], '#888') for p in peak_summary])
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width()/2, b.get_height(),
                f'{v:,.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    ax.set_title(f'{main_product} 5 场景峰值 QPS 汇总', fontsize=14, fontweight='bold')
    ax.set_ylabel('峰值 QPS'); ax.grid(True, alpha=0.3, axis='y', linestyle='--')
    plt.tight_layout()
    plt.savefig(os.path.join(charts_dir, 'single_peak_summary.png'))
    plt.close()


# ============== iteration ==============
def gen_iteration(extracted, analysis, charts_dir):
    iteration = analysis.get('iteration') or {}
    versions = iteration.get('version_order') or extracted['meta']['products']
    trend = iteration.get('trend', {})
    cumulative = iteration.get('cumulative_change', {})
    regressions = iteration.get('regression_points', [])
    scenarios = extracted['meta']['scenarios']

    # 5 场景演进趋势
    for s in scenarios:
        rows = trend.get(s, [])
        if not rows:
            continue
        labels = [r['version'] for r in rows]
        qps = [r['peak_qps'] for r in rows]
        p95 = [r.get('p95_ms') for r in rows]

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

        if any(p is not None for p in p95):
            fig, ax = plt.subplots(figsize=(9, 5))
            ax.plot(labels, p95, marker='s', linewidth=2.4, markersize=8,
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
        ax.set_title('5 场景累计变化（首版 → 末版）', fontsize=14, fontweight='bold')
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
            ax.annotate(SCENARIO_CN.get(r['scenario'], r['scenario']),
                        xy=(r['version'], r['delta_pct']),
                        xytext=(5, 5), textcoords='offset points', fontsize=9)
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

    # 主图：focus_dimension 与 QPS
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(labels, qps_vals, color='#1f77b4')
    for b, v in zip(bars, qps_vals):
        ax.text(b.get_x() + b.get_width()/2, b.get_height(),
                f'{v:,.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    ax.set_title(f'{custom.get("focus_dimension", "")} 维度与平均 QPS',
                 fontsize=14, fontweight='bold')
    ax.set_ylabel('平均 QPS'); ax.grid(True, alpha=0.3, axis='y', linestyle='--')
    plt.tight_layout()
    plt.savefig(os.path.join(charts_dir, 'custom_main.png'))
    plt.close()

    # 对比图：QPS vs P95
    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax2 = ax1.twinx()
    ax1.bar(labels, qps_vals, color='#1f77b4', alpha=0.7, label='平均 QPS')
    ax2.plot(labels, p95_vals, color='#d62728', marker='o', linewidth=2.4, label='平均 P95 (ms)')
    ax1.set_ylabel('平均 QPS', color='#1f77b4')
    ax2.set_ylabel('平均 P95 (ms)', color='#d62728')
    ax1.set_title(f'{custom.get("focus_dimension", "")} QPS vs P95 对比',
                  fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y', linestyle='--')
    plt.tight_layout()
    plt.savefig(os.path.join(charts_dir, 'custom_compare.png'))
    plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--extracted', required=True)
    ap.add_argument('--analysis', required=True)
    ap.add_argument('--charts-dir', required=True)
    ap.add_argument('--report-type', required=True,
                    choices=['single', 'comparison', 'iteration', 'custom'])
    args = ap.parse_args()

    with open(args.extracted, encoding='utf-8') as f:
        extracted = json.load(f)
    with open(args.analysis, encoding='utf-8') as f:
        analysis = json.load(f)
    os.makedirs(args.charts_dir, exist_ok=True)

    # TPC-DS 分支
    data_kind = extracted.get('meta', {}).get('data_kind', 'sysbench_oltp')
    if data_kind == 'tpcds_duration':
        from generate_charts_tpcds import gen_tpcds_charts
        gen_tpcds_charts(extracted, analysis, args.charts_dir)
        pngs = sorted([f for f in os.listdir(args.charts_dir) if f.endswith('.png')])
        print(f'\n✅ 生成 {len(pngs)} 张 TPC-DS 图表')
        for p in pngs:
            print(f'   - {p}')
        return

    if args.report_type == 'comparison':
        # 复用上游
        from generate_charts import (
            plot_peak_qps_compare, plot_concurrency_qps_compare, plot_concurrency_p95_compare,
            plot_radar, plot_ladder, plot_single_product_all,
        )
        for s in extracted['meta']['scenarios']:
            plot_peak_qps_compare(analysis, s, os.path.join(args.charts_dir, f'p0_peak_qps_compare_{s}.png'))
            plot_concurrency_qps_compare(extracted, analysis, s,
                                         os.path.join(args.charts_dir, f'p0_concurrency_qps_compare_{s}.png'))
            plot_concurrency_p95_compare(extracted, analysis, s,
                                         os.path.join(args.charts_dir, f'p0_concurrency_p95_compare_{s}.png'))
        plot_radar(analysis, os.path.join(args.charts_dir, 'p0_radar_summary.png'))
        plot_ladder(analysis, os.path.join(args.charts_dir, 'p1_ladder_summary.png'))
        for p in extracted['meta']['products']:
            plot_single_product_all(extracted, p,
                                    os.path.join(args.charts_dir, f'p1_single_product_{safe_name(p)}.png'))
    elif args.report_type == 'single':
        gen_single(extracted, analysis, args.charts_dir)
    elif args.report_type == 'iteration':
        gen_iteration(extracted, analysis, args.charts_dir)
    elif args.report_type == 'custom':
        gen_custom(extracted, analysis, args.charts_dir)

    pngs = sorted([f for f in os.listdir(args.charts_dir) if f.endswith('.png')])
    print(f'\n✅ 生成 {len(pngs)} 张图表（report_type={args.report_type}）')
    for p in pngs:
        print(f'   - {p}')


if __name__ == '__main__':
    main()
