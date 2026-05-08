#!/usr/bin/env python3
"""
probe_mrthree.py — 查询 UUID 格式 task_id 是否在 YunYu 报告系统中存在

用途：yunyu_test_results 表中只包含形如 100000xxxxx 或 xxxx_tdsql_xxx 的 task_id；
UUID 形式的 task_id（如 75ff5153-...）属于 MrThree 工作流，需要通过
/test/api/report/detail 接口验证其存在性。

用法：
    python probe_mrthree.py --task-id 75ff5153-e6db-4a6a-83ac-1a7828b1869b
"""
import argparse
import json
import os
import sys

try:
    import requests
    import urllib3
    urllib3.disable_warnings()
except ImportError:
    print('ERROR: 未安装 requests', file=sys.stderr)
    sys.exit(1)


URL = 'http://yunyu.woa.com/test/api/report/detail'
DEFAULT_TOKEN = 'QVBJfHwxOTQ5NjQ0MzQ0MjYxMTAzMDI5NDlhYWZlYTRmZmVhYzllMzg3MjE4MDcwNjU4ZjBmNQ=='


def probe(task_id: str, p_id: str = '1', token: str = None) -> dict:
    token = token or os.environ.get('YUNYU_API_TOKEN') or DEFAULT_TOKEN
    headers = {
        'YUNYU-SYS-ID': 'check',
        'YUNYU-TOKEN': token,
        'YUNYU-PID': str(p_id),
    }
    params = {
        'p_id': str(p_id),
        'formValue': '{}',
        'admin': 'true',
        'taskId': task_id,
    }
    r = requests.get(URL, params=params, headers=headers, timeout=30, verify=False)
    try:
        return r.json()
    except Exception:
        return {'raw': r.text[:500], 'status_code': r.status_code}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--p-id', default='1')
    args = ap.parse_args()

    result = probe(args.task_id, args.p_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    code = result.get('code') if isinstance(result, dict) else None
    if code in ('Success', 0, '0'):
        print('\n✅ UUID 存在')
        sys.exit(0)
    elif code == 'ReportFailure.NotFound':
        print(f'\n❌ UUID 不存在：{result.get("msg")}')
        sys.exit(2)
    else:
        print('\n⚠️ 返回未知 code，请人工检查')
        sys.exit(1)


if __name__ == '__main__':
    main()
