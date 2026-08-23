from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        change_required_url = reverse("accounts:change_required")
        allowed_paths = {
            change_required_url,
            reverse("accounts:login"),
            reverse("accounts:logout"),
            reverse("root"),
        }
        if (
            user.is_authenticated
            and user.must_change_password
            and request.path not in allowed_paths
        ):
            return redirect(change_required_url)
        return self.get_response(request)
