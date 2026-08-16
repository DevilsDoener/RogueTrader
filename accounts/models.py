from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    is_portal_admin = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=True)

    def can_view_all_characters(self) -> bool:
        return self.is_authenticated and self.is_portal_admin


class LoginThrottle(models.Model):
    key_hash = models.CharField(max_length=64, unique=True)
    window_started_at = models.DateTimeField()
    failure_count = models.PositiveSmallIntegerField(default=0)
    blocked_until = models.DateTimeField(blank=True, null=True)
