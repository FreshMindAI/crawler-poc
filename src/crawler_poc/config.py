from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRAWLER_", extra="ignore")

    database_url: str = "sqlite:///var/crawler.db"
    content_root: Path = Path("var/content")
    object_uri: str | None = None
    api_key: SecretStr = SecretStr("")
    workers: int = Field(default=4, ge=1, le=32)
    max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)
    max_wire_bytes: int = Field(default=5 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)
    request_timeout: float = Field(default=20, gt=0, le=120)
    max_attempts: int = Field(default=3, ge=1, le=5)
    origin_delay: float = Field(default=1, ge=0.1, le=60)
    lease_seconds: float = Field(default=120, ge=30, le=600)
    api_requests_per_minute: int = Field(default=60, ge=1, le=10000)
    max_pending_jobs: int = Field(default=10000, ge=1, le=1000000)
    browser_fallback: bool = False
    browser_channel: str = Field(default="msedge", pattern=r"^(msedge|chrome|chromium)$")
    browser_max_requests: int = Field(default=16, ge=1, le=64)
    user_agent: str = Field(
        default="CrawlerPOC/0.1 (+assignment research; respects robots.txt)",
        pattern=r"^[A-Za-z][A-Za-z0-9._-]*(?:/[^\r\n]*)?$",
        max_length=256,
    )
