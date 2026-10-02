"""Shared fixtures for Playwright-driven end-to-end tests.

There is no pytest-playwright plugin in this project (see requirements-dev.in)
-- these fixtures drive ``playwright.sync_api`` directly against Django's
``live_server`` fixture (pytest-django), so a real Chromium instance talks
to a real HTTP server backed by the test database.

Playwright's sync API pumps its asyncio event loop via a greenlet running
*on the calling thread*, and that loop is left "running" (from that
thread's point of view) for as long as the ``sync_playwright()`` context is
open -- i.e. for this whole test session. If that thread is also the one
pytest-django uses for direct (non-HTTP) Django ORM calls -- database setup,
``transactional_db`` teardown/flush, or anything a test does directly with
the ORM -- every one of those calls fails with
``SynchronousOnlyOperation: You cannot call this from an async context``,
because Django's ``async_unsafe`` guard sees a "running" loop on that
thread. The fix here is to run the entire Playwright driver (browser,
contexts, pages) on one dedicated worker thread, and have test code talk to
it through ``_ThreadedProxy``, which transparently marshals every call
across to that thread and back. Django/pytest-django fixtures (``db``,
``transactional_db``, ``live_server``, factories) then keep running on the
normal pytest thread, untouched by Playwright's event loop.
"""
from __future__ import annotations

import concurrent.futures
import time

import pytest
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from wiki.content import WikiRepository, get_repository, set_repository_for_tests

DEFAULT_PASSWORD = "Valid-Password-42!"

_PRIMITIVE_TYPES = (str, int, float, bool, bytes, type(None))


def _wrap(worker: "_PlaywrightWorker", value):
    if isinstance(value, _PRIMITIVE_TYPES):
        return value
    if isinstance(value, list):
        return [_wrap(worker, v) for v in value]
    if isinstance(value, tuple):
        return tuple(_wrap(worker, v) for v in value)
    if isinstance(value, dict):
        return {k: _wrap(worker, v) for k, v in value.items()}
    return _ThreadedProxy(worker, value)


def _unwrap(value):
    return value._target if isinstance(value, _ThreadedProxy) else value


class _ThreadedProxy:
    """Wraps a Playwright object so every call on it runs on the worker
    thread that owns Playwright's event loop, never on the caller's thread.
    """

    __slots__ = ("_worker", "_target")

    def __init__(self, worker: "_PlaywrightWorker", target):
        object.__setattr__(self, "_worker", worker)
        object.__setattr__(self, "_target", target)

    def __getattr__(self, name):
        if name == "wait_for_function" and isinstance(self._target, Page):
            return self._wait_for_function
        attr = getattr(self._target, name)
        if not callable(attr):
            return _wrap(self._worker, attr)

        def method(*args, **kwargs):
            real_args = tuple(_unwrap(a) for a in args)
            real_kwargs = {k: _unwrap(v) for k, v in kwargs.items()}
            result = self._worker.run(attr, *real_args, **real_kwargs)
            return _wrap(self._worker, result)

        return method

    def _wait_for_function(self, expression, *, arg=None, timeout=30_000, **_ignored):
        """``Page.wait_for_function`` that works under the portal's CSP.

        Playwright's own implementation ``eval``s the predicate inside the page,
        which ``script-src 'self'`` (no ``unsafe-eval``) refuses. ``evaluate``
        goes through the debugging protocol instead, so the predicate is polled
        with it: the same expression/function rules, same truthiness, same
        timeout error. This keeps the whole e2e suite running with the policy
        enforced rather than bypassing it.
        """
        page, real_arg = self._target, _unwrap(arg)
        deadline = time.monotonic() + timeout / 1000

        def poll():
            while True:
                result = page.evaluate(expression, real_arg)
                if result:
                    return result
                if time.monotonic() > deadline:
                    raise PlaywrightTimeoutError(
                        f"Page.wait_for_function: Timeout {timeout}ms exceeded."
                    )
                page.wait_for_timeout(50)

        return _wrap(self._worker, self._worker.run(poll))

    def __repr__(self):  # pragma: no cover - debugging aid only
        return f"_ThreadedProxy({self._target!r})"


class _PlaywrightWorker:
    """Owns a single background thread running Playwright's sync driver."""

    def __init__(self):
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="playwright-driver"
        )
        self.run(self._start)

    def _start(self):
        self._playwright_cm = sync_playwright()
        self._playwright = self._playwright_cm.__enter__()
        self._browser = self._playwright.chromium.launch()

    def run(self, fn, *args, **kwargs):
        return self._executor.submit(fn, *args, **kwargs).result()

    def new_page(self):
        def _create():
            context = self._browser.new_context()
            return context, context.new_page()

        context, page = self.run(_create)
        return _ThreadedProxy(self, context), _ThreadedProxy(self, page)

    def close_context(self, context: _ThreadedProxy):
        self.run(context._target.close)

    def shutdown(self):
        def _stop():
            try:
                self._browser.close()
            finally:
                self._playwright_cm.__exit__(None, None, None)

        try:
            self.run(_stop)
        finally:
            self._executor.shutdown(wait=True)


@pytest.fixture(scope="session")
def _playwright_worker():
    worker = _PlaywrightWorker()
    yield worker
    worker.shutdown()


@pytest.fixture
def page(_playwright_worker):
    context, pg = _playwright_worker.new_page()
    yield pg
    _playwright_worker.close_context(context)


@pytest.fixture
def second_page(_playwright_worker):
    """A second, independent browser context (separate cookies/session) so
    two different logged-in users can be driven concurrently against the
    same live server -- used by the shared-ship concurrency tests."""
    context, pg = _playwright_worker.new_page()
    yield pg
    _playwright_worker.close_context(context)


# The live server answers from another thread, so these tests need a
# flushed (not rolled-back) database. The overrides below take the root
# conftest's fixture of the same name and add ``transactional_db``; ``owner``,
# ``other_user``, ``portal_admin`` and ``character_factory`` build on them.
@pytest.fixture
def user_factory(transactional_db, user_factory):
    return user_factory


@pytest.fixture
def ship_sheet(transactional_db, ship_sheet):
    """The root fixture's migration-seeded ship. ``transactional_db`` flushes
    the database between tests without re-running data migrations, so after
    the first flush the root fixture's create-if-missing fallback is what
    keeps "the" active ship available here."""
    return ship_sheet


def login_via_browser(page, live_server, *, username, password=DEFAULT_PASSWORD):
    page.goto(f"{live_server.url}/account/login/")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


# -- Shared browser helpers ---------------------------------------------------

#: The two desktop widths every geometry contract is checked at: the minimum
#: supported width and a wide one.
VIEWPORT_MINIMUM = {"width": 1024, "height": 768}
VIEWPORT_WIDE = {"width": 1440, "height": 900}
DESKTOP_VIEWPORTS = (VIEWPORT_MINIMUM, VIEWPORT_WIDE)
NAMED_DESKTOP_VIEWPORTS = (
    ("desktop-minimum", VIEWPORT_MINIMUM),
    ("desktop-wide", VIEWPORT_WIDE),
)


def wait_saved(page):
    """Blocks until the sheet viewer reports that the last edit was saved."""
    page.wait_for_function(
        "document.getElementById('sheet-save-status').textContent === 'Gespeichert'",
        timeout=10_000,
    )


def wait_for_fit(page):
    """Blocks until the canvases are re-fitted to the column.

    The viewer re-fits via JS on resize (one event tick). A test that changes
    the viewport after load and measures at once has to wait for that: at 100%
    zoom a fitted canvas's rendered width equals the column (wrapper) width.
    """
    page.wait_for_function(
        """() => {
          const wr = document.getElementById('sheet-canvas-wrapper');
          const cs = document.querySelectorAll('.sheet-page .sheet-canvas');
          if (!wr || !cs.length) return false;
          return [...cs].every(
            (c) => Math.abs(c.getBoundingClientRect().width - wr.clientWidth) <= 1
          );
        }"""
    )


def open_character(page, live_server, owner, character_factory, *, values=None, admin=None):
    """Creates a character for ``owner``, logs in and opens its sheet.

    With ``admin`` the read-only admin viewer is opened as that user instead.
    """
    character = character_factory(owner=owner, values=values or {})
    login_via_browser(page, live_server, username=(admin or owner).username)
    route = "portal-admin/characters" if admin else "characters"
    page.goto(f"{live_server.url}/{route}/{character.id}/")
    page.wait_for_selector('[data-field-id="c1_character_name"]')
    return character


def open_ship(page, live_server, user, ship_sheet, *, values=None):
    """Logs ``user`` in and opens the shared ship, optionally pre-filled."""
    if values:
        ship_sheet.values = {**ship_sheet.values, **values}
        ship_sheet.save(update_fields=["values"])
    login_via_browser(page, live_server, username=user.username)
    page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    page.wait_for_selector('[data-field-id="ship_name"]')
    return ship_sheet


# All lengths below are RENDERED (post-transform) pixels: getBoundingClientRect
# already includes the canvas transform, and font size and line height -- which
# are computed in the canvas's fixed element space -- are multiplied by
# --sheet-scale so they land in the same rendered space. Every "shared
# canvas-relative size" / "fits its box" invariant is then a comparison between
# mutually consistent values. scrollHeight/clientHeight are in the element's own
# space and already consistent with each other.
_TEXT_METRICS_JS = """(input) => {
  const canvasEl = input.closest('.sheet-canvas');
  const scale = Number.parseFloat(
    getComputedStyle(canvasEl).getPropertyValue('--sheet-scale')
  ) || 1;
  const px = (value) => Number.parseFloat(value) || 0;
  const field = input.closest('.sheet-field').getBoundingClientRect();
  const canvas = canvasEl.getBoundingClientRect();
  const rect = input.getBoundingClientRect();
  const style = getComputedStyle(input);
  return {
    id: input.dataset.fieldId,
    pageId: input.closest('.sheet-page').dataset.pageId,
    value: input.value,
    color: style.color,
    bottomDelta: Math.abs(rect.bottom - field.bottom),
    fontFamily: style.fontFamily,
    fontSize: px(style.fontSize) * scale,
    renderedLineHeight: px(style.lineHeight) * scale,
    contentHeight: rect.height
      - px(style.paddingTop) - px(style.paddingBottom)
      - px(style.borderTopWidth) - px(style.borderBottomWidth),
    clientHeight: input.clientHeight,
    scrollHeight: input.scrollHeight,
    inputHeight: rect.height,
    fieldHeight: field.height,
    canvasWidth: canvas.width,
  };
}"""


def text_metrics(page, field_id):
    """Rendered text metrics of one text input (see ``_TEXT_METRICS_JS``)."""
    return page.locator(f'[data-field-id="{field_id}"]').evaluate(_TEXT_METRICS_JS)


def all_text_metrics(page):
    """Metrics of every bottom-anchored line-text input on the open sheet.

    The centred value fields (characteristics, value boxes without a printed
    line) deliberately fill their box and use their own size, so they are not
    part of the shared line-text contract.
    """
    return page.locator(".sheet-text:not(.sheet-text--center)").evaluate_all(
        f"(inputs) => inputs.map({_TEXT_METRICS_JS})"
    )


@pytest.fixture
def real_corpus(settings):
    """Serve the real ``content/`` chapters to the live server for one test.

    The wiki e2e files (library filter, chapter reader, Auspex palette) check
    behaviour on the chapters a reader actually sees; the previous repository
    is restored afterwards.
    """
    original_repository = get_repository()
    settings.WIKI_CONTENT_ROOT = settings.BASE_DIR / "content"
    settings.WIKI_CONTENT_ALLOWLIST = settings.WIKI_DEFAULT_CONTENT_ALLOWLIST
    set_repository_for_tests(WikiRepository.load())
    try:
        yield
    finally:
        set_repository_for_tests(original_repository)
