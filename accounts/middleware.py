from django.shortcuts import redirect
from django.urls import reverse


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
