import logging

from django.apps import AppConfig
from django.conf import settings
from django.core.checks import register

logger = logging.getLogger(__name__)


class WikiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "wiki"

    def ready(self):
        from . import content
        from .checks import check_wiki_content

        register(check_wiki_content)

        try:
            content.initialize_repository()
        except Exception:  # noqa: BLE001 - startup must not crash the whole app
            logger.exception("Failed to initialize the wiki content repository at startup.")
            # In a deployed container a failure here means the content mount is
            # wrong and every wiki page would 500 or come back empty. Failing to
            # boot is the honest outcome; locally the default stays forgiving so
            # an unrelated task is not blocked by a broken chapter.
            if getattr(settings, "WIKI_STRICT_CONTENT", False):
                raise
