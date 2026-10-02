"""Browser behaviour of the sheet viewer's autosave and of the ship history.

* Quick successive edits of one field never conflict with the user's own
  previous save (saves are serialized per field).
* Edits still waiting for the debounce are sent when the page is hidden or
  closed (``pagehide``), with ``keepalive`` so the request survives.
* The ship history shows a short German message instead of injecting a login
  page or an error page, and never turns fetched text into markup.
"""
from __future__ import annotations

import pytest

from sheets.models import SheetChange

from .conftest import login_via_browser, open_ship, wait_saved

pytestmark = pytest.mark.django_db(transaction=True)

_SLOW_FIRST_RESPONSE_JS = """() => {
  const original = window.fetch;
  let calls = 0;
  window.fetch = (...args) => {
    calls += 1;
    const slow = calls === 1;
    return original(...args).then(
      (response) => (slow ? new Promise((done) => setTimeout(() => done(response), 1500)) : response)
    );
  };
}"""

_RECORD_FETCHES_JS = """() => {
  window.__fetches = [];
  const original = window.fetch;
  window.fetch = (url, options) => {
    window.__fetches.push({ url: String(url), keepalive: Boolean(options && options.keepalive) });
    return original(url, options);
  };
}"""


def test_a_second_edit_while_the_first_save_is_in_flight_does_not_conflict(
    page, live_server, user_factory, ship_sheet
):
    open_ship(page, live_server, user_factory(), ship_sheet)
    page.wait_for_selector('[data-field-id="ship_name"]')
    page.evaluate(_SLOW_FIRST_RESPONSE_JS)

    name = page.locator('[data-field-id="ship_name"]')
    name.fill("A")
    page.wait_for_timeout(900)  # debounce fired, response still pending
    name.fill("AB")

    page.wait_for_function(
        "document.querySelector('[data-field-id=\"ship_name\"]').dataset.version === '2'",
        timeout=10_000,
    )
    wait_saved(page)
    assert page.locator(".sheet-conflict-panel").count() == 0

    page.reload()
    page.wait_for_selector('[data-field-id="ship_name"]')
    assert page.input_value('[data-field-id="ship_name"]') == "AB"


@pytest.mark.parametrize("event", ["pagehide", "visibilitychange"])
def test_pending_edits_are_sent_when_the_page_is_hidden(
    page, live_server, user_factory, ship_sheet, event
):
    open_ship(page, live_server, user_factory(), ship_sheet)
    page.wait_for_selector('[data-field-id="ship_name"]')
    page.evaluate(_RECORD_FETCHES_JS)

    page.locator('[data-field-id="ship_name"]').fill("Rosinante")
    # Well inside the 600 ms debounce window: nothing has been sent yet.
    assert page.evaluate("window.__fetches.length") == 0
    if event == "pagehide":
        page.evaluate("window.dispatchEvent(new Event('pagehide'))")
    else:
        page.evaluate(
            "Object.defineProperty(document, 'visibilityState', {value: 'hidden', configurable: true});"
            "document.dispatchEvent(new Event('visibilitychange'))"
        )

    sent = page.evaluate("window.__fetches")
    assert len(sent) == 1
    assert sent[0]["keepalive"] is True
    assert "/fields/ship_name/" in sent[0]["url"]
    wait_saved(page)
    page.wait_for_timeout(900)  # the cancelled debounce must not send a second copy
    assert page.evaluate("window.__fetches.length") == 1


def _open_history(page, live_server, user, ship_sheet, *, old, new):
    SheetChange.objects.create(
        ship=ship_sheet, actor=user, field_id="ship_name",
        old_value=old, new_value=new, resulting_version=1,
    )
    login_via_browser(page, live_server, username=user.username)
    page.goto(f"{live_server.url}/ships/{ship_sheet.id}/history/")
    page.wait_for_selector("#ship-history-table")


def test_history_details_are_shown_as_text_not_markup(page, live_server, user_factory, ship_sheet):
    payload = "<img src=x onerror=window.__pwned=1>"
    _open_history(page, live_server, user_factory(), ship_sheet, old=payload, new="<b>fett</b>")

    page.locator(".ship-history-expand").first.click()
    page.wait_for_function(
        "document.querySelector('#ship-history-table dl') !== null", timeout=5000
    )
    details = page.evaluate("document.querySelector('#ship-history-table dl').innerText")
    assert payload in details and "<b>fett</b>" in details
    assert not page.evaluate("!!document.querySelector('#ship-history-table img, #ship-history-table b')")
    assert page.evaluate("window.__pwned") is None


def test_history_details_failure_shows_a_short_german_message(
    page, live_server, user_factory, ship_sheet
):
    _open_history(page, live_server, user_factory(), ship_sheet, old="alt", new="neu")
    # The session has gone: the detail request is redirected to the login page.
    page.context.clear_cookies()

    page.locator(".ship-history-expand").first.click()
    page.wait_for_function(
        "document.querySelector('#ship-history-table').innerText"
        ".includes('Die Details konnten nicht geladen werden.')",
        timeout=5000,
    )
    assert not page.evaluate("!!document.querySelector('#ship-history-table input, #ship-history-table form')")
    assert not page.evaluate("!!document.querySelector('#ship-history-table dl')")
