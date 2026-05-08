-- ==========================================================
-- yunyu_test_results 标准查询模板
-- 严禁双引号包裹字段名/表名！仅字符串值用单引号
-- ==========================================================

-- 模板 1：单任务全场景（report_type=single）
-- 输入参数：:task_id
SELECT task_id, dimension, results, results_key, created
FROM yunyu_test_results
WHERE task_id = :task_id
ORDER BY created DESC;


-- 模板 2：纯关键词查询（report_type=single + keyword_only）
-- 输入参数：:keyword_pattern (e.g. '%集中式%')
SELECT task_id, dimension, results, results_key, created
FROM yunyu_test_results
WHERE dimension->>'test_name' LIKE :keyword_pattern
ORDER BY created DESC
LIMIT 200;


-- 模板 3：两版本对比（report_type=comparison）
-- 输入参数：:version_a, :version_b, :scenario_pattern
SELECT task_id, dimension, results, results_key, created
FROM yunyu_test_results
WHERE (
    dimension->>'tool_version' LIKE :version_a
    OR dimension->>'tool_version' LIKE :version_b
  )
  AND dimension->>'test_name' LIKE :scenario_pattern
ORDER BY dimension->>'tool_version', created DESC;


-- 模板 4：多版本迭代（report_type=iteration）
-- 输入参数：:version_in_clause (e.g. "'%22.6.13%','%22.6.14%','%22.7.0%'")
-- 注意：在 db_query.py 中动态构造 OR 子句
SELECT task_id, dimension, results, results_key, created
FROM yunyu_test_results
WHERE (
    dimension->>'tool_version' LIKE '%22.6.13%'
    OR dimension->>'tool_version' LIKE '%22.6.14%'
    OR dimension->>'tool_version' LIKE '%22.7.0%'
  )
ORDER BY created ASC;


-- 模板 5：OR 关键词组合（test_name_keywords_or）
-- 必须用括号包裹 OR 表达式
SELECT task_id, dimension, results, results_key, created
FROM yunyu_test_results
WHERE task_id = '878fd4d4'
  AND (
    (dimension->>'test_name' LIKE '%集中式%' AND dimension->>'test_name' LIKE '%read_only%')
    OR
    (dimension->>'test_name' LIKE '%集中式%' AND dimension->>'test_name' LIKE '%point_select%')
  )
ORDER BY created DESC;


-- 模板 6：客制化 — 高并发场景
-- 输入参数：:threads_min (e.g. 512)
SELECT task_id, dimension, results, results_key, created
FROM yunyu_test_results
WHERE dimension->>'test_name' ~ '([0-9]+)threads'
  AND (regexp_match(dimension->>'test_name', '([0-9]+)threads'))[1]::int >= :threads_min
ORDER BY (regexp_match(dimension->>'test_name', '([0-9]+)threads'))[1]::int DESC;
