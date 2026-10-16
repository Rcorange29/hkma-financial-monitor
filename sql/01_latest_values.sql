-- Most recent observation per (dataset, metric, freq).
-- Run with:  sqlite3 data/processed/hkma.db < sql/01_latest_values.sql
SELECT m.dataset,
       m.metric,
       m.freq,
       o.label,
       o.unit,
       o.date  AS latest_date,
       o.value AS latest_value
FROM (
    SELECT dataset, metric, freq, MAX(date) AS max_date
    FROM observations
    GROUP BY dataset, metric, freq
) m
JOIN observations o
  ON o.dataset = m.dataset
 AND o.metric  = m.metric
 AND o.freq    = m.freq
 AND o.date    = m.max_date
ORDER BY m.dataset, o.category, m.metric;
