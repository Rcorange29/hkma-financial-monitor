-- Duplicate detection on the composite primary key.
-- This must always return 0 rows.  The upsert primary key
-- (dataset, metric, freq, date) is what guarantees idempotency.
SELECT dataset, metric, freq, date, COUNT(*) AS n
FROM observations
GROUP BY dataset, metric, freq, date
HAVING COUNT(*) > 1;
