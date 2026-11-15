import json
import math
import re
from functools import lru_cache
from typing import Any
from urllib.parse import urljoin, urlsplit

import trafilatura
import yake
from lxml import etree, html

from crawler_poc.models import ExtractedPage, Topic


def _clean(value: str, limit: int = 4096) -> str:
    return re.sub(r"\s+", " ", value).strip()[:limit]


@lru_cache(maxsize=1)
def _keywords() -> Any:
    return yake.KeywordExtractor(lan="en", n=3, top=30, dedupLim=0.8)


def _visible_text(scope: Any) -> str:
    lines: list[str] = []
    size = 0
    for value in scope.itertext():
        line = _clean(value, 250000)
        if line:
            lines.append(line)
            size += len(line) + 1
            if size >= 250000:
                break
    return "\n".join(lines)[:250000]


def _bounded_json(value: Any, budget: list[int], depth: int = 0) -> Any:
    budget[0] -= 1
    if depth > 8 or budget[0] < 0:
        return None
    if isinstance(value, dict):
        return {
            str(key)[:100]: _bounded_json(child, budget, depth + 1)
            for key, child in list(value.items())[:40]
        }
    if isinstance(value, list):
        return [_bounded_json(child, budget, depth + 1) for child in value[:40]]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return _clean(value, 2000) if isinstance(value, str) else value


def _reject_json_constant(value: str) -> Any:
    raise ValueError("Non-finite JSON number")


def extract_page(content: bytes, url: str, top_k: int = 5) -> ExtractedPage:
    parser = html.HTMLParser(no_network=True, recover=True)
    tree = html.fromstring(content, parser=parser)
    metadata: dict[str, str] = {}
    for node in tree.xpath("//meta[@content]")[:200]:
        key = (node.get("name") or node.get("property") or "").lower()
        if key and key not in metadata:
            metadata[key] = _clean(node.get("content", ""))
    title = _clean(" ".join(tree.xpath("//head/title[1]/text()"))) or metadata.get("og:title")
    description = metadata.get("description") or metadata.get("og:description")
    canonical = tree.xpath(
        "//link[contains(concat(' ',normalize-space(@rel),' '),' canonical ')]/@href"
    )
    kinds: set[str] = set()
    json_ld: list[dict[str, Any]] = []
    breadcrumbs: list[str] = []
    authors: list[str] = []
    published: list[str] = []
    structured_names: list[str] = []
    json_budget = 32768

    def collect_types(value: Any, depth: int = 0) -> None:
        if depth > 12:
            return
        if isinstance(value, dict):
            kind = value.get("@type", [])
            if isinstance(kind, str):
                kinds.add(kind)
            elif isinstance(kind, list):
                kinds.update(item for item in kind if isinstance(item, str))
            author = value.get("author")
            for item in (author if isinstance(author, list) else [author])[:10]:
                name = item.get("name") if isinstance(item, dict) else item
                if isinstance(name, str) and len(authors) < 10:
                    authors.append(_clean(name, 200))
            if isinstance(value.get("datePublished"), str) and not published:
                published.append(_clean(value["datePublished"], 100))
            types = kind if isinstance(kind, list) else [kind]
            if any(
                name in types
                for name in (
                    "Product",
                    "Article",
                    "NewsArticle",
                    "BlogPosting",
                    "WebSite",
                    "CollectionPage",
                )
            ):
                for key in ("name", "headline", "keywords"):
                    if isinstance(value.get(key), str) and len(structured_names) < 20:
                        structured_names.append(_clean(value[key], 500))
            if "BreadcrumbList" in types:
                elements = value.get("itemListElement", [])
                for item in elements[:20] if isinstance(elements, list) else []:
                    if isinstance(item, dict):
                        child = item.get("item")
                        name = item.get("name") or (
                            child.get("name") if isinstance(child, dict) else None
                        )
                        if isinstance(name, str) and len(breadcrumbs) < 20:
                            breadcrumbs.append(_clean(name, 200))
            for key, child in value.items():
                if key != "@context":
                    collect_types(child, depth + 1)
        elif isinstance(value, list):
            for child in value[:100]:
                collect_types(child, depth + 1)

    for node in tree.xpath("//script[@type='application/ld+json']")[:20]:
        source = node.text or ""
        if len(source) <= 65536:
            try:
                document = json.loads(source, parse_constant=_reject_json_constant)
                collect_types(document)
                for item in (document if isinstance(document, list) else [document])[:20]:
                    if isinstance(item, dict) and len(json_ld) < 20:
                        candidate = _bounded_json(item, [1000])
                        size = len(json.dumps(candidate, ensure_ascii=True))
                        if size <= json_budget:
                            json_ld.append(candidate)
                            json_budget -= size
            except (ValueError, RecursionError):
                pass
    for itemtype in tree.xpath("//*[@itemtype]/@itemtype")[:100]:
        kinds.update(itemtype.split()[:10])
    labels = {_clean(node.text_content(), 100).casefold() for node in tree.xpath("//th|//dt")[:200]}
    commerce_fields = any(
        re.fullmatch(r"(?:sku|upc|gtin(?:-\d+)?|isbn(?:-\d+)?|mpn)", label) for label in labels
    ) and any(re.match(r"price(?:\s|\(|$)", label) for label in labels)
    script_count = len(tree.xpath("//script"))
    challenge = bool(
        tree.xpath(
            "//form[contains(translate(@action,'CAPTCHA','captcha'),'captcha')]"
            "|//input[contains(translate(@id,'CAPTCHA','captcha'),'captcha')]"
        )
    )
    if not breadcrumbs:
        breadcrumbs = [
            _clean(node.text_content(), 200)
            for node in tree.xpath(
                "//nav[@aria-label='breadcrumb' or @aria-label='Breadcrumb']//a"
            )[:20]
        ]
    image_alt = [_clean(value, 200) for value in tree.xpath("//img[@alt]/@alt")[:30] if value]
    links: list[str] = []
    internal_links, external_links, scanned_links = 0, 0, 0
    for node in tree.iter("a"):
        scanned_links += 1
        if scanned_links > 1000:
            break
        href = node.get("href", "")
        if not href or href.startswith("#"):
            continue
        try:
            candidate = urljoin(url, href)
            parts = urlsplit(candidate)
            if (
                parts.scheme not in {"http", "https"}
                or not parts.hostname
                or parts.username is not None
                or parts.password is not None
                or len(candidate) > 1024
            ):
                continue
            if parts.hostname == urlsplit(url).hostname:
                internal_links += 1
            else:
                external_links += 1
            if len(links) < 50:
                links.append(candidate)
        except ValueError:
            continue
    for node in tree.xpath(
        "//script|//style|//nav|//footer|//noscript|//svg|//template|//dialog"
        "|//*[@role='navigation' or @role='dialog' or @role='contentinfo' or @aria-hidden='true']"
    ):
        if node.getparent() is not None:
            node.drop_tree()
    scopes = tree.xpath("//main|//*[@role='main']")[:20]
    articles = tree.xpath("//article")
    if not scopes and len(articles) == 1:
        scopes = articles
    scope = (
        max(scopes, key=lambda node: len(node.text_content()))
        if scopes
        else (tree.xpath("//body") or [tree])[0]
    )
    headings = [_clean(node.text_content(), 500) for node in scope.xpath(".//h1|.//h2|.//h3")[:30]]
    decoded = etree.tostring(tree, encoding="unicode", method="html")
    body = trafilatura.extract(
        decoded, include_comments=False, include_tables=True, favor_precision=True
    )
    visible = _visible_text(scope)
    repeated_blocks = len(scope.xpath(".//li|.//tr|.//h2|.//h3"))
    structured_fallback = repeated_blocks >= 5 and len(visible) > max(400, 4 * len(body or ""))
    body_method = "trafilatura-precision"
    if structured_fallback:
        body = visible
        body_method = "structured-visible-text"
    if not body:
        body = visible
        body_method = "visible-text"
    body = body.strip()[:250000]
    language = tree.get("lang") or metadata.get("og:locale")
    normalized_types = {kind.rsplit("/", 1)[-1].lower() for kind in kinds}
    page_type, page_type_evidence = "other", []
    url_path = urlsplit(url).path.lower()
    if (
        "product" in normalized_types
        or metadata.get("og:type") == "product"
        or commerce_fields
        or "/dp/" in url_path
        or "/gp/product/" in url_path
    ):
        page_type = "product"
        page_type_evidence = ["structured-product" if not commerce_fields else "product-facts"]
    elif normalized_types & {"article", "newsarticle", "blogposting"}:
        page_type = "article"
        page_type_evidence = ["structured-article"]
    elif len(body) < 40:
        page_type = "unknown"
    elif urlsplit(url).path in {"", "/"} and not urlsplit(url).query:
        page_type, page_type_evidence = "home", ["root-path"]
    elif normalized_types & {"collectionpage", "itemlist"}:
        page_type = "category"
        page_type_evidence = ["structured-collection"]
    elif tree.xpath("//article"):
        page_type, page_type_evidence = "article", ["article-element"]
    warnings: list[str] = []
    if structured_fallback:
        warnings.append("structured_content_fallback")
    if len(body) < 40:
        warnings.append("javascript_only" if script_count else "insufficient_content")
    if challenge:
        warnings.append("challenge_detected")
    if scanned_links > 1000:
        warnings.append("links_scan_truncated")
    language_supported = not language or language.lower().split("-")[0].split("_")[0] == "en"
    topics: list[Topic] = []
    if len(body) >= 40 and language_supported:
        topic_title = title
        publishers: set[str] = set()
        site_name = metadata.get("og:site_name", "")
        if site_name and page_type != "home":
            publishers.add(site_name.casefold())
            for separator in (" | ", " - "):
                before, divider, suffix = (topic_title or "").rpartition(separator)
                if divider and re.search(
                    r"(?<!\w)" + re.escape(site_name.casefold()) + r"(?!\w)", suffix.casefold()
                ):
                    topic_title = before
                    publishers.add(suffix.casefold())
        segments = [
            topic_title,
            description,
            *headings[:5],
            " ".join(breadcrumbs),
            " ".join(structured_names),
            metadata.get("keywords"),
            *body[:30000].splitlines(),
        ]
        weighted = ".\n".join(segment.rstrip(".!? ") for segment in segments if segment)
        candidates: list[tuple[str, float, float, str]] = []
        for phrase, score in _keywords().extract_keywords(weighted):
            phrase = _clean(phrase, 100)
            short_acronym = len(phrase) == 2 and phrase.isupper() and phrase.isalpha()
            if (
                phrase
                and (len(phrase) > 2 or short_acronym)
                and phrase.casefold() not in publishers
            ):
                evidence, weight = [], 1
                for label, text, boost in (
                    ("title", topic_title, 3),
                    ("heading", " ".join(headings[:5]), 2),
                    ("description", description, 1),
                    ("breadcrumb", " ".join(breadcrumbs), 1),
                    ("json_ld", " ".join(structured_names), 1),
                    ("keywords", metadata.get("keywords"), 1),
                ):
                    if text and re.search(
                        r"(?<!\w)" + re.escape(phrase.casefold()) + r"(?!\w)",
                        text.casefold(),
                    ):
                        evidence.append(label)
                        weight += boost
                candidates.append(
                    (phrase, float(score), float(score) / weight, "+".join(evidence) or "body")
                )
        selected_tokens: list[set[str]] = []
        for phrase, raw, adjusted, evidence_text in sorted(candidates, key=lambda item: item[2]):
            tokens = set(re.findall(r"\w+", phrase.casefold()))
            if not tokens or any(tokens <= prior or prior <= tokens for prior in selected_tokens):
                continue
            selected_tokens.append(tokens)
            topics.append(
                Topic(
                    phrase=phrase,
                    rank=len(topics) + 1,
                    raw_score=raw,
                    ranking_score=adjusted,
                    method="yake-metadata-weighted",
                    evidence=evidence_text,
                )
            )
            if len(topics) >= top_k:
                break
    elif not language_supported:
        warnings.append("topics_unsupported_language")
    return ExtractedPage(
        title=title or None,
        description=description,
        body=body,
        headings=headings,
        canonical_candidate=urljoin(url, canonical[0]) if canonical else None,
        language=language,
        page_type=page_type,
        topics=topics,
        metadata={
            **{
                key: value for key, value in metadata.items() if key.startswith(("og:", "twitter:"))
            },
            "body_extraction": body_method,
            "content_scope": scope.tag,
            **({"product_evidence": "identifier-and-price-fields"} if commerce_fields else {}),
        },
        structured_types=sorted(kinds)[:30],
        json_ld=json_ld,
        keywords=[
            _clean(value, 100)
            for value in metadata.get("keywords", "").split(",")[:30]
            if value.strip()
        ],
        breadcrumbs=breadcrumbs,
        image_alt=image_alt,
        links=links,
        internal_links_count=internal_links,
        external_links_count=external_links,
        author=metadata.get("author") or (", ".join(dict.fromkeys(authors)) or None),
        published_time=metadata.get("article:published_time")
        or (published[0] if published else None),
        word_count=len(body.split()),
        page_type_evidence=page_type_evidence,
        warnings=warnings,
    )
