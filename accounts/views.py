import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views import View
from django.views.generic import ListView

from core.mixins import PortalAdminRequiredMixin

from .forms import LoginForm, ManagedUserCreateForm, ManagedUserForm, TemporaryPasswordForm
from .models import LoginThrottle, User
from .services import (
    create_managed_user,
    reset_temporary_password,
    set_user_active,
    update_managed_user,
)

GENERIC_LOGIN_ERROR = "Invalid username or password."
THROTTLE_WINDOW = timedelta(minutes=15)
THROTTLE_LIMIT = 5


def _throttle_key(request, username: str) -> str:
    normalized_identifier = username.strip().casefold()
    source_ip = request.META.get("REMOTE_ADDR", "")
    message = f"{normalized_identifier}\x00{source_ip}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def _is_blocked(key_hash: str, now) -> bool:
    throttle = LoginThrottle.objects.filter(key_hash=key_hash).first()
    if throttle is None:
        return False
    if throttle.blocked_until and throttle.blocked_until > now:
        return True
    if now - throttle.window_started_at >= THROTTLE_WINDOW:
        throttle.failure_count = 0
        throttle.window_started_at = now
        throttle.blocked_until = None
        throttle.save(update_fields=["failure_count", "window_started_at", "blocked_until"])
    return False


@transaction.atomic
def _record_login_failure(key_hash: str, now) -> None:
    throttle = LoginThrottle.objects.select_for_update().filter(key_hash=key_hash).first()
    if throttle is None:
        try:
            with transaction.atomic():
                throttle = LoginThrottle.objects.create(
                    key_hash=key_hash,
                    window_started_at=now,
                )
        except IntegrityError:
            throttle = LoginThrottle.objects.select_for_update().get(key_hash=key_hash)
    if now - throttle.window_started_at >= THROTTLE_WINDOW:
        throttle.window_started_at = now
        throttle.failure_count = 0
        throttle.blocked_until = None
    throttle.failure_count += 1
    if throttle.failure_count >= THROTTLE_LIMIT:
        throttle.blocked_until = now + THROTTLE_WINDOW
    throttle.save()


def login_view(request):
    form = LoginForm(request.POST or None)
    # ``next`` arrives as a GET query param on the initial redirect from
    # LoginRequiredMixin (see LOGIN_URL); the template below round-trips it
    # as a hidden POST field so it survives the form submission too.
    next_url = request.POST.get("next") or request.GET.get("next", "")
    if request.method == "POST" and form.is_valid():
        key_hash = _throttle_key(request, form.cleaned_data["username"])
        now = timezone.now()
        if _is_blocked(key_hash, now):
            form.add_error(None, GENERIC_LOGIN_ERROR)
        else:
            user = authenticate(
                request,
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"],
            )
            if user is None:
                _record_login_failure(key_hash, now)
                form.add_error(None, GENERIC_LOGIN_ERROR)
            else:
                LoginThrottle.objects.filter(key_hash=key_hash).delete()
                login(request, user)
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
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        user.must_change_password = False
        user.save(update_fields=["must_change_password"])
        update_session_auth_hash(request, user)
        return redirect("dashboard")
    return render(request, "accounts/force_password_change.html", {"form": form})


class PortalAdminUserListView(PortalAdminRequiredMixin, ListView):
    model = User
    context_object_name = "users"
    template_name = "accounts/user_list.html"
    ordering = "username"

    def get_queryset(self):
        return User.objects.filter(is_staff=False, is_superuser=False).order_by(self.ordering)


class PortalAdminUserCreateView(PortalAdminRequiredMixin, View):
    template_name = "accounts/user_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ManagedUserCreateForm()})

    def post(self, request):
        form = ManagedUserCreateForm(request.POST)
        if form.is_valid():
            create_managed_user(
                actor=request.user,
                username=form.cleaned_data["username"],
                temporary_password=form.cleaned_data["temporary_password"],
            )
            return redirect("accounts:admin_user_list")
        return render(request, self.template_name, {"form": form})


class PortalAdminUserUpdateView(PortalAdminRequiredMixin, View):
    template_name = "accounts/user_form.html"

    def get(self, request, pk):
        user = get_object_or_404(User.objects.filter(is_staff=False, is_superuser=False), pk=pk)
        return render(request, self.template_name, {"form": ManagedUserForm(instance=user)})

    def post(self, request, pk):
        user = get_object_or_404(User.objects.filter(is_staff=False, is_superuser=False), pk=pk)
        form = ManagedUserForm(request.POST, instance=user)
        if form.is_valid():
            update_managed_user(
                actor=request.user,
                user=user,
                username=form.cleaned_data["username"],
                active=form.cleaned_data["is_active"],
            )
            return redirect("accounts:admin_user_list")
        return render(request, self.template_name, {"form": form})


class PortalAdminUserActionView(PortalAdminRequiredMixin, View):
    action = None

    def post(self, request, pk):
        user = get_object_or_404(User.objects.filter(is_staff=False, is_superuser=False), pk=pk)
        if self.action == "deactivate":
            set_user_active(actor=request.user, user=user, active=False)
            if user.pk == request.user.pk:
                update_session_auth_hash(request, user)
        elif self.action == "reactivate":
            set_user_active(actor=request.user, user=user, active=True)
            if user.pk == request.user.pk:
                update_session_auth_hash(request, user)
        else:
            raise PermissionDenied
        return redirect("accounts:admin_user_list")


class PortalAdminPasswordResetView(PortalAdminRequiredMixin, View):
    template_name = "accounts/user_form.html"

    def get(self, request, pk):
        user = get_object_or_404(User.objects.filter(is_staff=False, is_superuser=False), pk=pk)
        return render(request, self.template_name, {"form": TemporaryPasswordForm(user=user)})

    def post(self, request, pk):
        user = get_object_or_404(User.objects.filter(is_staff=False, is_superuser=False), pk=pk)
        form = TemporaryPasswordForm(request.POST, user=user)
        if form.is_valid():
            reset_temporary_password(
                actor=request.user,
                user=user,
                temporary_password=form.cleaned_data["temporary_password"],
            )
            if user.pk == request.user.pk:
                update_session_auth_hash(request, user)
            return redirect("accounts:admin_user_list")
        return render(request, self.template_name, {"form": form})
