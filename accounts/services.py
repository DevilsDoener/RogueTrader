import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied
from django.db import transaction

from . import usernames

audit_logger = logging.getLogger("accounts.audit")


class AccountRuleViolation(Exception):
    """A rule that protects the portal's own administrators was hit.

    The message is German ("du") and meant for the person who tried it."""


def _log_managed_account_event(event_kind: str, *, actor, target, detail: str = "") -> None:
    audit_logger.info(
        "%s actor=%r target=%r%s",
        event_kind,
        actor.get_username(),
        target.get_username(),
        f" {detail}" if detail else "",
    )


def log_denied(actor, action: str, target=None) -> None:
    """Record a refused attempt on the account management routes."""
    audit_logger.warning(
        "managed_account_denied actor=%r action=%s target=%r",
        actor.get_username() if actor.is_authenticated else "<anonymous>",
        action,
        target.get_username() if target is not None else None,
    )


def _require_portal_admin(actor) -> None:
    if not actor.is_authenticated or not actor.is_portal_admin:
        log_denied(actor, "not-a-portal-admin")
        raise PermissionDenied("Portal administrator permission is required.")


def _require_manageable_user(actor, user) -> None:
    if not user.is_manageable:
        log_denied(actor, "unmanageable-account", user)
        raise PermissionDenied("Django administrator accounts cannot be managed here.")


def _refuse(actor, user, action: str, message: str):
    log_denied(actor, action, user)
    raise AccountRuleViolation(message)


def _require_not_self_deactivation(actor, user, active: bool) -> None:
    if not active and user.pk == actor.pk:
        _refuse(actor, user, "deactivate-self", "Du kannst dein eigenes Konto nicht deaktivieren.")


def _require_another_active_portal_admin(actor, user, active: bool) -> None:
    """Deactivating a portal admin must leave at least one active one."""
    if active or not user.is_portal_admin:
        return
    others = (
        get_user_model()
        .objects.filter(is_portal_admin=True, is_active=True)
        .exclude(pk=user.pk)
    )
    if not others.exists():
        _refuse(
            actor,
            user,
            "deactivate-last-admin",
            "Das ist der letzte aktive Portal-Administrator und kann nicht deaktiviert werden.",
        )


@transaction.atomic
def create_managed_user(*, actor, username: str, temporary_password: str):
    _require_portal_admin(actor)
    user_model = get_user_model()
    user = user_model(
        username=usernames.clean_username(username),
        is_active=True,
        is_staff=False,
        is_superuser=False,
        is_portal_admin=False,
        must_change_password=True,
    )
    validate_password(temporary_password, user)
    user.set_password(temporary_password)
    user.save()
    _log_managed_account_event("managed_account_created", actor=actor, target=user)
    return user


@transaction.atomic
def set_user_active(*, actor, user, active: bool):
    _require_portal_admin(actor)
    _require_manageable_user(actor, user)
    _require_not_self_deactivation(actor, user, active)
    _require_another_active_portal_admin(actor, user, active)
    user.is_active = active
    user.save(update_fields=["is_active"])
    _log_managed_account_event(
        "managed_account_reactivated" if active else "managed_account_deactivated",
        actor=actor,
        target=user,
    )
    return user


@transaction.atomic
def update_managed_user(*, actor, user, username: str, active: bool):
    _require_portal_admin(actor)
    _require_manageable_user(actor, user)
    _require_not_self_deactivation(actor, user, active)
    _require_another_active_portal_admin(actor, user, active)
    old_username = user.get_username()
    user.username = usernames.clean_username(username, existing=user)
    user.is_active = active
    user.save(update_fields=["username", "is_active"])
    _log_managed_account_event(
        "managed_account_updated",
        actor=actor,
        target=user,
        detail=f"old_username={old_username!r} new_username={user.username!r} active={active}",
    )
    return user


@transaction.atomic
def reset_temporary_password(*, actor, user, temporary_password: str):
    _require_portal_admin(actor)
    _require_manageable_user(actor, user)
    if user.pk == actor.pk:
        _refuse(
            actor,
            user,
            "reset-own-password",
            "Dein eigenes Passwort kannst du hier nicht zurücksetzen. "
            "Bitte einen anderen Portal-Administrator darum.",
        )
    validate_password(temporary_password, user)
    user.set_password(temporary_password)
    user.must_change_password = True
    user.save(update_fields=["password", "must_change_password"])
    _log_managed_account_event("managed_account_password_reset", actor=actor, target=user)
    return user
