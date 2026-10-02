from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views import View
from django.views.generic import ListView

from core.mixins import PortalAdminRequiredMixin

from . import devices, throttle
from .forms import (
    LoginForm,
    ManagedUserCreateForm,
    ManagedUserForm,
    RequiredPasswordChangeForm,
    TemporaryPasswordForm,
)
from .models import manageable_users
from .services import (
    AccountRuleViolation,
    audit_logger,
    create_managed_user,
    reset_temporary_password,
    set_user_active,
    update_managed_user,
)

GENERIC_LOGIN_ERROR = "Benutzername oder Passwort ungültig."
_LOGGED_USERNAME_LENGTH = 150


def _log_login_event(event_kind: str, *, username: str, source_ip: str) -> None:
    audit_logger.info(
        "%s username=%r source_ip=%s",
        event_kind,
        username[:_LOGGED_USERNAME_LENGTH],  # a hostile 2 MB "username" must not flood the log
        source_ip,
    )


def _safe_next(request) -> str:
    """The POSTed ``next`` if it stays on this host (and scheme), else the dashboard."""
    redirect_to = request.POST.get("next")
    if url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect_to
    return "dashboard"


def _log_blocked_once(keys, *, username: str, source_ip: str) -> None:
    """Log a blocked attempt, but only the first one per blocking counter and window.

    Otherwise one client hammering a blocked login could fill the rotating audit
    files and push the interesting records out. The memory is per worker process,
    so a restart or another worker may log once more -- that is fine.
    """
    fresh = [
        cache.add(f"login-blocked-logged:{key}", 1, int(throttle.THROTTLE_WINDOW.total_seconds()))
        for key in keys
    ]
    if any(fresh):
        _log_login_event("login_throttle_blocked", username=username, source_ip=source_ip)


def _authenticate_throttled(request, form):
    """The signed-in user, or ``None`` after adding the generic error to ``form``.

    Order matters: the counters are read before any password is hashed, so a
    blocked attempt costs no Argon2 run; a failure is recorded before the
    refusal; a success resets only the (username, address) and device counters.
    A browser holding a device cookie for the username is judged by its own
    device counter instead of the shared per-username and per-address ones.
    """
    username = form.cleaned_data["username"]
    source = throttle.client_source(request)
    counters = throttle.login_counters(
        username,
        source.bucket,
        distinguishes=source.distinguishes,
        device_id=devices.device_id_for(request, username),
    )
    now = timezone.now()

    blocking = throttle.blocking_keys(counters, now)
    if blocking:
        _log_blocked_once(blocking, username=username, source_ip=source.address)
        form.add_error(None, GENERIC_LOGIN_ERROR)
        return None

    user = None
    if not form.credentials_too_long:
        user = authenticate(request, username=username, password=form.cleaned_data["password"])
    if user is None:
        throttle.record_failure(counters, now)
        _log_login_event("login_failure", username=username, source_ip=source.address)
        form.add_error(None, GENERIC_LOGIN_ERROR)
        return None

    throttle.reset(counters.pair)
    if counters.device is not None:
        throttle.reset(counters.device)
    login(request, user)
    _log_login_event("login_success", username=user.get_username(), source_ip=source.address)
    return user


def login_view(request):
    form = LoginForm(request.POST or None)
    # ``next`` arrives as a GET query param on the initial redirect from
    # LoginRequiredMixin (see LOGIN_URL); the template below round-trips it
    # as a hidden POST field so it survives the form submission too.
    next_url = request.POST.get("next") or request.GET.get("next", "")
    if request.method == "POST" and form.is_valid():
        user = _authenticate_throttled(request, form)
        if user is not None:
            response = redirect(_safe_next(request))
            devices.remember(response, request, user.get_username())
            return response
    return render(request, "accounts/login.html", {"form": form, "next": next_url})


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        audit_logger.info(
            "logout username=%r source_ip=%s",
            request.user.get_username()[:_LOGGED_USERNAME_LENGTH],
            throttle.client_address(request),
        )
    logout(request)
    return redirect("accounts:login")


@login_required
def change_required(request):
    counter = throttle.password_change_counter(request.user)
    now = timezone.now()
    locked = request.method == "POST" and throttle.is_blocked([counter], now)
    form = RequiredPasswordChangeForm(request.user, request.POST or None, locked=locked)
    if request.method == "POST":
        if form.is_valid():
            user = form.save()
            user.must_change_password = False
            user.save(update_fields=["must_change_password"])
            update_session_auth_hash(request, user)
            throttle.reset(counter)
            audit_logger.info(
                "password_changed username=%r source_ip=%s",
                user.get_username()[:_LOGGED_USERNAME_LENGTH],
                throttle.client_address(request),
            )
            return redirect("dashboard")
        if "old_password" in form.errors and not locked:
            throttle.record_failure([counter], now)
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
            try:
                self.save(form)
            except AccountRuleViolation as violation:
                form.add_error(None, str(violation))
            else:
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
        try:
            set_user_active(actor=request.user, user=user, active=self.active)
        except AccountRuleViolation as violation:
            messages.error(request, str(violation))
        else:
            _keep_own_session(request, user)
        return redirect("accounts:admin_user_list")
