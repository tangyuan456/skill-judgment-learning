#!/usr/bin/env python3
"""
detect_input.py — 自动识别用户输入的数据源类型

用法：
    from detect_input import detect_data_source
    src = detect_data_source(user_input_text)
    # src = {"type": "local_file"|"local_data"|"task_id"|"keyword_only", "value": ...}
"""
import json
import os
import re
from typing import Dict, Optional


FILE_EXT_PATTERN = re.compile(r'([A-Za-z0-9_\-./\u4e00-\u9fa5]+?\.(?:log|xlsx|json|csv))', re.IGNORECASE)
TASK_ID_HINT = re.compile(r'(task_id|plan_id|report_id)\s*[:为=]?\s*([a-zA-Z0-9_\-]{6,80})', re.IGNORECASE)
TASK_ID_INLINE = re.compile(r'\b([a-f0-9]{8,32}(?:_[a-zA-Z0-9]+){2,5})\b')  # 含 _tdsql_intel_x86 形式
PURE_HEX_ID = re.compile(r'^[a-f0-9]{8,32}$', re.IGNORECASE)
JSON_BLOB = re.compile(r'\{[^{}]*"(test_name|results|dimension|task_id)"[^{}]*\}', re.DOTALL)


def detect_data_source(text: str) -> Dict[str, Optional[str]]:
    """根据用户输入文本判定数据源类型。

    返回 {"type": ..., "value": ..., "extras": [...]}
    """
    if not text:
        return {"type": "keyword_only", "value": None}

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

    # 2) 内嵌 JSON 数据（粘贴的数据库行）
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

    # 3) task_id 显式提及（"task_id 为 xxx"）
    hint = TASK_ID_HINT.search(text)
    if hint:
        return {
            "type": "task_id",
            "value": hint.group(2),
            "id_kind": hint.group(1).lower(),
        }

    # 4) task_id 模式（含产品/架构片段，如 878fd4d4_tdsql_intel_x86）
    inline = TASK_ID_INLINE.search(text)
    if inline:
        return {"type": "task_id", "value": inline.group(1), "id_kind": "task_id"}

    # 5) 纯 hex 字符串（可能是 task_id）
    stripped = text.strip()
    if PURE_HEX_ID.match(stripped):
        return {"type": "task_id", "value": stripped, "id_kind": "task_id"}

    # 6) 默认仅关键词
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
