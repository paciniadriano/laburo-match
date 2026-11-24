"""Generate the hard-layout PDFs for spike 1.6 from the fictional sample CV.

Run:
    uv run --no-project --with reportlab --with pypdf --with pypdfium2 --with pillow \
        python make_hard_pdfs.py

Each file fails text extraction in a different way:
- two_column.pdf: correct text, but two side-by-side blocks (reading order risk).
- garbled.pdf:    embedded font without a ToUnicode map (looks fine, extracts as junk).
- scanned.pdf:    page images only, no text layer at all.
"""

import os
from pathlib import Path

import pypdfium2 as pdfium
import reportlab
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    FrameBreak,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

import make_sample_cv as cv

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "hard"
SAMPLE_PDF = cv.OUTPUT


def make_two_column(path: Path) -> None:
    """Sidebar (contact, skills, languages, education) on the left, experience on the right.

    Page 1 has two frames; later pages switch to one full-width frame so the
    overflow of the main column does not land in an empty sidebar.
    """
    styles = getSampleStyleSheet()
    h1, h2, body = styles["Title"], styles["Heading2"], styles["BodyText"]
    width, height = A4
    margin, gap, sidebar_w = 1.5 * cm, 0.8 * cm, 5.5 * cm

    sidebar = Frame(margin, margin, sidebar_w, height - 2 * margin, id="sidebar")
    main = Frame(
        margin + sidebar_w + gap,
        margin,
        width - 2 * margin - sidebar_w - gap,
        height - 2 * margin,
        id="main",
    )
    full = Frame(margin, margin, width - 2 * margin, height - 2 * margin, id="full")

    doc = BaseDocTemplate(str(path), pagesize=A4, invariant=True)
    doc.addPageTemplates(
        [PageTemplate(id="first", frames=[sidebar, main]), PageTemplate(id="rest", frames=[full])]
    )

    story: list = [NextPageTemplate("rest"), Paragraph("Contact", h2)]
    story += [Paragraph(part.strip(), body) for part in cv.HEADER["contact"].split("·")]
    story += [Paragraph(part.strip(), body) for part in cv.HEADER["personal"].split("·")]
    for heading, lines in (
        ("Skills", cv.SKILLS),
        ("Languages", cv.LANGUAGES),
        ("Education", cv.EDUCATION),
    ):
        story.append(Paragraph(heading, h2))
        story.extend(Paragraph(line, body) for line in lines)

    story += [
        FrameBreak(),
        Paragraph(cv.HEADER["name"], h1),
        Paragraph(cv.HEADER["title"], body),
        Paragraph("Summary", h2),
        Paragraph(cv.SUMMARY, body),
        Paragraph("Experience", h2),
    ]
    for title, company, dates, bullets in cv.EXPERIENCES:
        story.append(Paragraph(f"<b>{title}</b> · {company} · {dates}", body))
        story.extend(Paragraph(f"- {bullet}", body) for bullet in bullets)
        story.append(Spacer(1, 0.2 * cm))
    doc.build(story)


def make_garbled(path: Path) -> None:
    """Same single-column CV with an embedded TrueType font, then strip /ToUnicode.

    With asciiReadable=False, reportlab assigns glyph codes in order of first use
    (like design tools do), so without the ToUnicode table those codes map to the
    wrong characters. The default (True) keeps ASCII codes readable and pypdf
    recovers the text even without the map. This is the failure seen in
    design-tool exports: the page renders perfectly but the extracted text is
    junk with a normal character count.
    """
    fonts_dir = Path(reportlab.__file__).parent / "fonts"
    for name, file in (("Vera", "Vera.ttf"), ("VeraBd", "VeraBd.ttf")):
        pdfmetrics.registerFont(TTFont(name, os.fspath(fonts_dir / file), asciiReadable=False))
    pdfmetrics.registerFontFamily("Vera", normal="Vera", bold="VeraBd")

    styles = getSampleStyleSheet()
    for name in ("Title", "Heading2", "BodyText"):
        styles[name].fontName = "VeraBd" if name != "BodyText" else "Vera"

    tmp = path.with_suffix(".tmp.pdf")
    SimpleDocTemplate(str(tmp), pagesize=A4, invariant=True).build(cv.build_story(styles))

    writer = PdfWriter(clone_from=PdfReader(tmp))
    removed = 0
    for page in writer.pages:
        for font in page["/Resources"]["/Font"].values():
            font = font.get_object()
            if "/ToUnicode" in font:
                del font["/ToUnicode"]
                removed += 1
    writer.write(path)
    tmp.unlink()
    print(f"  removed {removed} ToUnicode maps")


def make_scanned(path: Path, dpi: int = 150) -> None:
    """Render each page of the sample CV to a grayscale image and save images only.

    A slight rotation mimics a real scanner; there is no text layer left.
    """
    pdf = pdfium.PdfDocument(SAMPLE_PDF)
    images = [
        page.render(scale=dpi / 72).to_pil().convert("L").rotate(0.4, expand=False, fillcolor=255)
        for page in pdf
    ]
    images[0].save(path, save_all=True, append_images=images[1:], resolution=dpi)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    for name, build in (
        ("two_column.pdf", make_two_column),
        ("garbled.pdf", make_garbled),
        ("scanned.pdf", make_scanned),
    ):
        target = OUT_DIR / name
        build(target)
        print(f"Wrote {target.relative_to(HERE)} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
