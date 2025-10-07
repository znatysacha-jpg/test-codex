#!/usr/bin/env python3
"""Simple lead generation web scraper.

This script fetches the HTML content of one or more URLs and extracts email
addresses and phone numbers. The results are stored in a CSV file that can be
used for lead generation or outreach campaigns.

Example usage::

    python scraper_bot.py --urls https://example.com https://example.org \\
        --output leads.csv

You can also read URLs from a text file (one per line)::

    python scraper_bot.py --input-file urls.txt

The script handles network errors gracefully and skips URLs that cannot be
reached. The CSV output contains one row per contact detail with the columns
``url``, ``email`` and ``phone``.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_REGEX = re.compile(
    r"""
    (?:
        (?:(?:\+|00)\d{1,3}[\s.-]?)?       # Country code
        (?:\(\d{1,4}\)[\s.-]?|\d{1,4}[\s.-]?)?  # Area code
        \d{2,4}[\s.-]?\d{2,4}[\s.-]?\d{2,4}      # Local number
    )
    """,
    re.VERBOSE,
)

AGE_REGEX = re.compile(
    r"""
    (?:
        age\s*[:\-]?\s*(\d{1,3}) |      # "age 30" or "age: 30"
        aged?\s*(\d{1,3}) |              # "aged 30"
        (\d{1,3})\s*(?:ans?|years?\s*old|yo)  # "30 ans", "30 years old", "30yo"
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--urls",
        nargs="+",
        help="One or more URLs to scrape",
    )
    source.add_argument(
        "--input-file",
        type=Path,
        help="Path to a text file containing URLs (one per line)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("leads.csv"),
        help="Destination CSV file (default: leads.csv)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Timeout for HTTP requests in seconds (default: 10)",
    )
    parser.add_argument(
        "--locations",
        nargs="+",
        help="Location keywords to require in the page when running non-interactively",
    )
    parser.add_argument(
        "--min-age",
        type=int,
        help="Minimum age to accept when running non-interactively",
    )
    parser.add_argument(
        "--max-age",
        type=int,
        help="Maximum age to accept when running non-interactively",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run without prompting for filters (uses CLI options or defaults)",
    )
    return parser.parse_args(argv)


def read_urls(args: argparse.Namespace) -> List[str]:
    """Return the list of URLs provided by the user."""
    if args.urls:
        return args.urls
    assert args.input_file is not None
    if not args.input_file.exists():
        raise FileNotFoundError(f"Input file not found: {args.input_file}")
    with args.input_file.open("r", encoding="utf-8") as handle:
        urls = [line.strip() for line in handle if line.strip()]
    if not urls:
        raise ValueError("The input file does not contain any URLs")
    return urls


def fetch_url(url: str, timeout: float) -> str:
    """Fetch a URL and return its decoded text content."""
    request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        charset = "utf-8"
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].split(";")[0].strip()
        return response.read().decode(charset, errors="replace")


def extract_contacts(text: str) -> Tuple[Set[str], Set[str]]:
    """Extract email addresses and phone numbers from text."""
    emails = {match.lower() for match in EMAIL_REGEX.findall(text)}
    phones = {normalize_phone(match) for match in PHONE_REGEX.findall(text)}
    phones = {phone for phone in phones if len(phone) >= 7}
    return emails, phones


def normalize_phone(raw: str) -> str:
    """Normalize phone numbers by collapsing whitespace and punctuation."""
    digits = re.sub(r"[^+\d]", "", raw)
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    return digits


def normalise_filters(
    locations: Sequence[str] | None,
    min_age: int | None,
    max_age: int | None,
) -> Tuple[List[str], Tuple[int | None, int | None]]:
    """Normalise CLI-provided filters and validate the age range."""

    cleaned_locations = [part.strip() for part in (locations or []) if part.strip()]
    if min_age is not None and min_age < 0:
        raise ValueError("Minimum age must be non-negative")
    if max_age is not None and max_age < 0:
        raise ValueError("Maximum age must be non-negative")
    if min_age is not None and max_age is not None and min_age > max_age:
        print("Minimum age is greater than maximum age; swapping the values.")
        min_age, max_age = max_age, min_age
    return cleaned_locations, (min_age, max_age)


def prompt_filters() -> Tuple[List[str], Tuple[int | None, int | None]]:
    """Prompt the user for location keywords and an age range."""

    location_input = input(
        "Enter location keywords to match (comma-separated, leave blank for none): "
    ).strip()
    locations = [part.strip() for part in location_input.split(",") if part.strip()]

    def _parse_age(prompt: str) -> int | None:
        while True:
            value = input(prompt).strip()
            if not value:
                return None
            if value.isdigit():
                return int(value)
            print("Please enter a numeric value or leave blank.")

    min_age = _parse_age("Enter minimum age to match (leave blank for none): ")
    max_age = _parse_age("Enter maximum age to match (leave blank for none): ")

    if min_age is not None and max_age is not None and min_age > max_age:
        print("Minimum age is greater than maximum age; swapping the values.")
        min_age, max_age = max_age, min_age

    return locations, (min_age, max_age)


def extract_ages(text: str) -> Set[int]:
    """Extract probable ages referenced in the given text."""

    ages: Set[int] = set()
    for match in AGE_REGEX.findall(text):
        for group in match:
            if not group:
                continue
            try:
                value = int(group)
            except ValueError:
                continue
            if 0 < value < 130:
                ages.add(value)
    return ages


def matches_filters(
    text: str, locations: Sequence[str], age_range: Tuple[int | None, int | None]
) -> bool:
    """Return True if the text satisfies the requested location and age filters."""

    lowered = text.lower()
    if locations:
        if not any(location.lower() in lowered for location in locations):
            return False

    min_age, max_age = age_range
    if min_age is None and max_age is None:
        return True

    ages = extract_ages(text)
    if not ages:
        return False

    for age in ages:
        if (min_age is None or age >= min_age) and (max_age is None or age <= max_age):
            return True
    return False


def iter_rows(url: str, emails: Iterable[str], phones: Iterable[str]) -> Iterable[Tuple[str, str, str]]:
    """Yield CSV rows for the given contact information."""
    for email in sorted(set(emails)):
        yield url, email, ""
    for phone in sorted(set(phones)):
        yield url, "", phone


def write_csv(path: Path, rows: Iterable[Tuple[str, str, str]]) -> None:
    """Write the collected rows to a CSV file."""
    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["url", "email", "phone"])
        for row in rows:
            writer.writerow(row)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if (
            args.locations
            or args.min_age is not None
            or args.max_age is not None
        ):
            locations, age_range = normalise_filters(
                args.locations, args.min_age, args.max_age
            )
        elif args.non_interactive:
            locations, age_range = ([], (None, None))
        else:
            locations, age_range = prompt_filters()
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    try:
        urls = read_urls(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    all_rows: List[Tuple[str, str, str]] = []
    for url in urls:
        try:
            html = fetch_url(url, timeout=args.timeout)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            print(f"Failed to fetch {url}: {exc}", file=sys.stderr)
            continue

        if not matches_filters(html, locations, age_range):
            print(
                f"Skipping {url}: does not match the requested location/age filters"
            )
            continue

        emails, phones = extract_contacts(html)
        if not emails and not phones:
            print(f"No contacts found on {url}")
            continue
        all_rows.extend(iter_rows(url, emails, phones))
        print(
            f"Collected {len(emails)} email(s) and {len(phones)} phone number(s) from {url}"
        )

    if not all_rows:
        print("No contact details were collected.")
        return 0

    write_csv(args.output, all_rows)
    print(f"Saved {len(all_rows)} row(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
