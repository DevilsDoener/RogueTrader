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


def _require_role_change_allowed(actor, user, portal_admin: bool) -> None:
    """Taking the admin role away: never from yourself, never from the last active admin."""
    if portal_admin or not user.is_portal_admin:
        return
    if user.pk == actor.pk:
        _refuse(
            actor,
            user,
            "revoke-own-admin",
            "Du kannst dir die Admin-Rolle nicht selbst entziehen. "
            "Bitte einen anderen Portal-Administrator darum.",
        )
    others = (
        get_user_model()
        .objects.filter(is_portal_admin=True, is_active=True)
        .exclude(pk=user.pk)
    )
    if not others.exists():
        _refuse(
            actor,
            user,
            "revoke-last-admin",
            "Das ist der letzte aktive Portal-Administrator; die Admin-Rolle bleibt.",
        )


def _log_role_change(actor, user) -> None:
    _log_managed_account_event(
        "managed_account_role_changed",
        actor=actor,
        target=user,
        detail=f"portal_admin={user.is_portal_admin}",
    )


@transaction.atomic
def create_managed_user(
    *, actor, username: str, temporary_password: str, portal_admin: bool = False
):
    _require_portal_admin(actor)
    user_model = get_user_model()
    user = user_model(
        username=usernames.clean_username(username),
        is_active=True,
        is_staff=False,
        is_superuser=False,
        is_portal_admin=portal_admin,
        must_change_password=True,
    )
    validate_password(temporary_password, user)
    user.set_password(temporary_password)
    user.save()
    _log_managed_account_event("managed_account_created", actor=actor, target=user)
    if portal_admin:
        _log_role_change(actor, user)
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
def update_managed_user(
    *, actor, user, username: str, active: bool, portal_admin: bool | None = None
):
    """Rename, (de)activate and -- if ``portal_admin`` is given -- set the role.

    ``portal_admin=None`` leaves the role as it is. A role change is logged as
    its own ``managed_account_role_changed`` event.
    """
    _require_portal_admin(actor)
    _require_manageable_user(actor, user)
    _require_not_self_deactivation(actor, user, active)
    _require_another_active_portal_admin(actor, user, active)
    role_changes = portal_admin is not None and portal_admin != user.is_portal_admin
    if role_changes:
        _require_role_change_allowed(actor, user, portal_admin)
    old_username = user.get_username()
    user.username = usernames.clean_username(username, existing=user)
    user.is_active = active
    fields = ["username", "is_active"]
    if role_changes:
        user.is_portal_admin = portal_admin
        fields.append("is_portal_admin")
    user.save(update_fields=fields)
    _log_managed_account_event(
        "managed_account_updated",
        actor=actor,
        target=user,
        detail=f"old_username={old_username!r} new_username={user.username!r} active={active}",
    )
    if role_changes:
        _log_role_change(actor, user)
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


def deletion_summary(user) -> dict:
    """What deleting ``user`` takes with it, for the confirmation page and the log.

    Their characters are deleted with the account (``CharacterSheet.owner`` is
    CASCADE); their entries in the ship history and the network stay, without
    a name (SET_NULL).
    """
    from sheets.models import CharacterSheet

    names = list(
        CharacterSheet.objects.filter(owner=user)
        .order_by("display_name")
        .values_list("display_name", flat=True)
    )
    return {"character_names": [name or "Unbenannter Charakter" for name in names]}


@transaction.atomic
def delete_managed_user(*, actor, user) -> None:
    """Delete an account for good, with the same guard rails as deactivating.

    Never one's own account, never the last active portal admin, never a
    Django staff/superuser account.
    """
    _require_portal_admin(actor)
    _require_manageable_user(actor, user)
    if user.pk == actor.pk:
        _refuse(actor, user, "delete-self", "Du kannst dein eigenes Konto nicht löschen.")
    if user.is_portal_admin:
        others = (
            get_user_model()
            .objects.filter(is_portal_admin=True, is_active=True)
            .exclude(pk=user.pk)
        )
        if not others.exists():
            _refuse(
                actor,
                user,
                "delete-last-admin",
                "Das ist der letzte aktive Portal-Administrator und kann nicht gelöscht werden.",
            )
    summary = deletion_summary(user)
    _log_managed_account_event(
        "managed_account_deleted",
        actor=actor,
        target=user,
        detail=f"characters={len(summary['character_names'])}",
    )
    user.delete()
