#!/usr/bin/env python3
"""
detect_input.py — 自动识别用户输入的数据源类型（仅文本和本地文件）。

用法：
    from detect_input import detect_data_source
    src = detect_data_source(user_input_text)
    # src = {"type": "local_file"|"local_data"|"keyword_only", "value": ...}
"""
import json
import os
import re
from typing import Dict, Optional


FILE_EXT_PATTERN = re.compile(r'([A-Za-z0-9_\-./\u4e00-\u9fa5]+?\.(?:log|xlsx|xls|json|csv|txt))', re.IGNORECASE)
JSON_BLOB = re.compile(r'\{[^{}]*"(test_name|results|product|scenario|threads|tps|qps)"[^{}]*\}', re.DOTALL)


def detect_data_source(text: str) -> Dict[str, Optional[str]]:
    """根据用户输入文本判定数据源类型。只支持本地文件和粘贴数据。"""
    if not text:
        return {"type": "keyword_only", "value": None}

    # 1) 本地文件路径
    file_matches = FILE_EXT_PATTERN.findall(text)
    cwd = os.getcwd()
    existing = []
    for fp in file_matches:
        for base in (None, cwd):
            cand = fp if base is None else os.path.join(base, fp)
            if os.path.exists(cand):
                existing.append(os.path.abspath(cand))
                break
    if existing:
        return {
            "type": "local_file",
            "value": existing[0],
            "extras": existing[1:] if len(existing) > 1 else [],
        }

    # 2) 内嵌 JSON 数据（用户直接粘贴）
    json_match = JSON_BLOB.search(text)
    if json_match:
        start = json_match.start()
        depth = 0
        end = start
        for i, ch in enumerate(text[start:], start=start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        blob = text[start:end]
        try:
            json.loads(blob)
            return {"type": "local_data", "value": blob}
        except json.JSONDecodeError:
            pass

    # 3) 默认关键词
    return {"type": "keyword_only", "value": None}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--text', required=True, help='用户输入文本')
    args = ap.parse_args()
    result = detect_data_source(args.text)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
