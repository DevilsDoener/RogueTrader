from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    is_portal_admin = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=True)

    @property
    def is_manageable(self) -> bool:
        """Whether portal admins may manage this account. Django staff and
        superusers are never manageable; ``manageable_users()`` is the same
        rule as a queryset."""
        return not (self.is_staff or self.is_superuser)


def manageable_users():
    """The accounts portal admins may manage (see ``User.is_manageable``)."""
    return User.objects.filter(is_staff=False, is_superuser=False)


class LoginThrottle(models.Model):
    key_hash = models.CharField(max_length=64, unique=True)
    window_started_at = models.DateTimeField(db_index=True)
    failure_count = models.PositiveSmallIntegerField(default=0)
    blocked_until = models.DateTimeField(blank=True, null=True)
