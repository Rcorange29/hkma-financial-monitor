-- Values outside documented physical plausibility ranges.
-- Bounds are deliberately wide (see docs/DATA_CATALOG.md).  A row here is
-- FLAGGED for review; it is never deleted automatically.
SELECT o.dataset, o.metric, o.freq, o.date, o.value,
       m.hard_min, m.hard_max, m.unit
FROM observations o
JOIN metric_meta m
  ON m.dataset = o.dataset AND m.metric = o.metric
WHERE (m.hard_min IS NOT NULL AND o.value < m.hard_min)
   OR (m.hard_max IS NOT NULL AND o.value > m.hard_max)
ORDER BY o.dataset, o.metric, o.date;
