-- Bind the publication ID with the Trino client, not string concatenation.
SELECT count(*) AS rows, count(DISTINCT event_id) AS distinct_events
FROM iceberg.crawler.crawl_events
WHERE publish_batch_id = ?;

