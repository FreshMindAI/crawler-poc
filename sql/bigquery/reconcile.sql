-- Replace only the trusted deployment identifier; bind @batch_id as STRING.
SELECT count(*) AS rows, count(DISTINCT event_id) AS distinct_events
FROM `PROJECT.DATASET.crawl_events`
WHERE publish_batch_id = @batch_id;

