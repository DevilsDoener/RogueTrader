"""Shared fixtures for Playwright-driven end-to-end tests.

There is no pytest-playwright plugin in this project (see requirements.txt)
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
import uuid

import pytest
from playwright.sync_api import sync_playwright

from sheets.models import CharacterSheet, ShipSheet

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
        attr = getattr(self._target, name)
        if not callable(attr):
            return _wrap(self._worker, attr)

        def method(*args, **kwargs):
            real_args = tuple(_unwrap(a) for a in args)
            real_kwargs = {k: _unwrap(v) for k, v in kwargs.items()}
            result = self._worker.run(attr, *real_args, **real_kwargs)
            return _wrap(self._worker, result)

        return method

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


@pytest.fixture
def user_factory(transactional_db):
    def create_user(**attributes):
        from django.contrib.auth import get_user_model

        password = attributes.pop("password", DEFAULT_PASSWORD)
        attributes.setdefault("must_change_password", False)
        username = attributes.pop("username", None) or f"user-{uuid.uuid4().hex[:8]}"
        return get_user_model().objects.create_user(
            username=username, password=password, **attributes
        )

    return create_user


@pytest.fixture
def owner(user_factory):
    return user_factory(username=f"owner-{uuid.uuid4().hex[:8]}")


@pytest.fixture
def other_user(user_factory):
    return user_factory(username=f"other-{uuid.uuid4().hex[:8]}")


@pytest.fixture
def portal_admin(user_factory):
    return user_factory(username=f"admin-{uuid.uuid4().hex[:8]}", is_portal_admin=True)


@pytest.fixture
def character_factory(user_factory):
    def create_character(*, owner=None, display_name="", **attributes):
        if owner is None:
            owner = user_factory()
        return CharacterSheet.objects.create(owner=owner, display_name=display_name, **attributes)

    return create_character


@pytest.fixture
def ship_sheet(transactional_db):
    return ShipSheet.objects.create(display_name="Gemeinsames Schiff")


def login_via_browser(page, live_server, *, username, password=DEFAULT_PASSWORD):
    page.goto(f"{live_server.url}/account/login/")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
