#!/usr/bin/env python3
"""
detect_input.py — 自动识别用户输入的数据源类型

用法：
    from detect_input import detect_data_source
    src = detect_data_source(user_input_text)
    # src = {"type": "local_file"|"local_data"|"missing_data", "value": ...}
"""
import json
import os
import re
from typing import Dict, Optional


FILE_EXT_PATTERN = re.compile(r'([A-Za-z0-9_\-./\u4e00-\u9fa5]+?\.(?:log|xlsx|json|csv))', re.IGNORECASE)
JSON_BLOB = re.compile(r'\{[^{}]*"(meta|records|test_name|results|dimension)"[^{}]*\}', re.DOTALL)


def detect_data_source(text: str) -> Dict[str, Optional[str]]:
    """根据用户输入文本判定数据源类型。

    返回 {"type": ..., "value": ..., "extras": [...]}
    """
    if not text:
        return {"type": "missing_data", "value": None}

    # 1) 本地文件路径（绝对或相对）
    file_matches = FILE_EXT_PATTERN.findall(text)
    # 同时尝试相对当前工作目录与脚本所在仓库根目录
    cwd = os.getcwd()
    skill_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    existing = []
    for fp in file_matches:
        for base in (None, cwd, skill_root):
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

    # 2) 内嵌 JSON 数据（粘贴的标准 records 或原始测试行）
    json_match = JSON_BLOB.search(text)
    if json_match:
        # 尝试找到完整 JSON 对象（简化处理：从第一个 { 找到匹配的 }）
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

    # 3) 默认缺少可用本地数据源
    return {"type": "missing_data", "value": None}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--text', required=True, help='用户输入文本')
    args = ap.parse_args()
    result = detect_data_source(args.text)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
