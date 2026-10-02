"""Deployment check: has the operator said which proxy to believe?"""
from django.conf import settings
from django.core.checks import Tags, Warning as CheckWarning, register

PROXY_NOT_TRUSTED = "accounts.W001"


@register(Tags.security, deploy=True)
def check_trusted_proxy(app_configs, **kwargs):
    if settings.DEBUG or settings.TRUSTED_PROXY_IPS:
        return []
    return [
        CheckWarning(
            "TRUSTED_PROXY_IPS is empty: every login attempt and audit record is "
            "attributed to the reverse proxy's (or Docker gateway's) address, and the "
            "login throttle cannot count failures per client address.",
            hint="Set TRUSTED_PROXY_IPS to the proxy's address as the container "
            "sees it (docs/operations.md, section 2).",
            id=PROXY_NOT_TRUSTED,
        )
    ]
