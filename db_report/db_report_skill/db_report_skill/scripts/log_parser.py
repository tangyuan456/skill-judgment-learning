#!/usr/bin/env python3
"""
log_parser.py — 自包含 sysbench 日志解析器，不依赖上游 skill。
支持标准 sysbench run 输出格式。

解析的字段：scenario, threads, tps, qps, p95_ms, p99_ms, engine, start_time, db_endpoint, data_config, duration_sec
"""
import os
import re
from typing import Any, Dict, List, Optional, Tuple


def parse_log(filepath: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """解析 sysbench 日志文件，返回 (header, records)。"""
    with open(filepath, encoding='utf-8', errors='replace') as f:
        content = f.read()

    header = _parse_header(content)
    records = _parse_records(content)

    return header, records


def _parse_header(content: str) -> Dict[str, Any]:
    header: Dict[str, Any] = {
        'engine': 'sysbench',
        'start_time': '',
        'db_endpoint': '',
        'data_config': '',
        'duration_sec': 0,
    }

    # 引擎/工具名
    m = re.search(r'(?:Running|run|tool)\s*[:=]?\s*(sysbench|benchmarksql|tpcc|tpch)', content, re.IGNORECASE)
    if m:
        header['engine'] = m.group(1).lower()

    # 起始时间
    m = re.search(r'(?:start|开始).*?(\d{4}[-/]\d{2}[-/]\d{2}[\sT]\d{2}:\d{2}:\d{2})', content)
    if m:
        header['start_time'] = m.group(1)

    # DB 端点
    m = re.search(r'(?:host|主机|endpoint|db).*?[:=]?\s*([\w\.\-]+(?:[:：]\d+)?)', content, re.IGNORECASE)
    if m:
        header['db_endpoint'] = m.group(1)

    # 数据集/表配置
    m = re.search(r'(?:tables|表)\s*[:=]?\s*(\d+).*?(?:table.size|表大小|rows).*?[:=]?\s*(\d+)', content, re.IGNORECASE)
    if m:
        header['data_config'] = f"{m.group(1)} tables × {m.group(2)} rows"

    # 单场景时长
    m = re.search(r'(?:time|时长|duration).*?[:=]?\s*(\d+)', content, re.IGNORECASE)
    if m:
        header['duration_sec'] = int(m.group(1))

    return header


def _parse_records(content: str) -> List[Dict[str, Any]]:
    """从 sysbench 输出中提取各场景各并发的性能数据。"""
    records = []

    # 场景关键词映射
    scenario_map = {
        'point_select': 'oltp_point_select',
        'read_only': 'oltp_read_only',
        'write_only': 'oltp_write_only',
        'read_write': 'oltp_read_write',
        'update_index': 'oltp_update_index',
        'update_non_index': 'oltp_update_non_index',
        'insert': 'oltp_insert',
        'random_points': 'oltp_random_points',
        'random_ranges': 'oltp_random_ranges',
    }

    # 按 "Running test:" 或类似标记切分场景块
    scene_blocks = re.split(
        r'(?:Running\s+(?:the\s+)?test|开始测试|场景[:：])\s*[：:]?\s*(.+?)(?:\n|$|with)',
        content,
        flags=re.IGNORECASE,
    )

    if len(scene_blocks) < 2:
        # 尝试另一种切分：按 oltp_ 标记
        scene_blocks = re.split(r'(oltp_\w+)', content, flags=re.IGNORECASE)

    # 找到所有包含性能指标的位置
    pattern = re.compile(
        r'(?:oltp_(\w+)|tpcc)\s*.*?'
        r'(?:threads?|并发)\s*[:=]?\s*(\d+).*?'
        r'(?:transactions|tps|TPS)\s*[:=]?\s*([\d,.]+)\s*(?:per\s*sec)?.*?'
        r'(?:queries|qps|QPS)\s*[:=]?\s*([\d,.]+)\s*(?:per\s*sec)?.*?'
        r'(?:95th|p95|P95).*?[:=]?\s*([\d,.]+)',
        re.IGNORECASE | re.DOTALL,
    )

    # 更灵活的匹配：一次匹配一个完整的性能块
    # 匹配模式：scenario + threads + TPS + QPS + Latency
    block_pattern = re.compile(
        r'(?:oltp_(\w+)|(tpcc|benchmarksql))\s*.*?'
        r'(?:threads?|并发|Number of threads)[\s:=]*(\d+)',
        re.IGNORECASE,
    )

    blocks = list(block_pattern.finditer(content))

    # 如果没匹配到块格式，尝试逐行查找
    if not blocks:
        return _parse_records_fallback(content, scenario_map)

    for i, blk in enumerate(blocks):
        scenario_key = blk.group(1) or blk.group(2) or ''
        threads = int(blk.group(3))

        # 确定场景名
        if blk.group(2):
            scenario = 'tpmC'
        else:
            key = scenario_key.lower().replace('oltp_', '')
            scenario = scenario_map.get(key, f'oltp_{key}')

        # 从此块的结束到下个块的开始，提取性能数字
        start = blk.end()
        end = blocks[i + 1].start() if i + 1 < len(blocks) else len(content)
        snippet = content[start:end]

        tps = _extract_number(snippet, r'(?:transactions|tps|TPS)\s*[:=]?\s*([\d,.]+)')
        qps = _extract_number(snippet, r'(?:queries|qps|QPS)\s*[:=]?\s*([\d,.]+)')
        p95 = _extract_number(snippet, r'(?:95th|p95|P95|95th percentile)[\s:=]*([\d,.]+)')
        p99 = _extract_number(snippet, r'(?:99th|p99|P99|99th percentile)[\s:=]*([\d,.]+)')

        if tps is not None:
            records.append({
                'scenario': scenario,
                'threads': threads,
                'tps': tps,
                'qps': qps or tps,
                'p95_ms': p95,
                'p99_ms': p99,
            })

    return records


def _parse_records_fallback(content: str, scenario_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """备选解析：在原始文本中搜索所有数字序列。"""
    records = []
    seen = set()

    # 搜索所有 (scenario, threads, tps, qps, p95) 元组
    tps_pat = re.compile(r'[\s]*transactions:\s*[\d,]+\s*\(([\d,.]+)\s*per\s*sec', re.IGNORECASE)
    qps_pat = re.compile(r'[\s]*queries:\s*[\d,]+\s*\(([\d,.]+)\s*per\s*sec', re.IGNORECASE)
    p95_pat = re.compile(r'95th\s*percentile:\s*([\d,.]+)', re.IGNORECASE)
    p99_pat = re.compile(r'99th\s*percentile:\s*([\d,.]+)', re.IGNORECASE)
    thread_pat = re.compile(r'(?:Number of threads|threads?)[\s:=]*(\d+)', re.IGNORECASE)

    # 对每个场景名查找
    for key, scenario in scenario_map.items():
        # 找这个场景出现的所有位置
        for sc_m in re.finditer(rf'\b{re.escape(key)}\b', content, re.IGNORECASE):
            pos = sc_m.start()
            # 向前查找 threads
            before = content[max(0, pos - 200):pos]
            tm = thread_pat.search(before)
            if not tm:
                # 向后查找
                after = content[pos:pos + 500]
                tm = thread_pat.search(after)
            if not tm:
                continue
            threads = int(tm.group(1))

            # 向后查找 TPS/QPS/P95
            after_block = content[pos:pos + 2000]
            tps = _extract_number(after_block, r'transactions:\s*[\d,]+\s*\(([\d,.]+)\s*per\s*sec')
            qps = _extract_number(after_block, r'queries:\s*[\d,]+\s*\(([\d,.]+)\s*per\s*sec')
            p95 = _extract_number(after_block, r'95th\s*percentile:\s*([\d,.]+)')
            p99 = _extract_number(after_block, r'99th\s*percentile:\s*([\d,.]+)')

            key_id = (scenario, threads)
            if key_id in seen:
                continue
            seen.add(key_id)

            if tps is not None:
                records.append({
                    'scenario': scenario,
                    'threads': threads,
                    'tps': tps,
                    'qps': qps or tps,
                    'p95_ms': p95,
                    'p99_ms': p99,
                })

    return records


def _extract_number(text: str, pattern: str) -> Optional[float]:
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return None
    try:
        return float(m.group(1).replace(',', ''))
    except (ValueError, TypeError):
        return None


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print(f'用法: python {sys.argv[0]} <sysbench.log>')
        sys.exit(1)
    header, records = parse_log(sys.argv[1])
    print('=== Header ===')
    for k, v in header.items():
        print(f'  {k}: {v}')
    print(f'\n=== Records ({len(records)} 条) ===')
    for r in records:
        print(f'  {r["scenario"]:25s} threads={r["threads"]:>5d}  tps={r["tps"]:>12,.2f}  qps={r["qps"]:>12,.2f}  p95={r["p95_ms"]}ms')
