"""report_data 模板包，按 report_type 分发。

此 __init__ 负责在导入任何模板前，把 tdsql-b-whitepaper/scripts（上游 constants）
动态加入 sys.path，以便 single/comparison/iteration/custom 模板能成功 import。
"""
import os
import sys

_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 'tdsql-b-whitepaper', 'scripts'),
    os.path.join(os.getcwd(), 'tdsql-b-whitepaper', 'scripts'),
    os.path.join(os.getcwd(), '..', 'tdsql-b-whitepaper', 'scripts'),
]
for _c in _CANDIDATES:
    _c = os.path.abspath(_c)
    if os.path.exists(os.path.join(_c, 'constants.py')):
        if _c not in sys.path:
            sys.path.insert(0, _c)
        break
