from pathlib import Path

import pytest

from crawler_poc.extraction import extract_page

FIXTURES = Path(__file__).parent / "fixtures"


def test_product_metadata_and_topics() -> None:
    page = extract_page((FIXTURES / "product.html").read_bytes(), "https://example.com/item")
    assert page.page_type == "product"
    assert page.title == "Compact two slice toaster"
    assert page.description == "A compact toaster for a modern kitchen."
    assert any("toaster" in topic.phrase.lower() for topic in page.topics)
    assert "Product" in page.structured_types
    assert "crumb tray" in page.body
    assert len(page.topics) <= 5


def test_document_title_excludes_svg_accessibility_titles() -> None:
    source = (FIXTURES / "product.html").read_bytes()
    source = source.replace(b"</body>", b"<svg><title>Close icon</title><path /></svg></body>")
    page = extract_page(source, "https://example.com/item")
    assert page.title == "Compact two slice toaster"


def test_product_facts_outrank_generic_article_wrapper() -> None:
    source = (
        b"<html><head><title>Portable field recorder</title></head><body>"
        b"<article><h1>Portable field recorder</h1>"
        b"<p>A battery-powered recorder for clear outdoor interviews and voice notes.</p>"
        b"<table><tr><th>SKU</th><td>REC-7</td></tr>"
        b"<tr><th>Price (including tax)</th><td>45.00</td></tr></table>"
        b"</article></body></html>"
    )
    page = extract_page(source, "https://example.com/recorder")
    assert page.page_type == "product"
    assert page.metadata["product_evidence"] == "identifier-and-price-fields"
    editorial = source.replace(b"<th>SKU</th>", b"<th>Example</th>")
    assert extract_page(editorial, "https://example.com/editorial").page_type == "article"


def test_microdata_product_without_jsonld() -> None:
    source = (
        b"<html><head><title>Field notebook</title></head><body>"
        b'<article itemscope itemtype="https://schema.org/Product">'
        b"<h1>Field notebook</h1><p>A durable notebook for recording measurements"
        b" and field observations in every season.</p></article></body></html>"
    )
    assert extract_page(source, "https://example.com/notebook").page_type == "product"


def test_structured_listing_preserves_record_names_and_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "crawler_poc.extraction.trafilatura.extract",
        lambda *args, **kwargs: "A reference directory of regional capitals and populations.",
    )
    records = "".join(
        f"<div><h3>Region {index}</h3><div>Capital: City {index}</div>"
        f"<div>Population: {10000 + index}</div></div>"
        for index in range(20)
    )
    source = (
        "<html><head><title>Regional statistics</title></head><body>"
        "<nav>Account Sign in Home</nav><main><h1>Regional statistics</h1>"
        "<p>A reference directory of regional capitals and populations.</p>"
        f"{records}</main><footer>Copyright directory navigation</footer></body></html>"
    )
    page = extract_page(source.encode(), "https://example.com/regions")
    for index in range(20):
        assert f"Region {index}" in page.body
        assert f"City {index}" in page.body
        assert str(10000 + index) in page.body
    assert "Account Sign in" not in page.body
    assert "Copyright directory navigation" not in page.body
    assert "structured_content_fallback" in page.warnings


def test_dialog_headings_do_not_pollute_article_topics() -> None:
    source = (
        b"<html><head><title>Orchard soil health</title></head><body>"
        b'<div role="dialog"><h2>Magenta download installer</h2>'
        b"<p>Magenta download installer. Magenta download installer.</p></div>"
        b"<main><article><h1>Orchard soil health</h1>"
        b"<p>Orchard soil health improves with compost and careful irrigation."
        b" Healthy orchard trees need balanced nutrients and drainage.</p>"
        b"</article></main></body></html>"
    )
    page = extract_page(source, "https://example.com/orchards")
    assert page.headings == ["Orchard soil health"]
    assert "Magenta" not in page.body
    assert all("magenta" not in topic.phrase.casefold() for topic in page.topics)


def test_article_and_invalid_jsonld() -> None:
    source = (FIXTURES / "article.html").read_bytes()
    source = source.replace(b"</head>", b'<script type="application/ld+json">{bad}</script></head>')
    page = extract_page(source, "https://example.com/article", top_k=3)
    assert page.page_type == "article"
    assert len(page.topics) == 3
    assert "Home Store Account" not in page.body


def test_non_english_and_script_only_are_honest() -> None:
    page = extract_page(
        b'<html lang="fr"><body><p>' + b"French text not evaluated. " * 10 + b"</p></body></html>",
        "https://example.com/",
    )
    assert page.topics == []
    assert "topics_unsupported_language" in page.warnings
    shell = extract_page(
        b"<html><body><script>runApp()</script></body></html>", "https://example.com"
    )
    assert shell.page_type == "unknown"
    assert shell.topics == []
    assert "javascript_only" in shell.warnings


def test_structured_metadata_links_and_homepage_are_generic() -> None:
    source = b"""<html lang="en"><head><title>Field supplies</title>
    <meta name="keywords" content="orchards, tools">
    <script type="application/ld+json">
    {"@type":"WebSite","author":{"name":"Field team"},"datePublished":"2025-01-02",
     "subjectOf":{"@type":"BreadcrumbList","itemListElement":[{"name":"Field guide"}]}}
    </script></head><body><main><h1>Field supplies</h1><h3>Orchard equipment</h3>
    <p>Explore durable field supplies, orchard tools and practical guides for every season.</p>
    <a href="/tools">Tools</a><a href="https://elsewhere.example/guide">Guide</a>
    <a href="javascript:alert(1)">Ignore</a><a href="http://[invalid">Malformed</a>
    <img alt="Pruning tools"></main></body></html>"""
    page = extract_page(source, "https://example.com/")
    assert page.page_type == "home"
    assert page.page_type_evidence == ["root-path"]
    assert page.json_ld[0]["@type"] == "WebSite"
    assert page.keywords == ["orchards", "tools"]
    assert page.author == "Field team"
    assert page.published_time == "2025-01-02"
    assert page.breadcrumbs == ["Field guide"]
    assert "Orchard equipment" in page.headings
    assert page.image_alt == ["Pruning tools"]
    assert (page.internal_links_count, page.external_links_count) == (1, 1)
    assert page.word_count == len(page.body.split())


def test_topic_ranking_uses_location_not_only_yake_score(monkeypatch: pytest.MonkeyPatch) -> None:
    class Keywords:
        def extract_keywords(self, source: str) -> list[tuple[str, float]]:
            return [("background detail", 0.1), ("orchard health", 0.2)]

    monkeypatch.setattr("crawler_poc.extraction._keywords", lambda: Keywords())
    page = extract_page(
        b"<html><head><title>Orchard health</title></head><body><main>"
        b"<h1>Orchard health</h1><p>Background detail explains orchard health, compost,"
        b" irrigation and seasonal nutrient management.</p></main></body></html>",
        "https://example.com/guide",
    )
    assert page.topics[0].phrase == "orchard health"
    assert page.topics[0].raw_score == 0.2
    assert page.topics[0].ranking_score < page.topics[1].ranking_score
    assert page.topics[0].evidence == "title+heading"


def test_jsonld_output_is_bounded_and_finite() -> None:
    import json

    source = (
        "<html><head><script type='application/ld+json'>"
        '{"@type":"Article","huge":1e999,"description":"'
        + "x" * 5000
        + '"}</script></head><body><p>'
        + "Readable field notes. " * 10
        + "</p></body></html>"
    )
    page = extract_page(source.encode(), "https://example.com/notes")
    assert page.json_ld[0]["huge"] is None
    assert len(page.json_ld[0]["description"]) == 2000
    json.dumps(page.json_ld, allow_nan=False)


def test_topics_deduplicate_nested_phrases_without_losing_short_acronyms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Keywords:
        def extract_keywords(self, source: str) -> list[tuple[str, float]]:
            return [
                ("Black Friday Deal", 0.1),
                ("Friday Deal", 0.2),
                ("Black Friday", 0.3),
                ("Publisher Business", 0.11),
                ("AI", 0.2),
                ("seasonal offers", 0.4),
            ]

    monkeypatch.setattr("crawler_poc.extraction._keywords", lambda: Keywords())
    page = extract_page(
        b"<html><head><title>Retail and AI | Publisher Business</title>"
        b"<meta property='og:site_name' content='Publisher'></head>"
        b"<body><article><p>Black Friday Deal analysis looks at seasonal offers and"
        b" AI tools for improving retail planning.</p></article></body></html>",
        "https://example.com/retail",
    )
    phrases = {topic.phrase for topic in page.topics}
    assert "AI" in phrases
    assert "Black Friday Deal" in phrases
    assert not phrases & {"Friday Deal", "Black Friday", "Publisher Business"}
