"""Text preparation: markdown stripping, sentence chunking, language detection.

Pure Python, no Qt / no models, so it is fully unit-testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --------------------------------------------------------------------------- cleanup

_FENCE_RE = re.compile(r"```.*?```", re.S)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_LINK_RE = re.compile(r"\[([^\]]+)\]\((?:[^)\s]+)(?:\s+\"[^\"]*\")?\)")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_URL_RE = re.compile(r"https?://[^\s)>\]]+|www\.[^\s)>\]]+")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+", re.M)
_BULLET_RE = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+", re.M)
_QUOTE_RE = re.compile(r"^\s*>\s?", re.M)
_EMPHASIS_RE = re.compile(r"(\*\*|__|\*|_|~~)(?=\S)(.+?)(?<=\S)\1")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$", re.M)
_HR_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", re.M)
_HTML_TAG_RE = re.compile(r"<[^>\n]{1,80}>")
_MULTI_SPACE_RE = re.compile(r"[ \t\u00a0]{2,}")
_MULTI_NL_RE = re.compile(r"\n{3,}")
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # symbols & pictographs, emoticons, transport, etc.
    "\U00002600-\U000027BF"  # misc symbols, dingbats
    "\U0001F1E6-\U0001F1FF"  # flags
    "\uFE0F\u200d"  # variation selector, ZWJ
    "]+"
)


def clean_text(text: str, *, strip_markdown: bool = True, urls: str = "link") -> str:
    """Turn pasted/selected text (often Markdown from an AI chat) into speakable prose.

    urls: "link" -> replace URL with the word "link"; "skip" -> remove; "verbatim" -> keep.
    """
    if not text:
        return ""
    t = text.replace("\r\n", "\n").replace("\r", "\n")

    if strip_markdown:
        t = _FENCE_RE.sub(" (code block omitted) ", t)
        t = _IMAGE_RE.sub(lambda m: m.group(1) or "", t)
        t = _LINK_RE.sub(r"\1", t)
        t = _INLINE_CODE_RE.sub(r"\1", t)
        t = _TABLE_SEP_RE.sub("", t)
        t = _HR_RE.sub("", t)
        t = _HEADING_RE.sub("", t)
        t = _QUOTE_RE.sub("", t)
        t = _BULLET_RE.sub("", t)
        # run emphasis twice to unwrap nested ***bold italic***
        t = _EMPHASIS_RE.sub(r"\2", t)
        t = _EMPHASIS_RE.sub(r"\2", t)
        t = _HTML_TAG_RE.sub(" ", t)
        t = t.replace("|", ", ")

    if urls == "link":
        t = _URL_RE.sub("link", t)
    elif urls == "skip":
        t = _URL_RE.sub("", t)

    t = _EMOJI_RE.sub("", t)
    t = _MULTI_SPACE_RE.sub(" ", t)
    t = _MULTI_NL_RE.sub("\n\n", t)
    # strip trailing spaces per line
    t = "\n".join(line.strip() for line in t.split("\n"))
    return t.strip()


# --------------------------------------------------------------------------- chunking

# Sentence end: terminal punctuation (optionally followed by quotes/brackets) then whitespace.
_SENT_END_RE = re.compile(r"(?:(?<=[.!?…。！？])|(?<=[.!?…。！？][\"”’')\]]))\s+")
_ABBREVIATIONS = {
    "e.g.", "i.e.", "etc.", "vs.", "mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.",
    "st.", "no.", "approx.", "z.b.", "bzw.", "usw.", "ca.", "u.a.", "d.h.", "т.е.", "т.д.",
    "т.п.", "напр.", "ст.", "ул.",
}


def split_sentences(text: str) -> list[str]:
    """Split on sentence boundaries and paragraph breaks, re-joining abbreviation splits."""
    out: list[str] = []
    for para in re.split(r"\n\s*\n|\n", text):
        para = para.strip()
        if not para:
            continue
        parts = _SENT_END_RE.split(para)
        buf = ""
        for part in parts:
            part = part.strip()
            if not part:
                continue
            buf = f"{buf} {part}".strip() if buf else part
            last = buf.split()[-1].lower() if buf.split() else ""
            if last in _ABBREVIATIONS or (len(last) <= 2 and last.endswith(".") and last[:-1].isalpha()):
                continue  # "e.g." / single-initial "J." -> keep accumulating
            out.append(buf)
            buf = ""
        if buf:
            out.append(buf)
    return out


def chunk_text(text: str, *, max_chars: int = 280, min_chars: int = 40) -> list[str]:
    """Group sentences into speakable chunks.

    Short sentences are merged so the engine is not called for 3-word fragments;
    very long sentences are split on commas / semicolons so first audio arrives fast.
    """
    chunks: list[str] = []
    buf = ""
    for sent in split_sentences(text):
        if len(sent) > max_chars:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.extend(_split_long(sent, max_chars))
            continue
        candidate = f"{buf} {sent}".strip() if buf else sent
        if buf and len(candidate) > max_chars:
            chunks.append(buf)
            buf = sent
        else:
            buf = candidate
        if len(buf) >= min_chars:
            chunks.append(buf)
            buf = ""
    if buf:
        if chunks and len(buf) < min_chars // 2 and len(chunks[-1]) + len(buf) <= max_chars:
            chunks[-1] = f"{chunks[-1]} {buf}"
        else:
            chunks.append(buf)
    return chunks


def _split_long(sent: str, max_chars: int) -> list[str]:
    pieces = re.split(r"(?<=[,;:—–])\s+", sent)
    out: list[str] = []
    buf = ""
    for p in pieces:
        cand = f"{buf} {p}".strip() if buf else p
        if buf and len(cand) > max_chars:
            out.append(buf)
            buf = p
        else:
            buf = cand
    if buf:
        out.append(buf)
    # last resort: hard-wrap anything still too long on whitespace
    final: list[str] = []
    for piece in out:
        while len(piece) > max_chars:
            cut = piece.rfind(" ", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            final.append(piece[:cut].strip())
            piece = piece[cut:].strip()
        if piece:
            final.append(piece)
    return final


# --------------------------------------------------------------------------- language

_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_LATIN_RE = re.compile(r"[A-Za-z\u00C0-\u024F]")
_UK_ONLY = set("іїєґІЇЄҐ")
_RU_ONLY = set("ыэёъЫЭЁЪ")
_DE_MARKERS = set("äöüßÄÖÜ")
_DE_WORDS = {
    "der", "die", "das", "und", "nicht", "ist", "ich", "ein", "eine", "mit", "auf", "für", "auch",
    "sich", "wir", "es", "zu", "von", "den", "dem", "des", "im", "oder", "aber", "wie", "noch",
    "sind", "wird", "werden", "kann", "habe", "haben", "sehr", "schon", "nur", "wenn", "dann",
}
_EN_WORDS = {
    "the", "and", "is", "are", "to", "of", "in", "it", "that", "this", "you", "for", "with",
    "on", "as", "be", "was", "have", "not", "but", "they", "we", "can", "will", "your", "from",
}
_FR_WORDS = {"le", "la", "les", "des", "est", "et", "une", "pour", "dans", "que", "qui", "pas", "vous"}
_ES_WORDS = {"el", "los", "las", "es", "por", "para", "con", "una", "que", "como", "pero", "más"}
_IT_WORDS = {"il", "gli", "che", "per", "con", "una", "sono", "della", "anche", "non", "questo"}
_PL_WORDS = {"jest", "nie", "się", "to", "na", "że", "jak", "ale", "czy", "oraz", "tak"}
_PL_MARKERS = set("ąęłńśźżĄĘŁŃŚŹŻ")


@dataclass(frozen=True)
class LangGuess:
    code: str
    confidence: float  # 0..1, heuristic only


def detect_language(text: str, default: str = "en") -> LangGuess:
    """Cheap script/stopword heuristic. Good enough to pick a Supertonic language tag.

    Distinguishes uk / ru / de / en / fr / es / it / pl. Anything else -> default.
    """
    if not text or not text.strip():
        return LangGuess(default, 0.0)
    cyr = len(_CYRILLIC_RE.findall(text))
    lat = len(_LATIN_RE.findall(text))
    if cyr == 0 and lat == 0:
        return LangGuess(default, 0.0)

    if cyr > lat:
        uk = sum(1 for ch in text if ch in _UK_ONLY)
        ru = sum(1 for ch in text if ch in _RU_ONLY)
        if uk == 0 and ru == 0:
            # ambiguous: apostrophes and "та", "це", "що" lean Ukrainian; "что", "это" Russian
            words = set(re.findall(r"[\u0400-\u04FF']+", text.lower()))
            uk += len(words & {"та", "це", "що", "як", "але", "він", "вона", "бути", "також", "дуже"})
            ru += len(words & {"что", "это", "как", "он", "она", "быть", "также", "очень", "если"})
        total = uk + ru
        if total == 0:
            return LangGuess("uk" if default == "uk" else "ru", 0.4)
        return LangGuess("uk", uk / total) if uk >= ru else LangGuess("ru", ru / total)

    lowered = text.lower()
    words = re.findall(r"[a-z\u00e0-\u024f]+", lowered)
    if not words:
        return LangGuess(default, 0.0)
    wordset = words if len(words) < 400 else words[:400]
    scores = {
        "de": sum(1 for w in wordset if w in _DE_WORDS) + 2 * sum(1 for ch in text if ch in _DE_MARKERS),
        "en": sum(1 for w in wordset if w in _EN_WORDS),
        "fr": sum(1 for w in wordset if w in _FR_WORDS),
        "es": sum(1 for w in wordset if w in _ES_WORDS),
        "it": sum(1 for w in wordset if w in _IT_WORDS),
        "pl": sum(1 for w in wordset if w in _PL_WORDS) + 2 * sum(1 for ch in text if ch in _PL_MARKERS),
    }
    best = max(scores, key=scores.get)
    total = sum(scores.values())
    if total == 0:
        return LangGuess(default, 0.2)
    return LangGuess(best, scores[best] / total)
