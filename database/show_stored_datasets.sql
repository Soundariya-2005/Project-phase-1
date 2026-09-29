USE insider_threat;

SELECT run_id, table_name, created_at, row_count
FROM dataset_runs
ORDER BY created_at DESC, run_id DESC;

SET @latest_table = (
    SELECT table_name
    FROM dataset_runs
    ORDER BY created_at DESC, run_id DESC
    LIMIT 1
);

SET @dataset_query = IF(
    @latest_table IS NULL,
    "SELECT 'No stored datasets found' AS message",
    CONCAT(
        'SELECT * FROM `',
        REPLACE(@latest_table, '`', '``'),
        '` LIMIT 100'
    )
);

PREPARE show_latest_dataset FROM @dataset_query;
EXECUTE show_latest_dataset;
DEALLOCATE PREPARE show_latest_dataset;
