from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views import View
from django.views.generic import ListView

from core.mixins import PortalAdminRequiredMixin

from . import throttle
from .forms import (
    LoginForm,
    ManagedUserCreateForm,
    ManagedUserForm,
    RequiredPasswordChangeForm,
    TemporaryPasswordForm,
)
from .models import manageable_users
from .services import (
    audit_logger,
    create_managed_user,
    reset_temporary_password,
    set_user_active,
    update_managed_user,
)

GENERIC_LOGIN_ERROR = "Invalid username or password."


def _log_login_event(event_kind: str, *, username: str, source_ip: str) -> None:
    audit_logger.info(
        "%s username=%r source_ip=%s",
        event_kind,
        username,
        source_ip,
    )


def login_view(request):
    form = LoginForm(request.POST or None)
    # ``next`` arrives as a GET query param on the initial redirect from
    # LoginRequiredMixin (see LOGIN_URL); the template below round-trips it
    # as a hidden POST field so it survives the form submission too.
    next_url = request.POST.get("next") or request.GET.get("next", "")
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        source_ip = throttle.client_address(request)
        key_hash = throttle.throttle_key(username, source_ip)
        now = timezone.now()
        if throttle.is_blocked(key_hash, now):
            _log_login_event(
                "login_throttle_blocked",
                username=username,
                source_ip=source_ip,
            )
            form.add_error(None, GENERIC_LOGIN_ERROR)
        else:
            user = authenticate(
                request,
                username=username,
                password=form.cleaned_data["password"],
            )
            if user is None:
                throttle.record_failure(key_hash, now)
                _log_login_event(
                    "login_failure",
                    username=username,
                    source_ip=source_ip,
                )
                form.add_error(None, GENERIC_LOGIN_ERROR)
            else:
                throttle.reset(key_hash)
                login(request, user)
                _log_login_event(
                    "login_success",
                    username=user.get_username(),
                    source_ip=source_ip,
                )
                redirect_to = request.POST.get("next")
                if not url_has_allowed_host_and_scheme(
                    redirect_to,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    redirect_to = "dashboard"
                return redirect(redirect_to)
    return render(request, "accounts/login.html", {"form": form, "next": next_url})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("accounts:login")


@login_required
def change_required(request):
    form = RequiredPasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        user.must_change_password = False
        user.save(update_fields=["must_change_password"])
        update_session_auth_hash(request, user)
        return redirect("dashboard")
    return render(request, "accounts/force_password_change.html", {"form": form})


def _manageable_user_or_404(pk):
    return get_object_or_404(manageable_users(), pk=pk)


def _keep_own_session(request, user) -> None:
    """Keep an admin logged in after changing their own account."""
    if user.pk == request.user.pk:
        update_session_auth_hash(request, user)


class PortalAdminUserListView(PortalAdminRequiredMixin, ListView):
    context_object_name = "users"
    template_name = "accounts/user_list.html"

    def get_queryset(self):
        return manageable_users().order_by("username")


class _ManagedUserFormView(PortalAdminRequiredMixin, View):
    """GET shows the form; a valid POST runs ``save()`` and returns to the
    account list, an invalid one shows the form again with its errors."""

    template_name = "accounts/user_form.html"

    def get_form(self, data=None):
        raise NotImplementedError

    def save(self, form) -> None:
        raise NotImplementedError

    def get(self, request, **kwargs):
        return render(request, self.template_name, {"form": self.get_form()})

    def post(self, request, **kwargs):
        form = self.get_form(request.POST)
        if form.is_valid():
            self.save(form)
            return redirect("accounts:admin_user_list")
        return render(request, self.template_name, {"form": form})


class PortalAdminUserCreateView(_ManagedUserFormView):
    def get_form(self, data=None):
        return ManagedUserCreateForm(data)

    def save(self, form) -> None:
        create_managed_user(
            actor=self.request.user,
            username=form.cleaned_data["username"],
            temporary_password=form.cleaned_data["temporary_password"],
        )


class PortalAdminUserUpdateView(_ManagedUserFormView):
    def get_form(self, data=None):
        self.user = _manageable_user_or_404(self.kwargs["pk"])
        return ManagedUserForm(data, instance=self.user)

    def save(self, form) -> None:
        update_managed_user(
            actor=self.request.user,
            user=self.user,
            username=form.cleaned_data["username"],
            active=form.cleaned_data["is_active"],
        )


class PortalAdminPasswordResetView(_ManagedUserFormView):
    def get_form(self, data=None):
        self.user = _manageable_user_or_404(self.kwargs["pk"])
        return TemporaryPasswordForm(data, user=self.user)

    def save(self, form) -> None:
        reset_temporary_password(
            actor=self.request.user,
            user=self.user,
            temporary_password=form.cleaned_data["temporary_password"],
        )
        _keep_own_session(self.request, self.user)


class PortalAdminUserActionView(PortalAdminRequiredMixin, View):
    """Deactivate or reactivate an account; the route sets ``active``."""

    active = None

    def post(self, request, pk):
        user = _manageable_user_or_404(pk)
        set_user_active(actor=request.user, user=user, active=self.active)
        _keep_own_session(request, user)
        return redirect("accounts:admin_user_list")
