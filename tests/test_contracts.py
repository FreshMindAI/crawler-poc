import pytest
from pydantic import ValidationError

from crawler_poc.models import CrawlRequest, is_public_address, normalize_url


def test_normalization_preserves_query_semantics() -> None:
    assert normalize_url("HTTPS://Example.COM:443/a?b=2&a=1#x") == ("https://example.com/a?b=2&a=1")
    assert normalize_url("https://example.com/a?x=1&x=2") != normalize_url(
        "https://example.com/a?x=2&x=1"
    )


@pytest.mark.parametrize(
    "value",
    [
        "file:///etc/passwd",
        "https://user:pass@example.com/",
        "http://127.0.0.1/",
        "http://169.254.169.254/",
        "http://[::ffff:127.0.0.1]/",
        "https://example.com:8080/",
        "https://example.com\\@localhost/",
        "https://example.com/\nheader",
        "http://localhost/",
    ],
)
def test_unsafe_input_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_url(value)


def test_special_addresses() -> None:
    assert is_public_address("8.8.8.8")
    assert not is_public_address("100.64.0.1")
    assert not is_public_address("::ffff:10.0.0.1")
    assert not is_public_address("224.0.0.1")
    assert not is_public_address("168.63.129.16")


def test_request_bounds_and_ambiguity() -> None:
    assert CrawlRequest(url="https://example.com").urls == ["https://example.com/"]
    with pytest.raises(ValidationError):
        CrawlRequest(url="https://example.com", urls=["https://example.org"])
    with pytest.raises(ValidationError):
        CrawlRequest(urls=["https://example.com"] * 101)
