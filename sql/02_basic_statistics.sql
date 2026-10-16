-- Basic descriptive statistics per series (SQLite has no STDDEV;
-- variability is summarised with MIN/MAX and a simple average).
-- Useful for a quick sanity check before charting.
SELECT dataset,
       metric,
       freq,
       COUNT(*)               AS n,
       MIN(date)              AS first_date,
       MAX(date)              AS last_date,
       ROUND(MIN(value), 4)   AS min_value,
       ROUND(AVG(value), 4)   AS avg_value,
       ROUND(MAX(value), 4)   AS max_value,
       ROUND(MAX(value) - MIN(value), 4) AS range_value
FROM observations
GROUP BY dataset, metric, freq
ORDER BY dataset, metric, freq;
