#!/usr/bin/env python3
"""
db_query.py — PostgreSQL 查询执行器

按 references/数据源接入规范.md §3 规则：
  - 严禁 SQL 字段名/表名加双引号
  - 字符串值用单引号
  - test_name_keywords_or 必须用括号包裹整个 OR 表达式

用法（CLI）：
    python db_query.py --intent data/intent.json --out data/raw_query_result.json
"""
import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print('ERROR: 未安装 psycopg2。请运行: pip install psycopg2-binary', file=sys.stderr)
    sys.exit(1)

try:
    import yaml
except ImportError:
    print('ERROR: 未安装 pyyaml。请运行: pip install pyyaml', file=sys.stderr)
    sys.exit(1)


def load_db_config(config_path: str = 'config/db.yaml') -> Dict[str, Any]:
    """加载数据库配置，环境变量优先。"""
    cfg = {}
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}
    cfg = cfg.get('yunyu_test_results', cfg)

    # 环境变量覆盖
    overrides = {
        'host': os.environ.get('YUNYU_DB_HOST'),
        'port': os.environ.get('YUNYU_DB_PORT'),
        'database': os.environ.get('YUNYU_DB_NAME'),
        'user': os.environ.get('YUNYU_DB_USER'),
        'password': os.environ.get('YUNYU_DB_PASSWORD'),
    }
    for k, v in overrides.items():
        if v:
            cfg[k] = v

    required = ['host', 'port', 'database', 'user', 'password']
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        raise RuntimeError(f'数据库配置缺失字段: {missing}。请补充 {config_path} 或设置环境变量 YUNYU_DB_*')
    return cfg


def build_sql(intent: Dict[str, Any]) -> str:
    """根据 intent.json 构建 SQL。

    严格遵守：
      - 不加双引号包裹字段
      - test_name_keywords_or 用括号包裹
      - 字符串值用单引号
    """
    where_clauses: List[str] = []

    df = intent.get('dimension_filters') or {}
    rkf = intent.get('results_key_filters') or {}
    tf = intent.get('task_filters') or {}

    # 1) task_id / plan_id / report_id
    for kind in ['task_id', 'plan_id', 'report_id']:
        v = tf.get(kind)
        if v:
            ids = [_sql_escape(x.strip()) for x in v.split(',') if x.strip()]
            if len(ids) == 1:
                where_clauses.append(f"{kind} = '{ids[0]}'")
            else:
                where_clauses.append(f"{kind} IN ({', '.join(repr_quote(x) for x in ids)})")

    # 2) test_name_keywords_or（OR 逻辑，必须括号包裹）
    or_groups = df.get('test_name_keywords_or')
    if or_groups:
        or_parts = []
        for group in or_groups:
            and_parts = [
                f"dimension->>'test_name' LIKE '%{_sql_escape(kw)}%'"
                for kw in group
            ]
            or_parts.append('(' + ' AND '.join(and_parts) + ')')
        where_clauses.append('(' + ' OR '.join(or_parts) + ')')
    else:
        # 3) test_name_keywords（AND 逻辑）
        and_keywords = df.get('test_name_keywords') or []
        for kw in and_keywords:
            where_clauses.append(f"dimension->>'test_name' LIKE '%{_sql_escape(kw)}%'")

    # 4) tool_name
    tool = df.get('tool_name')
    if tool:
        where_clauses.append(f"dimension->>'tool_name' = '{_sql_escape(tool)}'")

    # 5) tool_version_keywords（OR 逻辑）
    tv_keywords = df.get('tool_version_keywords') or []
    if tv_keywords:
        tv_parts = [f"dimension->>'tool_version' LIKE '%{_sql_escape(kw)}%'" for kw in tv_keywords]
        where_clauses.append('(' + ' OR '.join(tv_parts) + ')')

    # 6) component_name
    if df.get('component_name'):
        where_clauses.append(f"dimension->>'component_name' = '{_sql_escape(df['component_name'])}'")

    # 7) results_key 参数
    for k in ['threads', 'tables', 'table_size', 'time', 'warehouses']:
        v = rkf.get(k)
        if v:
            where_clauses.append(f"results_key LIKE '%{k}={_sql_escape(str(v))}%'")

    where_sql = '\n  AND '.join(where_clauses) if where_clauses else 'TRUE'

    sql = f"""SELECT
  task_id,
  plan_id,
  report_id,
  dimension,
  results,
  results_key,
  created
FROM yunyu_test_results
WHERE
  {where_sql}
ORDER BY created DESC
LIMIT 5000"""
    return sql


def _sql_escape(s: str) -> str:
    """转义单引号（防 SQL 注入），不允许其他特殊字符。"""
    if s is None:
        return ''
    return str(s).replace("'", "''")


def repr_quote(s: str) -> str:
    return f"'{s}'"


def execute(intent: Dict[str, Any], config_path: str = 'config/db.yaml') -> List[Dict[str, Any]]:
    """执行查询并返回 list[dict]。"""
    cfg = load_db_config(config_path)
    sql = build_sql(intent)
    print(f'\n=== 生成的 SQL ===\n{sql}\n', file=sys.stderr)

    conn = psycopg2.connect(
        host=cfg['host'], port=int(cfg['port']),
        database=cfg['database'], user=cfg['user'], password=cfg['password'],
        sslmode=cfg.get('sslmode', 'disable'),
        connect_timeout=30,
    )
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            print(f'✅ 查询返回 {len(rows)} 行', file=sys.stderr)
            # RealDictRow → dict; 时间戳转 ISO
            out = []
            for r in rows:
                d = dict(r)
                if 'created' in d and d['created']:
                    d['created'] = d['created'].isoformat()
                out.append(d)
            return out
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--intent', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--config', default='config/db.yaml')
    ap.add_argument('--print-sql-only', action='store_true', help='仅生成 SQL 不执行（调试）')
    args = ap.parse_args()

    with open(args.intent, encoding='utf-8') as f:
        intent = json.load(f)

    if args.print_sql_only:
        print(build_sql(intent))
        return

    rows = execute(intent, args.config)
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=2, default=str)
    print(f'✅ 查询结果已保存: {args.out}（{len(rows)} 行）')


if __name__ == '__main__':
    main()
