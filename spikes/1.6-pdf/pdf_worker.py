"""Child process: read PDF bytes from stdin, write extracted text as JSON to stdout.

It runs in its own process so a malicious or broken PDF that loops or eats memory
can be killed by the parent without touching the server.

--hang simulates a parser stuck in a CPU-bound loop (spike only).
"""

import io
import json
import sys

def extract_pypdf(content: bytes) -> list[str]:
    """Baseline engine, kept only to compare against pdfminer (not a project dependency anymore)."""
    from pypdf import PdfReader

    return [page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages]


def extract_pdfminer(content: bytes) -> list[str]:
    """One string per page; pdfminer orders text by position on the page."""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTTextContainer

    return [
        "".join(el.get_text() for el in page if isinstance(el, LTTextContainer))
        for page in extract_pages(io.BytesIO(content))
    ]


def main() -> None:
    if "--hang" in sys.argv:
        while True:  # busy loop: no await, no sleep, only a kill can stop it
            pass

    engine = sys.argv[sys.argv.index("--engine") + 1] if "--engine" in sys.argv else "pypdf"
    content = sys.stdin.buffer.read()
    pages = extract_pdfminer(content) if engine == "pdfminer" else extract_pypdf(content)
    json.dump({"page_count": len(pages), "pages": pages}, sys.stdout)


if __name__ == "__main__":
    main()
