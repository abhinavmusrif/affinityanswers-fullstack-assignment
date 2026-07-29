#!/usr/bin/env python3
"""Scrape MDComputers search results into JSON or CSV.

The scraper is intentionally conservative: it uses a browser-like user agent,
retries transient failures, limits pagination, and can optionally enrich each
search result from its product page.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://mdcomputers.in/"
DEFAULT_TIMEOUT = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


class ScraperError(RuntimeError):
    """Raised when the site cannot be fetched or parsed safely."""


@dataclass(slots=True)
class Product:
    name: str
    price: str | None
    original_price: str | None
    discount: str | None
    availability: str | None
    url: str
    image_url: str | None
    model: str | None = None
    brand: str | None = None
    specifications: dict[str, str] | None = None


def clean_text(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def first_text(node: Tag, selectors: Sequence[str]) -> str | None:
    for selector in selectors:
        found = node.select_one(selector)
        if found:
            value = clean_text(found.get_text(" ", strip=True))
            if value:
                return value
    return None


def first_attr(node: Tag, selectors: Sequence[str], attribute: str) -> str | None:
    for selector in selectors:
        found = node.select_one(selector)
        if found:
            value = clean_text(found.get(attribute))
            if value:
                return value
    return None


def build_session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_html(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, str | int] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    try:
        response = session.get(url, params=params, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ScraperError(f"Request failed for {url}: {exc}") from exc

    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type.lower() and not response.text.lstrip().startswith("<"):
        raise ScraperError(
            f"Unexpected response type from {response.url}: {content_type or 'unknown'}"
        )
    return response.text


def find_product_cards(soup: BeautifulSoup) -> list[Tag]:
    """Return one non-overlapping set of product cards.

    MDComputers has changed themes over time, so selectors are ordered from
    specific to generic. The first selector yielding cards is used to avoid
    duplicate nested matches.
    """

    selectors = (
        "#content .product-layout",
        "#content .product-thumb",
        ".main-products .product-layout",
        ".products-grid .product-item",
        ".product-grid .product-item",
        "article.product",
        "[data-product-id]",
    )
    for selector in selectors:
        cards = [card for card in soup.select(selector) if isinstance(card, Tag)]
        if cards:
            return cards
    return []


def extract_product(card: Tag, base_url: str = BASE_URL) -> Product | None:
    name_anchor = None
    for selector in (
        "h4 a",
        "h3 a",
        ".name a",
        ".product-name a",
        ".caption a",
        ".description a[href]",
        "a[href*='product_id']",
    ):
        candidate = card.select_one(selector)
        if candidate and clean_text(candidate.get_text(" ", strip=True)):
            name_anchor = candidate
            break

    if not name_anchor:
        return None

    name = clean_text(name_anchor.get_text(" ", strip=True))
    href = clean_text(name_anchor.get("href"))
    if not name or not href:
        return None

    price = first_text(card, (".price-new", ".special-price", ".price .current-price"))
    original_price = first_text(card, (".price-old", ".old-price", "del"))
    if not price:
        price_container = card.select_one(".price, [class*='price']")
        if price_container:
            price_text = clean_text(price_container.get_text(" ", strip=True))
            if price_text:
                amounts = re.findall(r"₹\s?[\d,]+(?:\.\d{1,2})?", price_text)
                price = amounts[-1] if amounts else price_text
                if len(amounts) > 1 and not original_price:
                    original_price = amounts[0]

    discount = first_text(card, (".discount", ".sale", ".product-label", ".label-sale"))
    availability = first_text(card, (".stock", ".availability", ".product-stock"))
    if not availability:
        cart_text = first_text(card, ("button[onclick*='cart']", ".button-cart", ".btn-cart"))
        if cart_text and "add to cart" in cart_text.lower():
            availability = "In stock"

    image = first_attr(
        card,
        (".image img", ".product-image img", "img"),
        "data-src",
    ) or first_attr(card, (".image img", ".product-image img", "img"), "src")

    return Product(
        name=name,
        price=price,
        original_price=original_price,
        discount=discount,
        availability=availability,
        url=urljoin(base_url, href),
        image_url=urljoin(base_url, image) if image else None,
    )


def parse_search_page(html: str, base_url: str = BASE_URL) -> list[Product]:
    soup = BeautifulSoup(html, "html.parser")
    products: list[Product] = []
    seen_urls: set[str] = set()

    for card in find_product_cards(soup):
        product = extract_product(card, base_url)
        if product and product.url not in seen_urls:
            products.append(product)
            seen_urls.add(product.url)

    return products


def normalized_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def parse_product_details(html: str) -> dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    specifications: dict[str, str] = {}
    metadata: dict[str, str] = {}

    for row in soup.select("#tab-specification tr, .table-bordered tr, .product-specs tr"):
        cells = [clean_text(cell.get_text(" ", strip=True)) for cell in row.select("th, td")]
        cells = [cell for cell in cells if cell]
        if len(cells) >= 2:
            specifications[cells[0]] = " | ".join(cells[1:])

    for item in soup.select(".list-unstyled li, .product-info li"):
        text = clean_text(item.get_text(" ", strip=True))
        if text and ":" in text:
            key, value = text.split(":", 1)
            key, value = clean_text(key), clean_text(value)
            if key and value:
                metadata.setdefault(key, value)

    combined = {**specifications, **metadata}
    normalized = {normalized_label(key): value for key, value in combined.items()}

    def lookup(*keys: str) -> str | None:
        for key in keys:
            if key in normalized:
                return normalized[key]
        return None

    availability = lookup("availability", "stock status")
    if not availability:
        availability = first_text(soup, (".stock", ".availability", ".product-stock"))

    return {
        "model": lookup("model", "product code", "sku"),
        "brand": lookup("brand", "manufacturer"),
        "availability": availability,
        "specifications": specifications or None,
    }


def enrich_product(
    product: Product,
    session: requests.Session,
    *,
    timeout: int,
    delay: float,
) -> Product:
    if delay > 0:
        time.sleep(delay)
    html = fetch_html(session, product.url, timeout=timeout)
    details = parse_product_details(html)
    product.model = details["model"] if isinstance(details["model"], str) else None
    product.brand = details["brand"] if isinstance(details["brand"], str) else None
    product.availability = (
        details["availability"]
        if isinstance(details["availability"], str)
        else product.availability
    )
    specs = details["specifications"]
    product.specifications = specs if isinstance(specs, dict) else None
    return product


def scrape(
    search_term: str,
    *,
    pages: int = 1,
    include_details: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    delay: float = 0.5,
    session: requests.Session | None = None,
) -> list[Product]:
    if not search_term.strip():
        raise ValueError("search_term must not be empty")
    if pages < 1:
        raise ValueError("pages must be at least 1")

    own_session = session is None
    session = session or build_session()
    products: list[Product] = []
    seen_urls: set[str] = set()

    try:
        for page in range(1, pages + 1):
            html = fetch_html(
                session,
                BASE_URL,
                params={"route": "product/search", "search": search_term, "page": page},
                timeout=timeout,
            )
            page_products = parse_search_page(html)
            if not page_products:
                if page == 1:
                    raise ScraperError(
                        "No product cards were found. The site layout may have changed "
                        "or the request may have been blocked."
                    )
                break

            new_count = 0
            for product in page_products:
                if product.url not in seen_urls:
                    products.append(product)
                    seen_urls.add(product.url)
                    new_count += 1
            if new_count == 0:
                break

        if include_details:
            for product in products:
                try:
                    enrich_product(product, session, timeout=timeout, delay=delay)
                except ScraperError as exc:
                    print(f"warning: could not enrich {product.url}: {exc}", file=sys.stderr)
    finally:
        if own_session:
            session.close()

    return products


def write_json(products: Iterable[Product], output: Path | None) -> None:
    payload = json.dumps([asdict(product) for product in products], indent=2, ensure_ascii=False)
    if output:
        output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


def write_csv(products: Iterable[Product], output: Path | None) -> None:
    fieldnames = [
        "name",
        "price",
        "original_price",
        "discount",
        "availability",
        "url",
        "image_url",
        "model",
        "brand",
        "specifications",
    ]
    handle = output.open("w", encoding="utf-8", newline="") if output else sys.stdout
    try:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for product in products:
            row = asdict(product)
            row["specifications"] = (
                json.dumps(row["specifications"], ensure_ascii=False)
                if row["specifications"]
                else ""
            )
            writer.writerow(row)
    finally:
        if output:
            handle.close()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape MDComputers product search results into JSON or CSV."
    )
    parser.add_argument("search_term", help="Search phrase, for example: external harddrive")
    parser.add_argument("--pages", type=int, default=1, help="Number of result pages (default: 1)")
    parser.add_argument(
        "--include-details",
        action="store_true",
        help="Visit each product page for model, brand, availability, and specifications",
    )
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between detail requests")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--output", type=Path, help="Write output to this file instead of stdout")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        products = scrape(
            args.search_term,
            pages=args.pages,
            include_details=args.include_details,
            timeout=args.timeout,
            delay=max(args.delay, 0),
        )
        if args.format == "csv":
            write_csv(products, args.output)
        else:
            write_json(products, args.output)
    except (ScraperError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
