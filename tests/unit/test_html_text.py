from src.sources.html_text import html_to_text


def test_blocks_and_list_items_become_lines():
    html = "<div>Requirements</div><ul><li>React</li><li>TypeScript</li></ul>"

    assert html_to_text(html) == "Requirements\n- React\n- TypeScript"


def test_entities_and_non_breaking_spaces_become_plain_characters():
    assert html_to_text("<p>R&amp;D&nbsp;team &gt; 5</p>") == "R&D team > 5"


def test_script_and_style_content_is_dropped():
    html = "<div>Visible</div><script>alert('x')</script><style>p{color:red}</style><p>Also</p>"

    assert html_to_text(html) == "Visible\nAlso"


def test_br_and_paragraphs_separate_lines_and_empty_paragraphs_vanish():
    assert html_to_text("<p>One</p><p></p><p></p><p>Two<br>Three</p>") == "One\nTwo\nThree"


def test_newlines_inside_the_html_text_are_just_spaces():
    assert html_to_text("<div>first\n   second</div>") == "first second"


def test_inline_tags_keep_their_text_in_the_same_line():
    assert html_to_text("<div>We use <strong>Node.js</strong> and <a href='x'>AWS</a>.</div>") == (
        "We use Node.js and AWS."
    )


def test_broken_or_unclosed_html_does_not_crash():
    assert html_to_text("<ul><li>One<li>Two</div>text") == "- One\n- Two\ntext"


def test_empty_input_gives_empty_text():
    assert html_to_text("") == ""
    assert html_to_text("   \n ") == ""
