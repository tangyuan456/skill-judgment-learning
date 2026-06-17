"""对比报告模板（report_type=comparison）。

直接复用 tdsql-b-whitepaper/scripts/build_report_data.py 的 build_report_data。
"""
import os
import sys

SKILL_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(SKILL_BASE, 'tdsql-b-whitepaper', 'scripts'))

from build_report_data import build_report_data as _upstream_build  # noqa: E402


def build_comparison_report_data(extracted, analysis, insights, intent, charts_dir_rel='charts'):
    """直接调用上游 4 产品对比模板。

    上游模板默认主产品 = TDSQL-B；本 Skill 中可以由 intent.other_info 指定主产品。
    """
    return _upstream_build(extracted, analysis, insights, charts_dir_rel)
