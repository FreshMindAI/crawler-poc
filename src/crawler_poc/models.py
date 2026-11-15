import hashlib
import ipaddress
import re
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Outcome(StrEnum):
    SUCCESS = "success"
    POLICY_BLOCKED = "network_policy_blocked"
    ROBOTS_DISALLOWED = "robots_disallowed"
    ROBOTS_UNAVAILABLE = "robots_unavailable"
    TARGET_BLOCKED = "target_blocked"
    NOT_FOUND = "not_found"
    UNSUPPORTED = "unsupported_content"
    TOO_LARGE = "too_large"
    INSUFFICIENT = "insufficient_content"
    RETRY_EXHAUSTED = "retry_exhausted"
    CANCELED = "canceled"


def normalize_url(value: str) -> str:
    if not value or len(value) > 8192 or re.search(r"[\x00-\x20\x7f\\]", value):
        raise ValueError("URL contains whitespace, control characters, or is too long")
    try:
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            raise ValueError("Only absolute HTTP(S) URLs are supported")
        if parts.username is not None or parts.password is not None:
            raise ValueError("URL credentials are forbidden")
        scheme = parts.scheme.lower()
        host = parts.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        port = parts.port
        if port is not None and port not in {80, 443}:
            raise ValueError("Only ports 80 and 443 are supported")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not is_public_address(host):
            raise ValueError("Only public destinations are supported")
        if host in {"localhost", "metadata.google.internal"} or host.endswith(".localhost"):
            raise ValueError("Local/metadata destinations are forbidden")
        authority = f"[{host}]" if ":" in host else host
        if port is not None and port != (443 if scheme == "https" else 80):
            authority += f":{port}"
        return urlunsplit((scheme, authority, parts.path or "/", parts.query, ""))
    except (UnicodeError, ValueError) as exc:
        raise ValueError(str(exc)) from exc


def is_public_address(value: str) -> bool:
    address = ipaddress.ip_address(value.split("%")[0])
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    # Azure's platform virtual IP is globally classified, but is not a crawl target.
    if str(address) == "168.63.129.16":
        return False
    return address.is_global and not (
        address.is_multicast or address.is_reserved or address.is_unspecified
    )


def url_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


class Topic(BaseModel):
    phrase: str
    rank: int
    raw_score: float
    method: str = "yake"
    evidence: str = "body"
    ranking_score: float | None = None


class ExtractedPage(BaseModel):
    title: str | None = None
    description: str | None = None
    body: str = ""
    headings: list[str] = Field(default_factory=list)
    canonical_candidate: str | None = None
    language: str | None = None
    page_type: str = "unknown"
    topics: list[Topic] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    structured_types: list[str] = Field(default_factory=list)
    json_ld: list[dict[str, Any]] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    breadcrumbs: list[str] = Field(default_factory=list)
    image_alt: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    internal_links_count: int = 0
    external_links_count: int = 0
    author: str | None = None
    published_time: str | None = None
    word_count: int = 0
    page_type_evidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    extractor_version: str = "html-trafilatura-v3"
    classifier_version: str = "schema-rules-yake-weighted-v3"


class CrawlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str | None = None
    urls: list[str] | None = Field(default=None, min_length=1, max_length=100)
    generation: str = Field(default="initial", pattern=r"^[a-zA-Z0-9._-]{1,80}$")
    top_k: int = Field(default=5, ge=1, le=10)

    @model_validator(mode="after")
    def validate_urls(self) -> "CrawlRequest":
        if (self.url is None) == (self.urls is None):
            raise ValueError("Provide exactly one of url or urls")
        values = [self.url] if self.url is not None else self.urls
        assert values
        normalized = [normalize_url(item) for item in values]
        self.urls = normalized
        self.url = None
        return self
