"""The sheet viewer's autosave reads the CSRF token from a <meta> tag in the
authenticated shell instead of relying on the logout form's hidden input."""
from __future__ import annotations

import re

import pytest

META = re.compile(r'<meta name="csrf-token" content="([^"]+)">')


@pytest.mark.django_db
def test_character_sheet_page_carries_the_csrf_meta_tag(client, user_factory, character_factory):
    owner = user_factory()
    character = character_factory(owner=owner, display_name="Meta")
    client.force_login(owner)
    html = client.get(f"/characters/{character.id}/").content.decode()
    match = META.search(html)
    assert match, "authenticated sheet pages must expose the csrf-token meta tag"
    assert len(match.group(1)) >= 32


@pytest.mark.django_db
def test_ship_sheet_page_carries_the_csrf_meta_tag(client, user_factory, ship_sheet):
    client.force_login(user_factory())
    html = client.get(f"/ships/{ship_sheet.id}/").content.decode()
    assert META.search(html)


@pytest.mark.django_db
def test_login_page_has_no_csrf_meta_tag(client):
    html = client.get("/account/login/").content.decode()
    assert not META.search(html)


def test_sheet_viewer_reads_the_meta_tag_before_the_form_input():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "static" / "sheets" / "sheet-viewer.js"
    ).read_text(encoding="utf-8")
    body = source[source.index("function getCsrfToken()") :]
    body = body[: body.index("\n  }\n")]
    assert body.index('meta[name="csrf-token"]') < body.index("csrfmiddlewaretoken")
