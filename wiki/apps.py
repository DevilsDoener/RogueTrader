import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class WikiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "wiki"

    def ready(self):
        from . import content

        try:
            content.initialize_repository()
        except Exception:  # noqa: BLE001 - startup must not crash the whole app
            logger.exception("Failed to initialize the wiki content repository at startup.")
