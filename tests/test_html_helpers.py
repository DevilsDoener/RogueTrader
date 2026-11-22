"""The structural HTML helpers in ``tests/html.py`` that the view tests rely on."""
import pytest

from tests.html import attr, has_attr, has_link, select, select_one, text, texts

PAGE = """
<nav id="primary-nav" class="primary-nav">
  <ul>
    <li><a href="/dashboard/">Kommandobrücke</a></li>
    <li class="primary-nav-wiki">
      <a href="/wiki/" aria-current="page">  Wiki  </a>
      <ul class="primary-nav-sub"><li><a href="/wiki/skills/">Skills</a></li></ul>
    </li>
  </ul>
</nav>
<main>
  <p class="meta muted">Rogue Trader · <strong>Rank 2</strong></p>
  <input type="checkbox" name="admin" checked>
  <a href="/wiki/">Zur Bibliothek</a>
</main>
"""


def test_select_by_tag_id_class_and_attribute():
    assert texts(PAGE, "nav#primary-nav a[aria-current=page]") == ["Wiki"]
    assert texts(PAGE, ".primary-nav-sub a") == ["Skills"]
    assert len(select(PAGE, "a")) == 4
    assert select(PAGE, "a[href='/missing/']") == []


def test_classes_match_in_any_order_and_subset():
    assert text(select_one(PAGE, "p.muted.meta")) == "Rogue Trader · Rank 2"


def test_descendant_combinator_and_no_duplicates():
    assert texts(PAGE, "nav li a") == ["Kommandobrücke", "Wiki", "Skills"]


def test_boolean_attributes():
    checkbox = select_one(PAGE, "input[name=admin]")
    assert has_attr(checkbox, "checked")
    assert attr(checkbox, "type") == "checkbox"


def test_links():
    assert has_link(PAGE, "/wiki/")
    assert has_link(PAGE, "/wiki/", "Zur Bibliothek")
    assert not has_link(PAGE, "/wiki/", "Gibt es nicht")


def test_select_one_fails_loudly():
    with pytest.raises(AssertionError, match="expected 1 element, found 4"):
        select_one(PAGE, "a")


def test_unsupported_selector_is_an_error():
    with pytest.raises(ValueError):
        select(PAGE, "a > b")
