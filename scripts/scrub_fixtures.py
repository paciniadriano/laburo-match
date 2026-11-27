"""Remove third-party contact data from fixtures before they are committed (the repo is public).

    uv run python scripts/scrub_fixtures.py [fixtures]

Emails outside example.com and phone numbers are replaced with placeholders, in place. Contact
names cannot be detected reliably with a regex, so lines that mention contact words are printed
for a human to read. Company names and posting text may stay. Raw captures never enter the repo:
record them elsewhere, then scrub the copy that goes into fixtures/.
"""

import re
import sys
from pathlib import Path
from typing import Any

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}")
# A run of digits with optional phone separators. Commas and slashes are not separators, so salaries
# ("$4,000") and dates ("14/03/1993") never form a run; the digit count below rules out year ranges.
PHONE_RUN = re.compile(r"(?<![\w/,.$])\+?\(?\d[\d\s().-]*\d(?![\w/,$])")
MIN_PHONE_DIGITS, MAX_PHONE_DIGITS = 9, 15
SAFE_DOMAIN = re.compile(r"(^|\.)example\.com$", re.IGNORECASE)
CONTACT_WORDS = re.compile(
    r"\b(contact|contacto|recruiter|reclutador|hr manager|whatsapp)\b", re.IGNORECASE
)

EMAIL_PLACEHOLDER = "contact@example.com"
# No digits on purpose: a numeric placeholder would itself look like a phone.
PHONE_PLACEHOLDER = "[phone removed]"


def _is_phone(candidate: str) -> bool:
    digits = sum(ch.isdigit() for ch in candidate)
    return MIN_PHONE_DIGITS <= digits <= MAX_PHONE_DIGITS


def _is_external_email(candidate: str) -> bool:
    domain = candidate.rsplit("@", 1)[1]
    return not SAFE_DOMAIN.search(domain)


def find_contact_data(text: str) -> list[str]:
    """Emails outside example.com and phone-like numbers found in the text."""
    emails = [m.group(0) for m in EMAIL.finditer(text) if _is_external_email(m.group(0))]
    without_emails = EMAIL.sub(" ", text)  # digits inside an email are not a phone
    phones = [
        m.group(0).strip() for m in PHONE_RUN.finditer(without_emails) if _is_phone(m.group(0))
    ]
    return emails + phones


def scrub(text: str) -> str:
    """Replace contact data with placeholders; everything else is left untouched."""
    text = EMAIL.sub(
        lambda m: m.group(0) if not _is_external_email(m.group(0)) else EMAIL_PLACEHOLDER,
        text,
    )
    return PHONE_RUN.sub(lambda m: PHONE_PLACEHOLDER if _is_phone(m.group(0)) else m.group(0), text)


def scrub_json_values(value: Any) -> Any:
    """Scrub only the string values of parsed JSON.

    Scrubbing the raw text of a JSON file could rewrite a long number that is not a phone
    (a timestamp, an id) and break the file; walking the values cannot.
    """
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, list):
        return [scrub_json_values(item) for item in value]
    if isinstance(value, dict):
        return {key: scrub_json_values(item) for key, item in value.items()}
    return value


def main(root: Path) -> None:
    changed = 0
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        text = path.read_text(encoding="utf-8")
        found = find_contact_data(text)
        if found:
            path.write_text(scrub(text), encoding="utf-8")
            changed += 1
            print(f"scrubbed {path}: {len(found)} item(s)")
        for n, line in enumerate(text.splitlines(), 1):
            if CONTACT_WORDS.search(line):
                print(f"review {path}:{n}: {line.strip()[:120]}")
    print(f"done: {changed} file(s) changed under {root}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "fixtures"))
