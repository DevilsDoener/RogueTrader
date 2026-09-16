"""The served rulebook is English, and stays that way.

The corpus was transcribed from an English PDF but passed through a German
phase, and one chapter was still German when this was written. Nothing held
the translation in place, so this measures the text the wiki actually serves
rather than the raw files: a section that is hidden on purpose (transcription
bookkeeping) is allowed to stay German, because no reader sees it.
"""
import re

import pytest
from django.conf import settings

from wiki.content import WikiRepository

pytestmark = pytest.mark.skipif(
    not (settings.WIKI_CONTENT_ROOT / "03-Skills.md").exists(),
    reason="real wiki content is not available in this checkout",
)

#: Unambiguously German function words. Deliberately excludes English
#: homographs -- "die", "war", "am", "in" and "den" all occur in ordinary
#: English, and "a den of villainy" in the Koronus chapter would trip a
#: careless list.
GERMAN_FUNCTION_WORDS = frozenset(
    """der das den dem des eine einen einem eines und oder nicht ist sind waren
    wird werden kann muss wenn dann auch noch nur bei mit von zu fuer aus dieser
    diese dieses sich nach ueber unter durch gegen ohne zum zur beim seine ihre
    als wie sehr schon bereits jedoch aber sondern damit dass""".split()
)
GERMAN_FUNCTION_WORDS = GERMAN_FUNCTION_WORDS - {"den"}

#: A chapter may mention a German file name or proper noun; it may not be
#: written in German. The worst served chapter measured 0.12 % when this was
#: added, the offending file having been translated.
MAX_GERMAN_RATIO = 0.5

_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_WORD_RE = re.compile(r"[A-Za-zÄÖÜäöüß]+")

#: First bytes of a UTF-8 sequence when it is mistakenly decoded as latin-1 or
#: cp1252. Seven of these (an arrow, "â€™") survived in the career-paths
#: chapter until they were repaired.
MOJIBAKE_MARKERS = ("â", "Â", "Ã")


@pytest.fixture(scope="module")
def repository():
    return WikiRepository.load()


def _german_ratio(text: str) -> float:
    words = _WORD_RE.findall(text)
    if not words:
        return 0.0
    german = sum(
        1 for word in words if word.lower().translate(_UMLAUTS) in GERMAN_FUNCTION_WORDS
    )
    return 100.0 * german / len(words)


def test_no_served_chapter_is_written_in_german(repository):
    offenders = {}
    for chapter in repository.chapters():
        text = " ".join(section.plain_text for section in chapter.sections)
        ratio = _german_ratio(text)
        if ratio > MAX_GERMAN_RATIO:
            offenders[chapter.slug] = round(ratio, 2)

    assert offenders == {}, f"German text served to readers: {offenders}"


def test_no_served_section_title_is_german(repository):
    offenders = [
        (chapter.slug, section.title)
        for chapter in repository.chapters()
        for section in chapter.sections
        if _german_ratio(section.title) > 0
    ]

    assert offenders == []


def test_chapter_titles_are_english(repository):
    """They are the displayed chapter names, so they matter most."""
    offenders = [
        chapter.title
        for chapter in repository.chapters()
        if _german_ratio(chapter.title) > 0
    ]

    assert offenders == []


@pytest.mark.parametrize("marker", MOJIBAKE_MARKERS)
def test_no_content_file_carries_a_mojibake_marker(marker):
    offenders = {}
    for filename in settings.WIKI_CONTENT_ALLOWLIST:
        path = settings.WIKI_CONTENT_ROOT / filename
        if not path.is_file():
            continue
        count = path.read_text(encoding="utf-8").count(marker)
        if count:
            offenders[filename] = count

    assert offenders == {}, (
        f"{marker!r} suggests UTF-8 bytes were decoded as latin-1: {offenders}"
    )


def test_every_content_file_is_valid_utf8():
    broken = []
    for filename in settings.WIKI_CONTENT_ALLOWLIST:
        path = settings.WIKI_CONTENT_ROOT / filename
        if not path.is_file():
            continue
        try:
            path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            broken.append(filename)

    assert broken == []
