from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'accounts'
    verbose_name = 'Portal accounts'

    def ready(self):
        from . import checks  # noqa: F401 -- registers the deploy check
