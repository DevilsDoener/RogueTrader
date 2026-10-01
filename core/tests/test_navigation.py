"""The primary navigation marks exactly one entry as the current page."""
import re

import pytest


def _current_nav_entries(html: str) -> list[str]:
    nav = re.search(r'<nav class="primary-nav".*?</nav>', html, re.S).group(0)
    return [
        re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", link)).strip()
        for link in re.findall(r'<a [^>]*aria-current="page"[^>]*>.*?</a>', nav, re.S)
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path_template", "expected"),
    [
        ("/dashboard/", "Kommandobr&uuml;cke"),
        ("/characters/", "Charaktere"),
        ("/characters/{character}/", "Charaktere"),
        ("/characters/{character}/delete/", "Charaktere"),
        ("/ships/{ship}/", "Schiff"),
        ("/ships/{ship}/history/", "Schiff"),
    ],
)
def test_nav_marks_exactly_one_current_entry(
    client, owner, character_factory, ship_sheet, path_template, expected
):
    character = character_factory(owner=owner, display_name="Nav")
    client.force_login(owner)

    response = client.get(path_template.format(character=character.pk, ship=ship_sheet.pk))

    assert response.status_code == 200
    assert _current_nav_entries(response.content.decode()) == [expected]
