#!/usr/bin/env python3
"""
parse_intent.py — 用户自然语言 → intent.json（仅支持文本和文件输入）

规则驱动，无 LLM 依赖。
"""
import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detect_input import detect_data_source  # noqa: E402

# ============== 中英映射表 ==============
SCENARIO_MAP = {
    '只读': 'read_only',
    '只写': 'write_only',
    '写入': 'write_only',
    '读写': 'read_write',
    '混合读写': 'read_write',
    '更新索引': 'update_index',
    '更新非索引': 'update_non_index',
    '点查': 'point_select',
    '点选': 'point_select',
    '主键点查': 'point_select',
    '随机点查': 'random_points',
    '随机范围查询': 'random_ranges',
}

ARCH_MAP = {
    '集中式': '集中式性能',
    '分布式': '分布式性能',
    '单机': '集中式性能',
    '集群': '分布式性能',
}

TOOL_MAP = {
    'sysbench': 'sysbench',
    'benchmarksql': 'BenchmarkSQL',
    'tpcc': 'BenchmarkSQL',
    'tpch': 'tpch',
}

# ============== report_type 识别 ==============
RE_COMPARISON = re.compile(r'对比|比较|差异|哪个更好|\bvs\b', re.IGNORECASE)
RE_ITERATION = re.compile(r'迭代|版本演进|历史趋势|变化趋势|演进')
RE_CUSTOM = re.compile(r'客制化|专项|定制|深度分析|详细分析')


def detect_report_type(text: str) -> str:
    if RE_COMPARISON.search(text):
        return 'comparison'
    if RE_ITERATION.search(text):
        return 'iteration'
    if RE_CUSTOM.search(text):
        return 'custom'
    return 'single'


# ============== OR vs AND 识别 ==============
RE_OR_SEPARATOR = re.compile(r'\s*[和或、]\s*|以及')


def extract_test_name_keywords(text: str) -> Dict[str, Any]:
    arch_hits = {kw: ARCH_MAP[kw] for kw in ARCH_MAP if kw in text}
    scen_hits = {kw: SCENARIO_MAP[kw] for kw in SCENARIO_MAP if kw in text}

    if not arch_hits and not scen_hits:
        return {'test_name_keywords': [], 'test_name_keywords_or': None}

    has_separator = bool(RE_OR_SEPARATOR.search(text))
    distinct_scenarios = list(set(scen_hits.values()))

    if has_separator and len(distinct_scenarios) >= 2:
        arch_part = list(set(arch_hits.values()))
        groups = [arch_part + [scen] for scen in distinct_scenarios]
        return {
            'test_name_keywords': None,
            'test_name_keywords_or': groups,
        }

    keywords = list(set(arch_hits.values()) | set(scen_hits.values()))
    return {
        'test_name_keywords': keywords,
        'test_name_keywords_or': None,
    }


# ============== 版本号 ==============
RE_VERSION = re.compile(r'(\d+\.\d+\.\d+(?:[\.\-]\w+)?)')


def extract_versions(text: str) -> List[str]:
    return list(dict.fromkeys(RE_VERSION.findall(text)))


# ============== 数值参数 ==============
RE_THREADS = re.compile(r'(\d+)\s*(?:threads|线程|并发)')
RE_TABLES = re.compile(r'(\d+)\s*(?:tables|表|张表)')
RE_TIME = re.compile(r'(?:time|测试时长|测试时间)[\s=为:]*(\d+)')
RE_WAREHOUSES = re.compile(r'(\d+)\s*(?:warehouses|仓库)')


def extract_results_filters(text: str) -> Dict[str, Optional[str]]:
    out = {'threads': None, 'tables': None, 'table_size': None, 'time': None, 'warehouses': None}
    if m := RE_THREADS.search(text):
        out['threads'] = m.group(1)
    if m := RE_TABLES.search(text):
        out['tables'] = m.group(1)
    if m := RE_TIME.search(text):
        out['time'] = m.group(1)
    if m := RE_WAREHOUSES.search(text):
        out['warehouses'] = m.group(1)
    return out


def extract_tool_name(text: str) -> Optional[str]:
    lower = text.lower()
    for kw, val in TOOL_MAP.items():
        if kw.lower() in lower:
            return val
    return None


# ============== 主流程 ==============
def parse_intent(user_input: str) -> Dict[str, Any]:
    ds = detect_data_source(user_input)
    report_type = detect_report_type(user_input)
    test_name = extract_test_name_keywords(user_input)
    results_filters = extract_results_filters(user_input)
    versions = extract_versions(user_input)
    tool_name = extract_tool_name(user_input)

    intent = {
        'data_source_type': ds['type'],
        'data_source_value': ds.get('value'),
        'report_type': report_type,
        'dimension_filters': {
            **test_name,
            'tool_name': tool_name,
            'tool_version_keywords': versions,
            'component_name': None,
            'component_version': None,
        },
        'results_key_filters': results_filters,
        'task_filters': {'task_id': None, 'plan_id': None, 'report_id': None},
        'iteration_config': None,
        'custom_config': None,
        'other_info': None,
    }

    if report_type == 'iteration':
        intent['iteration_config'] = {
            'version_range': versions,
            'regression_threshold_pct': 5,
        }
    if report_type == 'custom':
        focus = None
        if 'buffer' in user_input.lower() or 'pool' in user_input.lower():
            focus = 'buffer_pool'
        elif 'numa' in user_input.lower():
            focus = 'numa'
        elif '高并发' in user_input:
            focus = '高并发'
        elif '表数量' in user_input:
            focus = '表数量'
        intent['custom_config'] = {
            'focus_dimension': focus,
            'extra_questions': [user_input.strip()] if focus else [],
        }

    return intent


def main():
    ap = argparse.ArgumentParser(description='用户输入 → intent.json')
    ap.add_argument('--text', required=True, help='用户输入')
    ap.add_argument('--out', required=True, help='intent.json 输出路径')
    args = ap.parse_args()

    intent = parse_intent(args.text)
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(intent, f, ensure_ascii=False, indent=2)
    print(f'intent.json 已生成: {args.out}')
    print(json.dumps(intent, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
