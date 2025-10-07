#!/usr/bin/env python3
"""Simple lead generation web scraper.

This script fetches the HTML content of one or more URLs and extracts email
addresses and phone numbers. The results are stored in an Excel workbook (or a
CSV file if you use a `.csv` extension) that can be used for lead generation or
outreach campaigns.

Example usage::

    python scraper_bot.py --urls https://example.com https://example.org \\
        --output leads.xlsx

You can also read URLs from a text file (one per line)::

    python scraper_bot.py --input-file urls.txt

    The script handles network errors gracefully and skips URLs that cannot be
    reached. The Excel output contains one row per contact with the columns
    ``Nom``, ``Prénom``, ``Email``, ``Numéro de téléphone``, ``Arrondissement``
    and ``Âge``.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

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
        default=Path("leads.xlsx"),
        help="Destination file (Excel .xlsx by default)",
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


@dataclass
class Contact:
    """Structured contact details extracted from a page."""

    last_name: str = ""
    first_name: str = ""
    email: str = ""
    phone: str = ""
    arrondissement: str = ""
    age: int | None = None

    def to_row(self) -> List[str]:
        """Return the contact as a list ready for export."""

        age_value = "" if self.age is None else str(self.age)
        return [
            self.last_name,
            self.first_name,
            self.email,
            self.phone,
            self.arrondissement,
            age_value,
        ]


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


NAME_FIELD_REGEX = re.compile(
    r"\b(?P<label>nom|prénom)\s*[:\-]\s*(?P<value>[A-Za-zÀ-ÖØ-öø-ÿ' -]{2,})",
    re.IGNORECASE,
)

TITLE_NAME_REGEX = re.compile(
    r"\b(?:M(?:me|lle|onsieur)?|Madame|Monsieur|Dr)\.?\s+"
    r"([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ'\-]+)\s+([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ'\-]+)",
)

ARRONDISSEMENT_REGEX = re.compile(
    r"\b(\d{1,2})(?:er|ème|e)?\s*arrondissement\b",
    re.IGNORECASE,
)

PARIS_POSTAL_REGEX = re.compile(r"\b75(\d{3})\b")


def normalise_name(raw: str) -> str:
    """Normalise a name by stripping whitespace and capitalising each part."""

    cleaned = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ' -]", "", raw).strip()
    if not cleaned:
        return ""
    tokens = cleaned.replace("-", " - ").split()
    lower_exceptions = {"de", "du", "des", "la", "le", "les", "d'", "l'"}
    parts: List[str] = []
    for token in tokens:
        if token == "-":
            parts.append("-")
            continue
        lowered = token.lower()
        if lowered in lower_exceptions:
            parts.append(lowered)
            continue
        parts.append(lowered.capitalize())
    normalised = " ".join(parts)
    normalised = normalised.replace(" - ", "-")
    return normalised


def extract_name_pairs(text: str) -> List[Tuple[str, str]]:
    """Extract potential (first_name, last_name) pairs from the text."""

    first_names: List[str] = []
    last_names: List[str] = []
    for match in NAME_FIELD_REGEX.finditer(text):
        label = match.group("label").lower()
        value = normalise_name(match.group("value"))
        if not value:
            continue
        if label.startswith("nom"):
            last_names.append(value)
        else:
            first_names.append(value)

    pairs: List[Tuple[str, str]] = []
    count = max(len(first_names), len(last_names))
    for index in range(count):
        first = first_names[index] if index < len(first_names) else ""
        last = last_names[index] if index < len(last_names) else ""
        if first or last:
            pairs.append((first, last))

    for match in TITLE_NAME_REGEX.finditer(text):
        first = normalise_name(match.group(1))
        last = normalise_name(match.group(2))
        if first or last:
            pairs.append((first, last))

    seen: Set[Tuple[str, str]] = set()
    unique_pairs: List[Tuple[str, str]] = []
    for first, last in pairs:
        key = (first.lower(), last.lower())
        if key in seen:
            continue
        seen.add(key)
        unique_pairs.append((first, last))
    return unique_pairs


def extract_arrondissements(text: str) -> List[str]:
    """Extract arrondissement mentions from the text."""

    arrondissements: List[str] = []
    for match in ARRONDISSEMENT_REGEX.finditer(text):
        number = int(match.group(1))
        suffix = "er" if number == 1 else "e"
        arrondissements.append(f"{number}{suffix} arrondissement")

    for match in PARIS_POSTAL_REGEX.finditer(text):
        digits = match.group(1)
        number = int(digits[-2:])
        suffix = "er" if number == 1 else "e"
        arrondissements.append(f"{number}{suffix} arrondissement")

    unique: List[str] = []
    seen: Set[str] = set()
    for arrondissement in arrondissements:
        key = arrondissement.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(arrondissement)
    return unique


def derive_names_from_email(email: str) -> Tuple[str, str]:
    """Best-effort derivation of first/last names from an email address."""

    local = email.split("@", 1)[0]
    parts = [part for part in re.split(r"[._-]+", local) if part and not part.isdigit()]
    if len(parts) < 2:
        return "", ""
    first = normalise_name(parts[0])
    last = normalise_name(parts[1])
    return first, last


def assign_sequence(contacts: List[Contact], values: Sequence, attr: str) -> None:
    """Assign a sequence of values to existing contacts or create new ones."""

    if not values:
        return
    if len(values) == 1 and contacts:
        value = values[0]
        for contact in contacts:
            setattr(contact, attr, value)
        return

    iterator = iter(values)
    for contact in contacts:
        try:
            value = next(iterator)
        except StopIteration:
            break
        setattr(contact, attr, value)
    for value in iterator:
        kwargs = {attr: value}
        contacts.append(Contact(**kwargs))


def assign_names(contacts: List[Contact], names: Sequence[Tuple[str, str]]) -> None:
    """Assign name pairs to contacts, adding new contacts if necessary."""

    if not names:
        return

    name_iter = iter(names)
    for contact in contacts:
        if contact.first_name or contact.last_name:
            continue
        try:
            first, last = next(name_iter)
        except StopIteration:
            return
        contact.first_name = first
        contact.last_name = last

    for first, last in name_iter:
        contacts.append(Contact(last_name=last, first_name=first))


def build_contacts(text: str, emails: Iterable[str], phones: Iterable[str]) -> List[Contact]:
    """Combine extracted data into structured contact entries."""

    email_list = sorted(set(emails))
    phone_list = sorted(set(phones))
    name_pairs = extract_name_pairs(text)
    arrondissements = extract_arrondissements(text)
    ages = sorted(extract_ages(text))

    contacts: List[Contact] = []
    for email in email_list:
        first, last = derive_names_from_email(email)
        contacts.append(Contact(last_name=last, first_name=first, email=email))

    assign_names(contacts, name_pairs)
    assign_sequence(contacts, phone_list, "phone")
    assign_sequence(contacts, arrondissements, "arrondissement")
    assign_sequence(contacts, ages, "age")

    if not contacts and (phone_list or name_pairs or arrondissements or ages):
        contacts.append(Contact())
        assign_names(contacts, name_pairs)
        assign_sequence(contacts, phone_list, "phone")
        assign_sequence(contacts, arrondissements, "arrondissement")
        assign_sequence(contacts, ages, "age")

    filtered_contacts = [
        contact
        for contact in contacts
        if contact.email
        or contact.phone
        or contact.first_name
        or contact.last_name
        or contact.arrondissement
        or contact.age is not None
    ]

    return filtered_contacts


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


HEADERS = ["Nom", "Prénom", "Email", "Numéro de téléphone", "Arrondissement", "Âge"]


def write_csv(path: Path, contacts: Sequence[Contact]) -> None:
    """Write the collected contacts to a CSV file."""

    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(HEADERS)
        for contact in contacts:
            writer.writerow(contact.to_row())


def column_letter(index: int) -> str:
    """Convert a 1-based column index to an Excel column letter."""

    result = ""
    current = index
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        result = chr(65 + remainder) + result
    return result


def build_sheet_xml(rows: List[List[str]]) -> str:
    """Return the XML content for the worksheet."""

    row_elements: List[str] = []
    for row_index, row in enumerate(rows, start=1):
        cell_elements: List[str] = []
        for col_index, value in enumerate(row, start=1):
            cell_ref = f"{column_letter(col_index)}{row_index}"
            if value == "":
                cell_elements.append(f'<c r="{cell_ref}"/>')
                continue
            if value.isdigit():
                cell_elements.append(f'<c r="{cell_ref}"><v>{value}</v></c>')
                continue
            cell_elements.append(
                """
                <c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{data}</t></is></c>
                """.strip().format(ref=cell_ref, data=escape(value))
            )
        row_elements.append(f"<row r=\"{row_index}\">{''.join(cell_elements)}</row>")

    total_rows = len(rows)
    total_cols = len(rows[0]) if rows else 0
    if total_rows and total_cols:
        dimension = f"A1:{column_letter(total_cols)}{total_rows}"
    else:
        dimension = "A1:A1"

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\""
        " xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">"
        f"<dimension ref=\"{dimension}\"/>"
        "<sheetViews><sheetView workbookViewId=\"0\"/></sheetViews>"
        "<sheetFormatPr defaultRowHeight=\"15\"/>"
        f"<sheetData>{''.join(row_elements)}</sheetData>"
        "</worksheet>"
    )


def write_xlsx(path: Path, contacts: Sequence[Contact]) -> None:
    """Write the collected contacts to an Excel workbook."""

    rows = [HEADERS] + [contact.to_row() for contact in contacts]
    sheet_xml = build_sheet_xml(rows)

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
    <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
    <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>
""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
    <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
    <sheets>
        <sheet name="Contacts" sheetId="1" r:id="rId1"/>
    </sheets>
</workbook>
""",
        )
        archive.writestr(
            "xl/styles.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
    <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
    <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
    <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
    <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
    <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
    <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>
""",
        )
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def write_output(path: Path, contacts: Sequence[Contact]) -> Path:
    """Persist contacts to disk, choosing CSV or Excel based on extension."""

    suffix = path.suffix.lower()
    if suffix == ".csv":
        write_csv(path, contacts)
        return path

    target = path if suffix == ".xlsx" else path.with_suffix(".xlsx")
    write_xlsx(target, contacts)
    return target


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

    contacts: List[Contact] = []
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

        page_contacts = build_contacts(html, emails, phones)
        if not page_contacts:
            print(f"No structured contacts could be created for {url}")
            continue

        contacts.extend(page_contacts)
        print(
            f"Collected {len(page_contacts)} contact(s) from {url}"
        )

    if not contacts:
        print("No contact details were collected.")
        return 0

    destination = write_output(args.output, contacts)
    print(f"Saved {len(contacts)} contact(s) to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
