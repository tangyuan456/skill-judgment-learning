#!/usr/bin/env python3
"""
run_pipeline.py — 一键端到端执行（自包含版本）

输入：用户自然语言（--text）或已生成的 intent.json（--intent）
输出：output/{report.md, report.docx, report.html, charts/, data/}

用法：
    # 模式 1：自然语言
    python run_pipeline.py --text "对 test.log 生成单次测试报告" --out output

    # 模式 2：本地文件
    python run_pipeline.py --text "/path/to/sysbench.log" --out output

    # 模式 3：已有 intent.json
    python run_pipeline.py --intent data/intent.json --out output
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
SKILL_DIR = HERE.parent


def run(cmd, cwd=None):
    print(f'\n> {" ".join(cmd)}')
    effective_cwd = cwd or os.getcwd()
    r = subprocess.run(cmd, cwd=effective_cwd)
    if r.returncode != 0:
        raise SystemExit(f'步骤失败: {" ".join(cmd)}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--text', help='用户自然语言输入')
    ap.add_argument('--intent', help='已有 intent.json 路径（跳过解析）')
    ap.add_argument('--out', required=True, help='输出目录')
    args = ap.parse_args()

    out_dir = Path(args.out).resolve()
    data_dir = out_dir / 'data'
    charts_dir = out_dir / 'charts'
    out_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(exist_ok=True)
    charts_dir.mkdir(exist_ok=True)

    intent_path = data_dir / 'intent.json'
    extracted_path = data_dir / 'extracted_data.json'
    analysis_path = data_dir / 'analysis_results.json'
    insights_path = data_dir / 'insights.json'

    # === 阶段 1：意图解析 ===
    if args.intent:
        with open(args.intent, encoding='utf-8') as f:
            intent = json.load(f)
        with open(intent_path, 'w', encoding='utf-8') as f:
            json.dump(intent, f, ensure_ascii=False, indent=2)
    else:
        if not args.text:
            raise SystemExit('必须提供 --text 或 --intent')
        run([sys.executable, str(HERE / 'parse_intent.py'),
             '--text', args.text, '--out', str(intent_path)])

    intent = json.load(open(intent_path, encoding='utf-8'))
    print(f'\n意图解析结果：')
    print(f'  data_source_type: {intent["data_source_type"]}')
    print(f'  report_type:      {intent["report_type"]}')

    # === 阶段 2：数据接入 ===
    run([sys.executable, str(HERE / 'data_source_adapter.py'),
         '--intent', str(intent_path),
         '--out', str(extracted_path)])

    # === 阶段 3：分析 ===
    run([sys.executable, str(HERE / 'analyze.py'),
         '--extracted', str(extracted_path),
         '--intent', str(intent_path),
         '--out-analysis', str(analysis_path),
         '--out-insights', str(insights_path)])

    # === 阶段 4：图表 ===
    run([sys.executable, str(HERE / 'generate_charts.py'),
         '--extracted', str(extracted_path),
         '--analysis', str(analysis_path),
         '--charts-dir', str(charts_dir),
         '--report-type', intent['report_type']])

    # === 阶段 5：渲染三格式 ===
    run([sys.executable, str(HERE / 'render_all.py'),
         '--extracted', str(extracted_path),
         '--analysis', str(analysis_path),
         '--insights', str(insights_path),
         '--intent', str(intent_path),
         '--out-dir', str(out_dir),
         '--charts-dir-rel', 'charts'])

    print('\n流水线完成')
    print(f'   报告位于: {out_dir}/')
    print(f'     - report.md')
    print(f'     - report.docx')
    print(f'     - report.html')
    print(f'     - charts/  ({len(list(charts_dir.glob("*.png")))} 张图)')
    print(f'     - data/    ({len(list(data_dir.glob("*.*")))} 份中间产物)')


if __name__ == '__main__':
    main()
