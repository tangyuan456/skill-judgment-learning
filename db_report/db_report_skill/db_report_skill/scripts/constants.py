"""
constants.py — 自包含常量定义，不依赖任何上游 skill。
"""
# 场景中英映射
SCENARIO_CN = {
    'oltp_point_select': '点查',
    'oltp_read_only': '只读',
    'oltp_write_only': '写入',
    'oltp_read_write': '混合读写',
    'oltp_update_index': '索引更新',
    'oltp_update_non_index': '非索引更新',
    'oltp_random_points': '随机点查',
    'oltp_random_ranges': '随机范围',
    'oltp_insert': '插入',
    'tpmC': 'tpmC',
}

# 标准场景顺序
SCENARIOS = [
    'oltp_point_select',
    'oltp_read_only',
    'oltp_write_only',
    'oltp_read_write',
    'oltp_update_index',
    'oltp_update_non_index',
    'oltp_insert',
    'oltp_random_points',
    'oltp_random_ranges',
]

# 中文字体回退链
MATPLOTLIB_CN_FONTS = [
    'PingFang SC', 'Hiragino Sans GB', 'Arial Unicode MS',
    'Microsoft YaHei', 'SimHei', 'DejaVu Sans',
]

# 场景标准配色
SCENARIO_COLORS = {
    'oltp_point_select': '#1f77b4',
    'oltp_read_only': '#ff7f0e',
    'oltp_write_only': '#2ca02c',
    'oltp_read_write': '#d62728',
    'oltp_update_index': '#9467bd',
    'oltp_update_non_index': '#8c564b',
    'oltp_insert': '#e377c2',
    'oltp_random_points': '#7f7f7f',
    'oltp_random_ranges': '#bcbd22',
    'tpmC': '#17becf',
}

# 产品配色
PRODUCT_COLORS = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',
    '#9467bd', '#8c564b', '#e377c2', '#7f7f7f',
    '#bcbd22', '#17becf',
]

# 报告类型中文名
REPORT_TYPE_CN = {
    'single': '单次测试报告',
    'comparison': '性能对比报告',
    'iteration': '迭代演进报告',
    'custom': '客制化报告',
}
