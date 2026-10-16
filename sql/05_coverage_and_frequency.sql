-- Coverage per dataset / frequency: how many series and dates exist, and
-- how many value rows.  Confirm the expected number of metric columns
-- (fx=6, interbank=7, monetary=19).
SELECT dataset,
       freq,
       COUNT(DISTINCT metric) AS metric_count,
       COUNT(DISTINCT date)   AS date_count,
       COUNT(*)               AS value_rows,
       MIN(date)              AS first_date,
       MAX(date)              AS last_date
FROM observations
GROUP BY dataset, freq
ORDER BY dataset, freq;
