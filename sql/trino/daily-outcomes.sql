-- Bound the observed_at range for Iceberg day-partition pruning. Capture EXPLAIN remotely.
SELECT date(observed_at) AS observed_day, outcome, count(*) AS events
FROM iceberg.crawler.crawl_events
WHERE observed_at >= TIMESTAMP '2026-11-01 00:00:00 UTC'
  AND observed_at < TIMESTAMP '2026-12-01 00:00:00 UTC'
GROUP BY date(observed_at), outcome;
