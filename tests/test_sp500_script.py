import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "constituents.csv"


def test_shell_script_handles_quoted_commas_and_sorts_by_earliest_year() -> None:
    result = subprocess.run(
        ["bash", str(ROOT / "sp500_companies.sh"), FIXTURE.as_uri()],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.splitlines() == [
        "Company Name\tLocation\tFounding Year",
        "Old, Inc.\tNew York City, New York\t1784",
        "New Company\tAustin, Texas\t1888",
        "Middle Company\tDublin, Ireland\t1999",
    ]
