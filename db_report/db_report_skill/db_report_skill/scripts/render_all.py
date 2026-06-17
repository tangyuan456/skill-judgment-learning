#!/usr/bin/env python3
"""
render_all.py — 按 report_type 生成 md/docx/html 三格式

复用上游 render_md / render_docx / render_html 渲染器，
模板由 templates/{type}_report.py 提供。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 上游脚本（render_md/docx/html、constants）动态寻找
_UPSTREAM_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 'tdsql-b-whitepaper', 'scripts'),
    os.path.join(os.getcwd(), 'tdsql-b-whitepaper', 'scripts'),
    os.path.join(os.getcwd(), '..', 'tdsql-b-whitepaper', 'scripts'),
]
for _cand in _UPSTREAM_CANDIDATES:
    _cand = os.path.abspath(_cand)
    if os.path.exists(os.path.join(_cand, 'render_md.py')):
        if _cand not in sys.path:
            sys.path.insert(0, _cand)
        break
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from render_md import render_md  # noqa: E402  (来自上游)
from render_html import render_html  # noqa: E402
from render_docx import render_docx  # noqa: E402

from templates.single_report import build_single_report_data  # noqa: E402
from templates.comparison_report import build_comparison_report_data  # noqa: E402
from templates.iteration_report import build_iteration_report_data  # noqa: E402
from templates.custom_report import build_custom_report_data  # noqa: E402
from templates.tpcds_single_report import build_tpcds_single_report_data  # noqa: E402


BUILDERS = {
    'single': build_single_report_data,
    'comparison': build_comparison_report_data,
    'iteration': build_iteration_report_data,
    'custom': build_custom_report_data,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--extracted', required=True)
    ap.add_argument('--analysis', required=True)
    ap.add_argument('--insights', required=True)
    ap.add_argument('--intent', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--charts-dir-rel', default='charts')
    args = ap.parse_args()

    extracted = json.load(open(args.extracted, encoding='utf-8'))
    analysis = json.load(open(args.analysis, encoding='utf-8'))
    insights = json.load(open(args.insights, encoding='utf-8'))
    intent = json.load(open(args.intent, encoding='utf-8'))

    rt = intent.get('report_type', 'single')
    data_kind = extracted.get('meta', {}).get('data_kind', 'sysbench_oltp')

    # TPC-DS 数据只支持 single 模板
    if data_kind == 'tpcds_duration' and rt == 'single':
        report_data = build_tpcds_single_report_data(extracted, analysis, insights, intent, args.charts_dir_rel)
    else:
        builder = BUILDERS.get(rt)
        if not builder:
            raise SystemExit(f'未知 report_type: {rt}')
        report_data = builder(extracted, analysis, insights, intent, args.charts_dir_rel)

    os.makedirs(args.out_dir, exist_ok=True)
    md_path = os.path.join(args.out_dir, 'report.md')
    docx_path = os.path.join(args.out_dir, 'report.docx')
    html_path = os.path.join(args.out_dir, 'report.html')

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(render_md(report_data))
    print(f'✅ Markdown: {md_path}')

    render_docx(report_data, docx_path,
                charts_abs_dir=os.path.abspath(os.path.join(args.out_dir, args.charts_dir_rel)))
    print(f'✅ Word:     {docx_path}')

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(render_html(report_data))
    print(f'✅ HTML:     {html_path}')


if __name__ == '__main__':
    main()
