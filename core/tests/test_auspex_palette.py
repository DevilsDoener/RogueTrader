"""The Auspex command palette is part of the authenticated shell only.

``templates/base.html`` renders the ``<dialog id="auspex">`` (opened by
``static/js/auspex.js``) and the "Strg K" hint for signed-in users; the bare
login page carries neither, so no anonymous page points at the suggest API.
"""
from django.urls import reverse


def test_authenticated_shell_renders_the_palette(client, owner):
    client.force_login(owner)

    content = client.get(reverse("dashboard")).content.decode()

    assert 'id="auspex"' in content
    assert 'data-suggest-url="/search/suggest/"' in content
    assert 'data-search-url="/search/"' in content
    assert 'role="combobox"' in content
    assert 'aria-controls="auspex-results"' in content
    # A real accessible name, not only the placeholder.
    assert 'aria-label="Regelwerk durchsuchen"' in content
    assert "js/auspex.js" in content
    assert 'class="topbar-search-kbd js-only"' in content
    # The idle/empty/error note is a live region beside the listbox.
    assert '<div class="auspex-note" role="status"></div>' in content
    # The shared rt-wiki-recent helper runs before every script using it.
    assert content.index("js/wiki-recent.js") < content.index("js/auspex.js")
    # The topbar form stays a plain GET search for readers without JS.
    assert 'id="topbar-search-input"' in content
    assert 'action="/search/"' in content


def test_login_page_has_no_palette(client):
    content = client.get(reverse("accounts:login")).content.decode()

    assert 'id="auspex"' not in content
    assert "/search/suggest/" not in content
    assert "js/auspex.js" not in content


def test_the_recent_helper_precedes_the_wiki_page_scripts(client, owner):
    client.force_login(owner)

    content = client.get(reverse("wiki:index")).content.decode()

    assert content.index("js/wiki-recent.js") < content.index("js/wiki-library.js")
