-- Day-to-day change for a daily interest-rate series.
-- Window functions (LAG) make "previous value" easy to express in SQL.
-- Replace the metric to inspect another series.
WITH s AS (
    SELECT date, value,
           LAG(value) OVER (ORDER BY date) AS prev_value,
           LAG(date)  OVER (ORDER BY date) AS prev_date
    FROM observations
    WHERE dataset = 'interbank_daily'
      AND metric  = 'disc_win_base_rate'
      AND freq    = 'daily'
)
SELECT date, prev_date, prev_value, value,
       ROUND(value - prev_value, 4) AS change
FROM s
WHERE prev_value IS NOT NULL
  AND ABS(value - prev_value) > 0
ORDER BY date;
