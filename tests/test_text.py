from utter.tts.text import chunk_text, clean_text, detect_language, split_sentences


def test_clean_strips_markdown():
    md = "## Title\n\nSome **bold** and *italic* with `code` and a [link](https://x.y/z).\n\n- item one\n- item two\n\n```py\nprint(1)\n```\n"
    out = clean_text(md)
    assert "##" not in out and "**" not in out and "`" not in out
    assert "link" in out and "https://" not in out
    assert "(code block omitted)" in out
    assert "item one" in out and "- item" not in out


def test_clean_url_modes():
    t = "see https://example.com/a?b=c now"
    assert clean_text(t, urls="link") == "see link now"
    assert clean_text(t, urls="skip") == "see now"
    assert "https://example.com/a?b=c" in clean_text(t, urls="verbatim")


def test_clean_keeps_plain_text_when_markdown_disabled():
    t = "2 * 3 = 6 and a_b_c"
    assert clean_text(t, strip_markdown=False) == t


def test_clean_removes_emoji_and_collapses_space():
    assert clean_text("Hello \U0001F600   world  \U0001F680") == "Hello world"


def test_split_sentences_handles_abbreviations():
    s = split_sentences("Use e.g. this. Then that! Really? Yes.")
    assert s == ["Use e.g. this.", "Then that!", "Really?", "Yes."]


def test_split_sentences_on_paragraphs():
    s = split_sentences("first line\nsecond line\n\nthird")
    assert s == ["first line", "second line", "third"]


def test_chunk_merges_short_and_splits_long():
    short = "Hi. Ok. Yes. No. Go."
    assert len(chunk_text(short)) == 1
    long = " ".join(["word"] * 200) + "."
    chunks = chunk_text(long, max_chars=280)
    assert len(chunks) > 1
    assert all(len(c) <= 280 for c in chunks)
    assert " ".join(chunks) == long


def test_chunk_never_exceeds_max_on_comma_heavy_text():
    t = ", ".join(["alpha beta gamma"] * 60) + "."
    for c in chunk_text(t, max_chars=120):
        assert len(c) <= 120


def test_detect_language_scripts():
    assert detect_language("The quick brown fox is here and it is fine.").code == "en"
    assert detect_language("Das ist ein sch\u00f6ner Tag und wir gehen nicht raus.").code == "de"
    assert detect_language("\u0426\u0435 \u0434\u0443\u0436\u0435 \u0433\u0430\u0440\u043d\u0438\u0439 \u0434\u0435\u043d\u044c, \u0456 \u043c\u0438 \u0439\u0434\u0435\u043c\u043e \u0433\u0443\u043b\u044f\u0442\u0438.").code == "uk"
    assert detect_language("\u042d\u0442\u043e \u043e\u0447\u0435\u043d\u044c \u0445\u043e\u0440\u043e\u0448\u0438\u0439 \u0434\u0435\u043d\u044c, \u0438 \u043c\u044b \u0438\u0434\u0451\u043c \u0433\u0443\u043b\u044f\u0442\u044c.").code == "ru"
    assert detect_language("").code == "en"
    assert detect_language("12345 !!!", default="de").code == "de"
