import asyncio
import contextlib
import json
import logging
import random
import time
from typing import Any

from lxml.etree import ParserError

from crawler_poc.config import Settings
from crawler_poc.fetching import FetchError, SafeFetcher
from crawler_poc.models import Outcome
from crawler_poc.pipeline import CrawlPipeline
from crawler_poc.storage import ContentStore, Store

logger = logging.getLogger(__name__)


class Worker:
    def __init__(
        self, settings: Settings, store: Store, content: ContentStore, fetcher: SafeFetcher
    ) -> None:
        self.settings, self.store, self.content, self.fetcher = settings, store, content, fetcher
        self.pipeline = CrawlPipeline(settings, fetcher)

    async def _heartbeat(self, job: dict[str, Any]) -> None:
        while True:
            await asyncio.sleep(self.settings.lease_seconds / 3)
            valid = await asyncio.to_thread(
                self.store.heartbeat, job["id"], job["token"], self.settings.lease_seconds
            )
            if not valid:
                return

    async def once(self) -> bool:
        job = await asyncio.to_thread(self.store.claim, self.settings.lease_seconds)
        if job is None:
            return False
        pulse = asyncio.create_task(self._heartbeat(job))
        started = time.perf_counter()
        try:
            if job["attempts"] > self.settings.max_attempts:
                raise FetchError(Outcome.RETRY_EXHAUSTED, "worker_attempt_budget")
            analyzed = await self.pipeline.analyze(job["url"], job["top_k"])
            fetched, page = analyzed.fetched, analyzed.page
            raw_ref, body_ref = await asyncio.gather(
                asyncio.to_thread(self.content.put, fetched.body),
                asyncio.to_thread(self.content.put, page.body.encode()),
            )
            result = page.model_dump(exclude={"body"})
            if analyzed.initial_body is not None:
                result["metadata"]["initial_raw_ref"] = await asyncio.to_thread(
                    self.content.put, analyzed.initial_body
                )
            result["metadata"]["timings_ms"] = json.dumps(analyzed.timings_ms)
            result["metadata"]["extracted_details_json"] = json.dumps(
                {
                    key: result[key]
                    for key in (
                        "json_ld",
                        "keywords",
                        "breadcrumbs",
                        "image_alt",
                        "links",
                        "internal_links_count",
                        "external_links_count",
                        "author",
                        "published_time",
                        "word_count",
                        "page_type_evidence",
                        "topics",
                    )
                },
                ensure_ascii=True,
            )
            result.update(
                outcome="success",
                final_url=fetched.final_url,
                http_status=fetched.http_status,
                content_type=fetched.content_type,
                raw_ref=raw_ref,
                body_ref=body_ref,
                body_preview=page.body[:16000],
                body_characters=len(page.body),
                raw_bytes=len(fetched.body),
                fetch_method=fetched.fetch_method,
                timings_ms=analyzed.timings_ms,
            )
            await asyncio.to_thread(self.store.finish, job, result)
        except FetchError as exc:
            if exc.retryable and job["attempts"] < self.settings.max_attempts:
                delay = max(exc.retry_after, min(30, 2 ** job["attempts"] + random.random()))
                await asyncio.to_thread(self.store.retry, job["id"], job["token"], delay)
            else:
                result = exc.as_result()
                result["timings_ms"] = {"total": round((time.perf_counter() - started) * 1000, 3)}
                result["metadata"]["timings_ms"] = json.dumps(result["timings_ms"])
                await asyncio.to_thread(self.store.finish, job, result)
        except (ParserError, ValueError, UnicodeError):
            await asyncio.to_thread(
                self.store.finish,
                job,
                {"outcome": Outcome.UNSUPPORTED.value, "reason": "invalid_html"},
            )
        except asyncio.CancelledError:
            await asyncio.to_thread(self.store.retry, job["id"], job["token"], 0)
            raise
        finally:
            pulse.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pulse
        return True

    async def run(self, stop_when_idle: bool = False) -> None:
        while True:
            try:
                worked = await self.once()
                if not worked:
                    if stop_when_idle:
                        counts = await asyncio.to_thread(self.store.counts)
                        if not counts.get("queued", 0) and not counts.get("running", 0):
                            return
                    await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.error("worker_internal_error; job lease will be recovered")
                await asyncio.sleep(1)
