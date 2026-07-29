#!/usr/bin/env bash
# Download the S&P 500 constituents CSV and print:
# Company Name<TAB>Location<TAB>Founding Year, sorted by year.
set -euo pipefail

DEFAULT_URL="https://raw.githubusercontent.com/datasets/s-and-p-500-companies/refs/heads/main/data/constituents.csv"
CSV_URL="${1:-$DEFAULT_URL}"

for command in curl python3; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf 'error: required command not found: %s\n' "$command" >&2
    exit 1
  fi
done

curl --fail --silent --show-error --location \
  --retry 3 --retry-delay 1 --connect-timeout 10 --max-time 60 \
  "$CSV_URL" |
python3 -c '
import csv
import re
import sys

reader = csv.DictReader(sys.stdin)
required = {"Security", "Headquarters Location", "Founded"}
missing = required.difference(reader.fieldnames or [])
if missing:
    raise SystemExit("error: missing CSV columns: " + ", ".join(sorted(missing)))

rows = []
for row in reader:
    founded = (row.get("Founded") or "").strip()
    years = [int(value) for value in re.findall(r"(?<!\d)(?:17|18|19|20)\d{2}(?!\d)", founded)]
    # Some entries include a legal-entity year plus an older historical origin,
    # e.g. "2013 (1888)". The earliest year is the most useful founding year.
    year = min(years) if years else None
    rows.append(
        (
            year is None,
            year if year is not None else 10**9,
            (row.get("Security") or "").casefold(),
            (row.get("Security") or "").strip(),
            (row.get("Headquarters Location") or "").strip(),
            str(year) if year is not None else "Unknown",
        )
    )

rows.sort(key=lambda item: item[:3])
writer = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
writer.writerow(["Company Name", "Location", "Founding Year"])
for _, _, _, company, location, year in rows:
    writer.writerow([company, location, year])
'
