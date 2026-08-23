"""Shared view mixins usable by any app.

There used to be two near-identical copies of ``PortalAdminRequiredMixin``
(one in ``accounts/views.py``, one in ``sheets/views.py``). Consolidated
here so a future fix only has to land in one place.
"""
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class PortalAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restricts a view to authenticated portal admins.

    Deliberately does *not* set ``raise_exception = True``: with that flag,
    ``AccessMixin.handle_no_permission`` raises ``PermissionDenied`` (a bare
    403) unconditionally, even for an anonymous visitor -- inconsistent with
    every other authenticated route in the app, which redirects anonymous
    visitors to the login page via ``LOGIN_URL``.

    Leaving ``raise_exception`` at its default (``False``) gives the
    behaviour every other route already has, from ``AccessMixin`` itself:
    an anonymous visitor is redirected to login (``LoginRequiredMixin``
    intercepts before ``test_func`` ever runs), while an authenticated user
    who fails ``test_func`` (i.e. is not a portal admin) still gets a 403,
    because ``handle_no_permission`` raises whenever the user is already
    authenticated.
    """

    def test_func(self):
        return self.request.user.is_portal_admin
