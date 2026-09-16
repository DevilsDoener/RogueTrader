import logging

from django.apps import AppConfig
from django.conf import settings
from django.core.checks import register
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class WikiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "wiki"

    def ready(self):
        from . import content
        from .checks import check_wiki_content

        register(check_wiki_content)

        strict = getattr(settings, "WIKI_STRICT_CONTENT", False)

        try:
            content.initialize_repository()
        except Exception:  # noqa: BLE001 - startup must not crash the whole app
            logger.exception("Failed to initialize the wiki content repository at startup.")
            # In a deployed container a failure here means the content mount is
            # wrong and every wiki page would 500 or come back empty. Failing to
            # boot is the honest outcome; locally the default stays forgiving so
            # an unrelated task is not blocked by a broken chapter.
            if strict:
                raise
            return

        # The common misconfiguration -- a wrong or missing content mount --
        # does not raise: load() logs each unreadable file and returns an empty
        # repository. Catching only exceptions would let the container come up
        # and serve a wiki with no chapters at all, which is exactly what strict
        # mode exists to prevent. Partial loss is caught separately, and before
        # boot, by the `manage.py check` in wiki/checks.py.
        if strict and settings.WIKI_CONTENT_ALLOWLIST and not content.get_repository().chapters():
            raise ImproperlyConfigured(
                "The wiki content repository loaded no chapters from "
                f"{settings.WIKI_CONTENT_ROOT}. Check that the content directory "
                "is mounted and readable. Set WIKI_STRICT_CONTENT=false to boot "
                "anyway with an empty wiki."
            )
