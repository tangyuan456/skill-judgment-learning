#!/usr/bin/env python3
"""
db_query_http.py — 通过 YunYu HTTP API 查询 yunyu_test_results（Skill 默认数据源）

接口：http://yunyu.woa.com/test/api/alarm/sql_query/
请求体：{"p_id": 1, "sql_query": "SELECT ... ;"}
响应：{"code":"Success", "data": {"results": "[{...},{...}]"}}
  - 注意：data.results 是**字符串**形式的 Python dict repr（带单引号），
    需用 ast.literal_eval 解析，再转为 list[dict]。

复用：db_query.build_sql() 生成 SQL 文本（同一套 无双引号 / 字符串单引号 规则）。

用法：
    python db_query_http.py --intent data/intent.json --out data/raw_query_result.json

环境变量覆盖（优先级最高）：
    YUNYU_API_URL      默认 http://yunyu.woa.com/test/api/alarm/sql_query/
    YUNYU_API_SYS_ID   默认 check
    YUNYU_API_TOKEN    默认内置
    YUNYU_API_PID      默认 1
"""
import argparse
import ast
import json
import os
import sys
from typing import Any, Dict, List

try:
    import requests
except ImportError:
    print('ERROR: 未安装 requests。请运行: pip install requests', file=sys.stderr)
    sys.exit(1)

try:
    import yaml  # noqa: F401
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db_query import build_sql  # 复用 SQL 构造

# ============== 默认配置（Skill 级固定） ==============
DEFAULT_URL = 'http://yunyu.woa.com/test/api/alarm/sql_query/'
DEFAULT_SYS_ID = 'check'
DEFAULT_TOKEN = 'QVBJfHwxOTQ5NjQ0MzQ0MjYxMTAzMDI5NDlhYWZlYTRmZmVhYzllMzg3MjE4MDcwNjU4ZjBmNQ=='
DEFAULT_PID = 1
DEFAULT_TIMEOUT = 60

# 与 SKILL 目录同级的默认配置路径
_SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG_PATH = os.path.join(_SKILL_DIR, 'config', 'yunyu_api.yaml')


def load_api_config(config_path: str = None) -> Dict[str, Any]:
    """加载 YunYu API 配置。优先级：环境变量 > 配置文件 > 内置默认。"""
    cfg = {
        'url': DEFAULT_URL,
        'sys_id': DEFAULT_SYS_ID,
        'token': DEFAULT_TOKEN,
        'p_id': DEFAULT_PID,
        'timeout': DEFAULT_TIMEOUT,
    }
    path = config_path or DEFAULT_CONFIG_PATH
    if _HAS_YAML and os.path.exists(path):
        try:
            import yaml
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            file_cfg = data.get('yunyu_api') or data
            for k in cfg.keys():
                if file_cfg.get(k) is not None:
                    cfg[k] = file_cfg[k]
        except Exception as e:
            print(f'[WARN] 读取配置 {path} 失败: {e}', file=sys.stderr)
    # 环境变量覆盖
    env_map = {
        'url': 'YUNYU_API_URL',
        'sys_id': 'YUNYU_API_SYS_ID',
        'token': 'YUNYU_API_TOKEN',
        'p_id': 'YUNYU_API_PID',
        'timeout': 'YUNYU_API_TIMEOUT',
    }
    for k, env_key in env_map.items():
        v = os.environ.get(env_key)
        if v:
            cfg[k] = int(v) if k in ('p_id', 'timeout') else v
    return cfg


def query_single_sql(sql: str, config_path: str = None) -> Dict[str, Any]:
    """调用 YunYu sql_query 接口。返回原始 JSON 响应。"""
    cfg = load_api_config(config_path)
    headers = {
        'Content-Type': 'application/json',
        'YUNYU-SYS-ID': cfg['sys_id'],
        'YUNYU-TOKEN': cfg['token'],
    }
    cleaned = '\n'.join(ln.strip() for ln in sql.split('\n') if ln.strip())
    if not cleaned.endswith(';'):
        cleaned += ';'
    payload = {'p_id': int(cfg['p_id']), 'sql_query': cleaned}

    print(f'\n=== YunYu HTTP 查询 ===\nURL: {cfg["url"]}\np_id: {cfg["p_id"]}\nSQL:\n{cleaned}\n',
          file=sys.stderr)
    resp = requests.post(cfg['url'], json=payload, headers=headers, timeout=int(cfg['timeout']))
    if resp.status_code != 200:
        raise RuntimeError(f'HTTP {resp.status_code}: {resp.text[:500]}')
    try:
        return resp.json()
    except Exception as e:
        raise RuntimeError(f'响应非 JSON: {e} | body={resp.text[:500]}')


def _sanitize_repr_for_literal_eval(s: str) -> str:
    """把 Python repr 里的非字面量表达式替换为可解析的字符串。

    已知问题形态：
      - datetime.datetime(2026, 5, 8, 0, 5, 23, 465863, tzinfo=<UTC>)
      - datetime.date(2026, 5, 8)
      - <UTC>（尖括号对象）
    """
    import re as _re
    # 1) datetime.datetime(…)  / datetime.date(…)  → 提取参数转 ISO 字符串
    def _dt_repl(m):
        args = m.group(2)
        # 清掉 tzinfo=... 子串
        args = _re.sub(r',\s*tzinfo=[^,)]+', '', args)
        nums = [x.strip() for x in args.split(',') if x.strip().isdigit()]
        try:
            vals = [int(x) for x in nums]
            if m.group(1) == 'datetime' and len(vals) >= 3:
                # datetime(y,m,d[,h,mi,s[,us]])
                from datetime import datetime as _dt
                pad = vals + [0, 0, 0, 0]
                return "'" + _dt(pad[0], pad[1], pad[2], pad[3], pad[4], pad[5], pad[6]).isoformat() + "'"
            if m.group(1) == 'date' and len(vals) >= 3:
                from datetime import date as _d
                return "'" + _d(vals[0], vals[1], vals[2]).isoformat() + "'"
        except Exception:
            pass
        return "''"
    s = _re.sub(r'datetime\.(datetime|date)\(([^)]*)\)', _dt_repl, s)
    # 2) <...> 形式对象（tzinfo=<UTC> 之类）
    s = _re.sub(r'<[^<>]*>', "'<unserializable>'", s)
    return s


def _parse_results_payload(payload: Any) -> List[Dict[str, Any]]:
    """把接口 data.results（可能是 str/list）解析为 list[dict]。"""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, str):
        return []
    s = payload.strip()
    if not s or s == '[]':
        return []
    # 先尝试标准 JSON
    try:
        return json.loads(s)
    except Exception:
        pass
    # 退化到 Python literal（含 datetime 等需要预清洗）
    try:
        v = ast.literal_eval(s)
    except Exception:
        s2 = _sanitize_repr_for_literal_eval(s)
        try:
            v = ast.literal_eval(s2)
        except Exception as e:
            raise RuntimeError(f'results 解析失败: {e} | head={s[:200]}')
    if isinstance(v, list):
        return v
    if isinstance(v, dict):
        return [v]
    return []


def _extract_rows(resp_json: Any) -> List[Dict[str, Any]]:
    """从 YunYu 响应中抽取行列表。"""
    if isinstance(resp_json, list):
        return resp_json
    if not isinstance(resp_json, dict):
        raise RuntimeError(f'响应格式不识别: {type(resp_json)}')

    code = resp_json.get('code', resp_json.get('errcode', 0))
    if code not in (0, '0', None, 'Success', 'SUCCESS', 'success'):
        msg = resp_json.get('msg') or resp_json.get('message') or resp_json.get('error') or resp_json
        raise RuntimeError(f'接口返回错误 code={code}: {msg}')

    data = resp_json.get('data')
    if isinstance(data, dict):
        for key in ('results', 'rows', 'data'):
            if key in data:
                return _parse_results_payload(data[key])
        # 兜底：rows + columns
        if isinstance(data.get('rows'), list) and (data.get('columns') or data.get('fields')):
            cols = data.get('columns') or data.get('fields')
            col_names = [c['name'] if isinstance(c, dict) else c for c in cols]
            return [dict(zip(col_names, r)) for r in data['rows']]
        return [data]
    if isinstance(data, list):
        return data
    if isinstance(data, str):
        return _parse_results_payload(data)

    for key in ('result', 'results', 'rows'):
        v = resp_json.get(key)
        if v is not None:
            return _parse_results_payload(v) if isinstance(v, str) else (v if isinstance(v, list) else [v])

    raise RuntimeError(f'响应中未找到行列表: keys={list(resp_json.keys())}')


def execute_via_http(intent: Dict[str, Any], config_path: str = None) -> List[Dict[str, Any]]:
    """构建 SQL → 调接口 → 返回标准 list[dict]。dimension/results 若为字符串会尝试解析。"""
    sql = build_sql(intent)
    raw = query_single_sql(sql, config_path)
    rows = _extract_rows(raw)

    for r in rows:
        for k in ('dimension', 'results'):
            if k in r and isinstance(r[k], str):
                try:
                    r[k] = json.loads(r[k])
                except Exception:
                    try:
                        r[k] = ast.literal_eval(r[k])
                    except Exception:
                        pass
        if 'created' in r and hasattr(r['created'], 'isoformat'):
            r['created'] = r['created'].isoformat()

    print(f'✅ YunYu HTTP 返回 {len(rows)} 行', file=sys.stderr)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--intent', required=True)
    ap.add_argument('--out', required=False)
    ap.add_argument('--config', default=None, help='YunYu API 配置文件路径')
    ap.add_argument('--print-sql-only', action='store_true')
    args = ap.parse_args()
    if not args.print_sql_only and not args.out:
        ap.error('--out 在非 --print-sql-only 模式下必填')

    with open(args.intent, encoding='utf-8') as f:
        intent = json.load(f)

    sql = build_sql(intent)
    if args.print_sql_only:
        print(sql)
        return

    rows = execute_via_http(intent, args.config)
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=2, default=str)
    print(f'✅ 结果已保存: {args.out}（{len(rows)} 行）')


if __name__ == '__main__':
    main()
