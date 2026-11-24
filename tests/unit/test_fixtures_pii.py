"""Fixtures from real postings must not carry third-party contact data (the repo is public).

Two guards: the detector behaves as expected on a table of cases, and no file under fixtures/ contains
an email outside example.com or a phone number. Names cannot be detected reliably with a regex: the
scrub script lists lines with contact words for a human look instead.
"""

from pathlib import Path

import pytest

from scripts.scrub_fixtures import find_contact_data, scrub

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.mark.parametrize(
    "text",
    [
        "Send your CV to jobs@acme-recruiting.com today",
        "Escribinos a rrhh.talento@empresa.com.ar",
        "WhatsApp +54 9 11 5555-1234",
        "Llamar al 011 4555 1234",
        "Tel: (341) 555-0100 int 2",
        "Cel 1565085816",
    ],
)
def test_detector_finds_contact_data(text: str) -> None:
    assert find_contact_data(text), text


@pytest.mark.parametrize(
    "text",
    [
        "Compensation: $4,000–$6,000 USD per month",
        "Rate: $30–$40 USD/hour",
        "Universidad Tecnológica Nacional, Rosario · 2011 – 2017",
        "Jun 2019 - Feb 2022",
        "Date: 14/03/1993",
        "5+ years of experience; 6 hours of overlap",
        "Questions? contact@example.com or hr@jobs.example.com",
        "JOB 01 | raw_index=89",
    ],
)
def test_detector_ignores_non_contact_numbers_and_example_domains(text: str) -> None:
    assert find_contact_data(text) == [], text


def test_scrub_replaces_contact_data_with_placeholders() -> None:
    out = scrub("Mail jobs@acme.com or call +54 9 11 5555-1234.")
    assert "jobs@acme.com" not in out and "5555-1234" not in out
    assert "contact@example.com" in out
    assert find_contact_data(out) == []


def test_fixtures_have_no_contact_data() -> None:
    files = [p for p in FIXTURES.rglob("*") if p.is_file()]
    assert files, "fixtures/ is empty"
    leaks = {
        str(p.relative_to(FIXTURES)): find_contact_data(p.read_text(encoding="utf-8"))
        for p in files
    }
    assert {k: v for k, v in leaks.items() if v} == {}
