from pathlib import Path

from mdcomputers_scraper import parse_product_details, parse_search_page

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_search_page_extracts_and_deduplicates_products() -> None:
    html = (FIXTURES / "mdcomputers_search.html").read_text(encoding="utf-8")

    products = parse_search_page(html)

    assert len(products) == 2
    assert products[0].name == "Western Digital My Book 8TB External Hard Drive"
    assert products[0].price == "₹26,480"
    assert products[0].original_price == "₹30,000"
    assert products[0].discount == "-11%"
    assert products[0].availability == "In stock"
    assert products[0].url == "https://mdcomputers.in/western-digital-my-book-8tb.html"
    assert products[0].image_url == "https://mdcomputers.in/images/wd-my-book.jpg"
    assert products[1].price == "₹7,499"
    assert products[1].availability == "Out of stock"


def test_parse_product_details_extracts_common_opencart_fields() -> None:
    html = (FIXTURES / "mdcomputers_product.html").read_text(encoding="utf-8")

    details = parse_product_details(html)

    assert details["brand"] == "Western Digital"
    assert details["model"] == "WDBBGB0080HBK-BESN"
    assert details["availability"] == "In Stock"
    assert details["specifications"] == {
        "Capacity": "8 TB",
        "Interface": "USB 3.0",
    }
