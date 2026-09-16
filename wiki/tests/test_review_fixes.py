"""Regression tests for the two Important findings from the Task 3 code review.

Kept separate from the adopted RED test files (test_content.py, test_markdown.py,
test_search.py, test_views.py), which are not to be modified.
"""
import re

import pytest
from django.urls import reverse

from wiki.content import WikiRepository, set_repository_for_tests


def _heading_texts(html: str, level: int) -> list[str]:
    """Visible text of every ``<hN>`` on the page, permalink anchor removed.

    Asserting on the exact string ``<h2>Details</h2>`` would now fail for a
    cosmetic reason: every heading carries a permalink ``<a class="wiki-anchor">``
    since headings moved out of the sanitized body HTML and into the template
    (see wiki/templates/wiki/_section.html). The behaviour these tests actually
    pin -- which headings exist, and how many -- is unchanged.
    """
    blocks = re.findall(rf"<h{level}[^>]*>(.*?)</h{level}>", html, re.DOTALL)
    without_anchor = [
        re.sub(r'<a class="wiki-anchor".*?</a>', "", block, flags=re.DOTALL)
        for block in blocks
    ]
    return [re.sub(r"<[^>]+>", "", text).strip() for text in without_anchor]


def test_fenced_code_block_heading_marker_does_not_start_new_section(tmp_path, settings):
    (tmp_path / "01-Chapter.md").write_text(
        "# Chapter\n\n"
        "## Real Section\nSome text.\n\n"
        "```\n## not a heading\n```\n\n"
        "More text.",
        encoding="utf-8",
    )
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Chapter.md"]

    chapter = WikiRepository.load().get_chapter("chapter")

    assert [section.id for section in chapter.sections] == ["real-section"]


@pytest.mark.django_db
def test_chapter_intro_heading_is_not_duplicated_when_slug_and_title_differ(
    client, user_factory, tmp_path, settings
):
    # The filename-derived chapter slug ("second") and the H1-derived intro
    # section id ("plasma-doctrine") deliberately differ here, which is the
    # exact case the reviewed template bug mishandled.
    (tmp_path / "02-Second.md").write_text(
        "# Plasma Doctrine\nIntro body text.\n\n## Details\nMore text.",
        encoding="utf-8",
    )
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["02-Second.md"]
    set_repository_for_tests(WikiRepository.load())
    client.force_login(user_factory())

    response = client.get(reverse("wiki:chapter", kwargs={"chapter_slug": "second"}))
    content = response.content.decode()

    assert response.status_code == 200
    # The intro section's title equals the chapter title, so the chapter
    # heading must appear exactly once, as the <h1>; the intro section must
    # not render its own duplicate <h2> with the same text. The real "##
    # Details" section still gets its <h2> normally.
    assert _heading_texts(content, 1) == ["Plasma Doctrine"]
    assert _heading_texts(content, 2) == ["Details"]
