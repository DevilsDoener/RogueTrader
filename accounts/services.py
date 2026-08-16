from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied
from django.db import transaction


def _require_portal_admin(actor) -> None:
    if not actor.is_authenticated or not actor.is_portal_admin:
        raise PermissionDenied("Portal administrator permission is required.")


def _require_manageable_user(user) -> None:
    if user.is_staff or user.is_superuser:
        raise PermissionDenied("Django administrator accounts cannot be managed here.")


@transaction.atomic
def create_managed_user(*, actor, username: str, temporary_password: str):
    _require_portal_admin(actor)
    user_model = get_user_model()
    user = user_model(
        username=username,
        is_active=True,
        is_staff=False,
        is_superuser=False,
        is_portal_admin=False,
        must_change_password=True,
    )
    validate_password(temporary_password, user)
    user.set_password(temporary_password)
    user.save()
    return user


@transaction.atomic
def set_user_active(*, actor, user, active: bool):
    _require_portal_admin(actor)
    _require_manageable_user(user)
    user.is_active = active
    user.save(update_fields=["is_active"])
    return user


@transaction.atomic
def update_managed_user(*, actor, user, username: str, active: bool):
    _require_portal_admin(actor)
    _require_manageable_user(user)
    user.username = username
    user.is_active = active
    user.save(update_fields=["username", "is_active"])
    return user


@transaction.atomic
def reset_temporary_password(*, actor, user, temporary_password: str):
    _require_portal_admin(actor)
    _require_manageable_user(user)
    validate_password(temporary_password, user)
    user.set_password(temporary_password)
    user.must_change_password = True
    user.save(update_fields=["password", "must_change_password"])
    return user
