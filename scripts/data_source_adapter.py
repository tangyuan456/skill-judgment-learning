#!/usr/bin/env python3
"""
data_source_adapter.py — 统一数据接入

根据 intent.data_source_type 调用不同适配器，输出标准 records.json。
适配器：
  - local_file: 本地 .log/.xlsx/.json/.csv
  - local_data: 粘贴的 JSON 文本
  - task_id / keyword_only: 经 db_query.py 查询，再转换为标准结构

标准结构见 references/数据源接入规范.md §1。
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 懒加载上游 log 解析（仅在处理 .log 时才需要；寻找 tdsql-b-whitepaper/scripts）
_UPSTREAM_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 'tdsql-b-whitepaper', 'scripts'),
    os.path.join(os.getcwd(), 'tdsql-b-whitepaper', 'scripts'),
    os.path.join(os.getcwd(), '..', 'tdsql-b-whitepaper', 'scripts'),
]


def _load_parse_log():
    """动态加载 tdsql-b-whitepaper/scripts/log_to_excel.parse_log。"""
    for cand in _UPSTREAM_CANDIDATES:
        cand = os.path.abspath(cand)
        if os.path.exists(os.path.join(cand, 'log_to_excel.py')):
            if cand not in sys.path:
                sys.path.insert(0, cand)
            from log_to_excel import parse_log  # type: ignore
            return parse_log
    raise RuntimeError(
        '未找到 tdsql-b-whitepaper/scripts/log_to_excel.py（解析 .log 文件需要此脚本）'
    )


# ============== 反向场景映射 ==============
SCEN_FROM_DB = {
    'point_select': 'oltp_point_select',
    'read_only': 'oltp_read_only',
    'write_only': 'oltp_write_only',
    'read_write': 'oltp_read_write',
    'update_index': 'oltp_update_index',
    'update_non_index': 'oltp_update_non_index',
    'random_points': 'oltp_random_points',
    'random_ranges': 'oltp_random_ranges',
    'tpmC': 'tpmC',
    'NewOrders': 'tpmC',
}


def _normalize_scenario(name: str) -> Optional[str]:
    """从 test_name 字符串中识别 sysbench 标准场景名。"""
    if not name:
        return None
    # 已是 oltp_* 标准名
    m = re.search(r'(oltp_[a-z_]+)', name, re.IGNORECASE)
    if m:
        return m.group(1).lower()
    # DB 短格式
    for short, full in SCEN_FROM_DB.items():
        if short in name:
            return full
    return None


def _extract_threads(test_name: str, results_key: str) -> Optional[int]:
    """从 test_name 或 results_key 中提取 threads。"""
    m = re.search(r'(\d+)\s*threads?', test_name or '', re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r'threads\s*=\s*(\d+)', results_key or '', re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _extract_arch(test_name: str) -> str:
    if '集中式' in (test_name or ''):
        return '集中式'
    if '分布式' in (test_name or ''):
        return '分布式'
    return ''


# ============== 适配器：本地 log ==============
def adapter_local_log(path: str) -> Dict[str, Any]:
    """复用 tdsql-b-whitepaper 的 parse_log。"""
    parse_log = _load_parse_log()
    header, recs = parse_log(path)
    product = header.get('engine', os.path.basename(path).split('.')[0])
    records = []
    for r in recs:
        records.append({
            'product': product,
            'scenario': f"oltp_{r['scenario'].replace('oltp_','').lstrip('_')}" if not r['scenario'].startswith('oltp_') else r['scenario'],
            'threads': r['threads'],
            'tps': r['tps'],
            'qps': r['qps'],
            'p95_ms': r['p95_ms'],
            'p99_ms': r.get('p99_ms'),
            'source_log': os.path.basename(path),
        })
    return {
        'meta': {
            'products': [product],
            'scenarios': sorted({r['scenario'] for r in records}),
            'concurrencies': sorted({r['threads'] for r in records}),
            'test_env': {},
            'log_meta': [{
                'product': product,
                'log_file': os.path.basename(path),
                'engine': header['engine'],
                'start_time': header['start_time'],
                'db_endpoint': header['db_endpoint'],
                'data_config': header['data_config'],
                'duration_sec': header['duration_sec'],
            }],
            'source_info': {'type': 'local_file', 'value': path, 'rows_fetched': len(records)},
        },
        'records': records,
    }


# ============== 适配器：本地 xlsx（沿用上游约定）==============
def adapter_local_xlsx(path: str) -> Dict[str, Any]:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    product_sheets = [s for s in wb.sheetnames if not s.startswith('_')]
    expected = ['scenario', 'threads', 'tps', 'qps', 'p95_ms', 'p99_ms']
    records = []
    products = []
    for sn in product_sheets:
        ws = wb[sn]
        header = [c.value for c in ws[1]]
        if header[:6] != expected:
            raise RuntimeError(f'{sn} 表头不符合标准: {header}')
        products.append(sn)
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or row[0] is None:
                continue
            records.append({
                'product': sn,
                'scenario': row[0],
                'threads': row[1],
                'tps': row[2],
                'qps': row[3],
                'p95_ms': row[4],
                'p99_ms': row[5] if len(row) > 5 else None,
                'source_log': os.path.basename(path),
            })
    return {
        'meta': {
            'products': products,
            'scenarios': sorted({r['scenario'] for r in records}),
            'concurrencies': sorted({r['threads'] for r in records}),
            'test_env': {},
            'log_meta': [{'product': p, 'log_file': os.path.basename(path)} for p in products],
            'source_info': {'type': 'local_file', 'value': path, 'rows_fetched': len(records)},
        },
        'records': records,
    }


# ============== 适配器：本地 json ==============
def adapter_local_json(path: str) -> Dict[str, Any]:
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, dict) and 'records' in data and 'meta' in data:
        return data  # 已是标准格式
    if isinstance(data, list):
        # 尝试将 yunyu 表导出的列表转换
        return adapter_yunyu_rows(data, source_value=path)
    raise RuntimeError(f'JSON 格式不识别: {path}')


# ============== 适配器：本地 csv ==============
def adapter_local_csv(path: str) -> Dict[str, Any]:
    records = []
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append({
                'product': row.get('product', os.path.basename(path)),
                'scenario': row['scenario'],
                'threads': int(row['threads']),
                'tps': float(row['tps']),
                'qps': float(row['qps']),
                'p95_ms': float(row['p95_ms']) if row.get('p95_ms') else None,
                'p99_ms': float(row['p99_ms']) if row.get('p99_ms') else None,
            })
    return {
        'meta': {
            'products': sorted({r['product'] for r in records}),
            'scenarios': sorted({r['scenario'] for r in records}),
            'concurrencies': sorted({r['threads'] for r in records}),
            'test_env': {},
            'log_meta': [],
            'source_info': {'type': 'local_file', 'value': path, 'rows_fetched': len(records)},
        },
        'records': records,
    }


# ============== 数据种类检测 ==============
def _detect_data_kind(rows: List[Dict[str, Any]]) -> str:
    """根据 yunyu 行的字段识别数据种类。

    返回值：
      - 'tpcds_duration' : mrthree 工具 + tpcds_qNN/tpcds_load 场景（只有 duration_s）
      - 'sysbench_oltp'  : sysbench + oltp_* 场景（TPS/QPS/P95）
      - 'mixed'          : 混合或未知
    """
    if not rows:
        return 'unknown'
    tpcds_cnt = 0
    sysbench_cnt = 0
    for r in rows[:200]:
        dim = r.get('dimension') or {}
        if isinstance(dim, str):
            try:
                dim = json.loads(dim)
            except Exception:
                dim = {}
        test_name = (dim.get('test_name') or '').lower()
        test_scene = (dim.get('test_scene') or '').lower()
        tool = (dim.get('tool_name') or '').lower()
        if 'tpcds_q' in test_name or 'tpcds_q' in test_scene or 'tpcds_load' in test_name:
            tpcds_cnt += 1
        elif 'oltp_' in test_name or tool == 'sysbench':
            sysbench_cnt += 1
    if tpcds_cnt > sysbench_cnt and tpcds_cnt > 0:
        return 'tpcds_duration'
    if sysbench_cnt > 0:
        return 'sysbench_oltp'
    return 'mixed'


# ============== 适配器：TPC-DS duration ==============
_EXCLUDE_KEYWORDS = [
    'cleanup', 'clean_up', 'drop', 'truncate', 'setup', 'prepare', 'init',
    'create_table', 'load_data', 'create_database', 'import_data', 'insert_data',
    'download_test_case', 'precheck', 'sysbench_precheck', 'download',
]
_EXCLUDE_TOOLS = ['setup', 'mrthree_setup', 'precheck_tool']


def adapter_yunyu_rows_tpcds(rows: List[Dict[str, Any]], source_value: str = '') -> Dict[str, Any]:
    """TPC-DS 场景：每条 dimension.test_name 对应 1 个查询，results.duration_s 为耗时。"""
    import re as _re
    records = []
    env_info = {}
    for row in rows:
        dim = row.get('dimension') or {}
        results = row.get('results') or {}
        if isinstance(dim, str):
            try: dim = json.loads(dim)
            except Exception: dim = {}
        if isinstance(results, str):
            try: results = json.loads(results)
            except Exception: results = {}

        tool = (dim.get('tool_name') or '').lower()
        if tool in _EXCLUDE_TOOLS:
            continue
        test_name = dim.get('test_name') or ''
        tn_lower = test_name.lower()
        # 过滤数据准备/清理场景
        if any(k in tn_lower for k in _EXCLUDE_KEYWORDS):
            continue
        # 只保留 tpcds_q* 查询（load_Ng 仍保留，但单独打标签）
        if 'tpcds_q' not in tn_lower and 'tpcds_load' not in tn_lower:
            continue

        duration = _to_float(results.get('duration_s') or results.get('duration'))
        if duration is None:
            continue

        # 解析查询编号
        m = _re.search(r'tpcds_q(\d+)', tn_lower)
        q_no = int(m.group(1)) if m else None
        is_load = 'tpcds_load' in tn_lower

        deploy_arch = dim.get('deploy_arch') or ('standalone' if 'standalone' in tn_lower else
                                                 ('distributed' if 'distributed' in tn_lower else ''))
        product_type = dim.get('product_type') or dim.get('component_name') or 'unknown'
        product = f"{product_type}-{deploy_arch}" if deploy_arch else product_type

        records.append({
            'product': product,
            'query_no': q_no,
            'query_label': f'Q{q_no}' if q_no is not None else ('数据加载' if is_load else test_name),
            'test_name': test_name,
            'duration_s': duration,
            'is_load': is_load,
            'task_id': row.get('task_id'),
            'plan_id': row.get('plan_id'),
            'report_id': row.get('report_id'),
            'start_time': row.get('created'),
            'raw': {'dimension': dim, 'results_key': row.get('results_key')},
        })

        # 环境信息（取第一条）
        if not env_info:
            env_info = {
                'product_type': dim.get('product_type'),
                'deploy_arch': dim.get('deploy_arch'),
                'cn_version': dim.get('cn_version'),
                'dn_version': dim.get('dn_version'),
                'cvm_cpu': dim.get('cvm_cpu'),
                'cvm_memory': dim.get('cvm_memory'),
                'cpu_arch': dim.get('cpu_arch'),
                'machine_model': dim.get('machine_model'),
                'machine_type': dim.get('machine_type'),
                'cpu_performance_mode': dim.get('cpu_performance_mode'),
                'node_config': dim.get('node_config'),
                'network_type': dim.get('network_type'),
                'kernel_config': dim.get('kernel_config'),
                'requirement_type': dim.get('requirement_type'),
                'env_tag': dim.get('env_tag'),
                'test_category': dim.get('test_category'),
            }

    return {
        'meta': {
            'data_kind': 'tpcds_duration',
            'products': sorted({r['product'] for r in records}),
            'scenarios': sorted({r['query_label'] for r in records}),
            'concurrencies': [],
            'test_env': env_info,
            'log_meta': [{
                'product': (sorted({r['product'] for r in records}) or ['unknown'])[0],
                'engine': 'mrthree (TPC-DS)',
                'task_id': (records[0]['task_id'] if records else source_value),
            }],
            'source_info': {
                'type': 'task_id',
                'value': source_value,
                'rows_fetched': len(records),
                'total_rows_in_source': len(rows),
            },
        },
        'records': records,
    }


# ============== 适配器：yunyu 数据库行转换（sysbench OLTP）==============
def adapter_yunyu_rows(rows: List[Dict[str, Any]], source_value: str = '') -> Dict[str, Any]:
    """yunyu_test_results 数据库行 → 标准 records。"""
    records = []
    log_meta_set = {}

    for row in rows:
        dim = row.get('dimension') or {}
        results = row.get('results') or {}
        if isinstance(dim, str):
            dim = json.loads(dim)
        if isinstance(results, str):
            results = json.loads(results)

        test_name = dim.get('test_name', '')
        scenario = _normalize_scenario(test_name)
        threads = _extract_threads(test_name, row.get('results_key', ''))
        if not scenario or threads is None:
            continue  # 跳过无法解析的

        arch = _extract_arch(test_name)
        product_base = dim.get('tool_version') or dim.get('component_version') or 'unknown'
        product = f"{arch}-{product_base}" if arch else product_base

        # 提取关键指标（兼容多种字段名）
        qps = _to_float(results.get('qps') or results.get('QPS'))
        tps = _to_float(results.get('tps') or results.get('TPS'))
        p95 = _to_float(results.get('p95') or results.get('p95_latency') or results.get('latency_p95'))
        p99 = _to_float(results.get('p99') or results.get('p99_latency') or results.get('latency_p99'))

        if qps is None or tps is None:
            # 主键点查/索引更新场景，TPS=QPS（每事务 1 语句）
            qps = qps or tps
            tps = tps or qps

        if qps is None or tps is None or p95 is None:
            continue

        records.append({
            'product': product,
            'scenario': scenario,
            'threads': threads,
            'tps': tps,
            'qps': qps,
            'p95_ms': p95,
            'p99_ms': p99,
            'task_id': row.get('task_id'),
            'plan_id': row.get('plan_id'),
            'report_id': row.get('report_id'),
            'start_time': row.get('created'),
            'raw': {'dimension': dim, 'results_key': row.get('results_key')},
        })

        # log_meta 去重
        key = product
        if key not in log_meta_set:
            log_meta_set[key] = {
                'product': product,
                'engine': dim.get('tool_name', ''),
                'start_time': row.get('created'),
                'data_config': row.get('results_key', ''),
                'duration_sec': _extract_duration(row.get('results_key', '')),
                'task_id': row.get('task_id'),
            }

    return {
        'meta': {
            'products': sorted({r['product'] for r in records}),
            'scenarios': sorted({r['scenario'] for r in records}),
            'concurrencies': sorted({r['threads'] for r in records}),
            'test_env': {},
            'log_meta': list(log_meta_set.values()),
            'source_info': {
                'type': 'task_id',
                'value': source_value,
                'rows_fetched': len(records),
            },
        },
        'records': records,
    }


def _to_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _extract_duration(rk: str) -> Optional[int]:
    m = re.search(r'time\s*=\s*(\d+)', rk or '')
    return int(m.group(1)) if m else None


# ============== 主分发 ==============
def load_records(intent: Dict[str, Any], db_config_path: str = 'config/db.yaml') -> Dict[str, Any]:
    ds_type = intent['data_source_type']
    ds_value = intent.get('data_source_value')

    if ds_type == 'local_file':
        if not ds_value or not os.path.exists(ds_value):
            raise RuntimeError(f'E2001: 本地文件不存在: {ds_value}')
        ext = ds_value.rsplit('.', 1)[-1].lower()
        if ext == 'log':
            return adapter_local_log(ds_value)
        if ext == 'xlsx':
            return adapter_local_xlsx(ds_value)
        if ext == 'json':
            return adapter_local_json(ds_value)
        if ext == 'csv':
            return adapter_local_csv(ds_value)
        raise RuntimeError(f'E2002: 不识别的扩展名: {ext}')

    if ds_type == 'local_data':
        # 期望是 yunyu 单条记录的 JSON 字符串，或多条数组
        data = json.loads(ds_value)
        rows = data if isinstance(data, list) else [data]
        return adapter_yunyu_rows(rows, source_value='local_data')

    if ds_type in ('task_id', 'keyword_only'):
        # 默认走 YunYu HTTP API（无需直连 PostgreSQL）
        # 如需直连 PG，设环境变量 USE_DIRECT_PG=1
        use_pg = os.environ.get('USE_DIRECT_PG', '').lower() in ('1', 'true', 'yes')
        if use_pg:
            from db_query import execute as db_execute
            rows = db_execute(intent, db_config_path)
        else:
            from db_query_http import execute_via_http
            rows = execute_via_http(intent)
        if not rows:
            raise RuntimeError('E2004: 查询返回 0 行（请检查 task_id/场景关键词是否正确，或数据是否已入库 yunyu_test_results）')
        kind = _detect_data_kind(rows)
        if kind == 'tpcds_duration':
            return adapter_yunyu_rows_tpcds(rows, source_value=str(ds_value))
        return adapter_yunyu_rows(rows, source_value=str(ds_value))

    raise RuntimeError(f'未知 data_source_type: {ds_type}')


# ============== 数据质量门控 ==============
def quality_check(extracted: Dict[str, Any]) -> Dict[str, Any]:
    records = extracted['records']
    n = len(records)
    if n == 0:
        raise RuntimeError('E2004: records 为空')

    kind = extracted.get('meta', {}).get('data_kind', 'sysbench_oltp')

    if kind == 'tpcds_duration':
        null_dur = sum(1 for r in records if r.get('duration_s') is None)
        if null_dur:
            raise RuntimeError(f'E2005: duration_s 空值率超标 {null_dur}/{n}')
        return {
            'records': n,
            'duration_null_rate': 0,
            'queries': sorted({r.get('query_label', '-') for r in records}),
            'data_kind': kind,
        }

    # sysbench_oltp 默认逻辑
    null_tps = sum(1 for r in records if r.get('tps') is None)
    null_qps = sum(1 for r in records if r.get('qps') is None)
    null_p95 = sum(1 for r in records if r.get('p95_ms') is None)
    null_p99 = sum(1 for r in records if r.get('p99_ms') is None)

    if null_tps or null_qps or null_p95:
        raise RuntimeError(
            f'E2005: 空值率超标 — TPS={null_tps}/{n}, QPS={null_qps}/{n}, P95={null_p95}/{n}'
        )

    cbm = defaultdict(lambda: defaultdict(set))
    for r in records:
        cbm[r['product']][r['scenario']].add(r['threads'])

    return {
        'records': n,
        'tps_null_rate': null_tps / n,
        'qps_null_rate': null_qps / n,
        'p95_null_rate': null_p95 / n,
        'p99_null_rate': null_p99 / n,
        'concurrencies_by_product_scenario': {
            p: {s: sorted(ts) for s, ts in sd.items()} for p, sd in cbm.items()
        },
        'data_kind': kind,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--intent', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--db-config', default='config/db.yaml')
    args = ap.parse_args()

    with open(args.intent, encoding='utf-8') as f:
        intent = json.load(f)

    extracted = load_records(intent, args.db_config)
    qc = quality_check(extracted)
    if qc.get('data_kind') != 'tpcds_duration':
        extracted['meta']['concurrencies_by_product_scenario'] = qc['concurrencies_by_product_scenario']

    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(extracted, f, ensure_ascii=False, indent=2, default=str)
    print(f'✅ extracted_data.json 已保存: {args.out}（{qc["records"]} 条记录, kind={qc.get("data_kind","?")}）')
    print(f'   产品: {extracted["meta"]["products"]}')
    print(f'   场景: {extracted["meta"]["scenarios"][:10]}{"..." if len(extracted["meta"]["scenarios"])>10 else ""}')
    if qc.get('data_kind') != 'tpcds_duration':
        print(f'   并发档: {extracted["meta"]["concurrencies"]}')


if __name__ == '__main__':
    main()
