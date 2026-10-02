from django.shortcuts import redirect
from django.urls import reverse

from . import throttle
from .services import audit_logger


class ForcePasswordChangeMiddleware:
    """Send a user who still has a temporary password to the change form.

    Only the change form itself, login, logout and the root redirect stay
    reachable until the password is changed.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and user.must_change_password:
            change_required_url = reverse("accounts:change_required")
            allowed_paths = {
                change_required_url,
                reverse("accounts:login"),
                reverse("accounts:logout"),
                reverse("root"),
            }
            if request.path not in allowed_paths:
                return redirect(change_required_url)
        return self.get_response(request)


class AdminAccessAuditMiddleware:
    """Leave an audit record when someone is refused on a ``/portal-admin/`` route.

    The refusal itself comes from ``PortalAdminRequiredMixin`` (HTTP 403); this
    only notes who tried, so a player probing the admin pages shows up in the log.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code == 403 and request.path.startswith("/portal-admin/"):
            audit_logger.warning(
                "admin_access_denied username=%r method=%s path=%r source_ip=%s",
                request.user.get_username()[:150],
                request.method,
                request.path[:200],
                throttle.client_address(request),
            )
        return response
