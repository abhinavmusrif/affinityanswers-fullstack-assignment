# AffinityAnswers Full-Stack Internship Assignment

Two small, production-minded command-line tasks:

1. A Python scraper for MDComputers product search results.
2. A shell script that downloads the S&P 500 constituents CSV and prints company name, headquarters location, and founding year sorted chronologically.

## 1. MDComputers product scraper

### Setup

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### Usage

```bash
python mdcomputers_scraper.py "external harddrive"
```

Write JSON to a file and scan two result pages:

```bash
python mdcomputers_scraper.py "external harddrive" \
  --pages 2 \
  --output external-harddrives.json
```

Write CSV:

```bash
python mdcomputers_scraper.py "external harddrive" \
  --format csv \
  --output external-harddrives.csv
```

Enrich each search result by visiting its product page:

```bash
python mdcomputers_scraper.py "external harddrive" \
  --include-details \
  --delay 0.75 \
  --output external-harddrives-detailed.json
```

Extracted fields include product name, current/original price, discount, availability, product URL, image URL, and—when `--include-details` is used—model, brand, and specifications.

### Reliability choices

- Uses request timeouts, retries, backoff, and a browser-like user agent.
- Stops pagination when no new products are found.
- Deduplicates products by canonical product URL.
- Supports multiple selectors because e-commerce themes change over time.
- Adds an optional delay before product-detail requests.
- Returns a non-zero exit code with a useful error if the site blocks the request or changes its HTML.

Websites can change their markup or scraping policy. Run this responsibly, at a low request rate, and follow the site's terms and robots policy.

## 2. S&P 500 company sorter

```bash
chmod +x sp500_companies.sh
./sp500_companies.sh
```

The output is tab-separated:

```text
Company Name    Location    Founding Year
```

A custom CSV URL or local `file://` URL can be supplied as the first argument:

```bash
./sp500_companies.sh "https://example.com/constituents.csv"
```

The script uses `curl` for resilient downloading and Python's standard `csv` module for correct handling of quoted commas. For entries such as `2013 (1888)`, the earliest year is treated as the historical founding year.

## Tests

Tests use local HTML/CSV fixtures and do not need network access.

```bash
pip install -r requirements-dev.txt
pytest -q
bash -n sp500_companies.sh
```

## Sample output

Fixture-based examples are available under [`sample_output/`](sample_output/). They demonstrate the output schema without presenting cached values as current live prices.
