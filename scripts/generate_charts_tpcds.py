#!/usr/bin/env python3
"""TPC-DS 单次报告图表生成。"""
from __future__ import annotations
import os

import matplotlib
matplotlib.rcParams['font.sans-serif'] = [
    'PingFang SC', 'Hiragino Sans GB', 'Arial Unicode MS',
    'Microsoft YaHei', 'SimHei', 'WenQuanYi Zen Hei', 'Source Han Sans CN',
    'Noto Sans CJK SC', 'DejaVu Sans',
]
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['figure.dpi'] = 120
matplotlib.rcParams['savefig.dpi'] = 180
matplotlib.rcParams['savefig.bbox'] = 'tight'
import matplotlib.pyplot as plt  # noqa: E402


def _q_num(label: str) -> int:
    if label.startswith('Q'):
        try: return int(label[1:])
        except ValueError: return 9999
    return 9999


def gen_tpcds_charts(extracted, analysis, charts_dir: str):
    os.makedirs(charts_dir, exist_ok=True)
    main_product = analysis.get('main_product', '')
    full = analysis.get('tpcds_full_table', [])
    top10_slow = analysis.get('tpcds_top10_slow', [])
    stats = analysis.get('tpcds_stats', {})

    # 图 1：全量查询耗时柱状图（按 Q 编号排序）
    by_q = sorted([x for x in full if x['query_label'].startswith('Q')], key=lambda x: _q_num(x['query_label']))
    labels = [x['query_label'] for x in by_q]
    durs = [x['duration_s'] for x in by_q]
    fig, ax = plt.subplots(figsize=(max(14, len(labels) * 0.18), 6))
    colors = ['#d62728' if d >= stats.get('p95_duration_s', 0) else '#1f77b4' for d in durs]
    ax.bar(labels, durs, color=colors, edgecolor='white', linewidth=0.3)
    ax.set_title(f'{main_product} TPC-DS 全量 {len(labels)} 查询耗时（红色=超过 P95）', fontsize=14, fontweight='bold')
    ax.set_xlabel('查询编号'); ax.set_ylabel('耗时 (s)')
    ax.grid(True, alpha=0.3, axis='y', linestyle='--')
    plt.xticks(rotation=90, fontsize=7)
    plt.tight_layout()
    plt.savefig(os.path.join(charts_dir, 'tpcds_all_queries.png'))
    plt.close()

    # 图 2：Top 10 最慢查询
    if top10_slow:
        lbl = [x['query_label'] for x in top10_slow]
        dur = [x['duration_s'] for x in top10_slow]
        fig, ax = plt.subplots(figsize=(9, 5.5))
        bars = ax.barh(lbl[::-1], dur[::-1], color='#d62728')
        for i, (b, v) in enumerate(zip(bars, dur[::-1])):
            ax.text(b.get_width(), b.get_y() + b.get_height() / 2,
                    f' {v:.2f}s', va='center', fontsize=10, fontweight='bold')
        ax.set_title(f'{main_product} TPC-DS Top 10 最慢查询', fontsize=14, fontweight='bold')
        ax.set_xlabel('耗时 (s)'); ax.grid(True, alpha=0.3, axis='x', linestyle='--')
        plt.tight_layout()
        plt.savefig(os.path.join(charts_dir, 'tpcds_top10_slow.png'))
        plt.close()

    # 图 3：耗时分布直方图
    all_durs = [x['duration_s'] for x in full]
    if all_durs:
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.hist(all_durs, bins=20, color='#1f77b4', edgecolor='white')
        for key, label, color in [('avg_duration_s', '平均', '#2ca02c'),
                                  ('median_duration_s', '中位数', '#ff7f0e'),
                                  ('p95_duration_s', 'P95', '#d62728')]:
            v = stats.get(key)
            if v:
                ax.axvline(v, color=color, linewidth=1.8, linestyle='--', label=f'{label}={v:.2f}s')
        ax.set_title(f'{main_product} TPC-DS 查询耗时分布', fontsize=14, fontweight='bold')
        ax.set_xlabel('耗时 (s)'); ax.set_ylabel('查询数')
        ax.legend(); ax.grid(True, alpha=0.3, linestyle='--')
        plt.tight_layout()
        plt.savefig(os.path.join(charts_dir, 'tpcds_duration_dist.png'))
        plt.close()


if __name__ == '__main__':
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument('--extracted', required=True)
    ap.add_argument('--analysis', required=True)
    ap.add_argument('--charts-dir', required=True)
    args = ap.parse_args()
    with open(args.extracted, encoding='utf-8') as f:
        extracted = json.load(f)
    with open(args.analysis, encoding='utf-8') as f:
        analysis = json.load(f)
    gen_tpcds_charts(extracted, analysis, args.charts_dir)
    print(f'✅ TPC-DS 图表已生成: {args.charts_dir}')
