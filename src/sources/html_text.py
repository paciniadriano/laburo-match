"""HTML to plain text, with the list style the fixtures and the extraction prompt expect.

One rule drives the layout: a block element ends the current line unless that line is empty.
Consecutive blocks therefore never leave blank lines, and empty paragraphs vanish.
"""

import re
from html.parser import HTMLParser

_BLOCK_TAGS = {"div", "p", "br", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table"}
_SKIP_TAGS = {"script", "style"}  # their content is never text a person reads


class _TextBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)  # &amp; &nbsp; ... become real characters
        self.parts: list[str] = []
        self._line = ""  # text of the line being built
        self._skip_depth = 0

    def _end_line(self) -> None:
        if self._line.strip():
            self.parts.append("\n")
        self._line = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag == "li":
            self._end_line()
            self.parts.append("- ")
            self._line = "- "
        elif tag in _BLOCK_TAGS:
            self._end_line()

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS or tag == "li":
            self._end_line()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        data = re.sub(r"\s+", " ", data.replace("\xa0", " "))  # HTML treats newlines as spaces
        self.parts.append(data)
        self._line += data


def html_to_text(html: str) -> str:
    builder = _TextBuilder()
    builder.feed(html)
    builder.close()
    lines = "".join(builder.parts).split("\n")
    return "\n".join(line.strip() for line in lines).strip()
