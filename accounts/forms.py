from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.password_validation import validate_password

from . import usernames
from .models import User

LOGIN_USERNAME_MAX_LENGTH = usernames.USERNAME_MAX_LENGTH
LOGIN_PASSWORD_MAX_LENGTH = 4096


class LoginForm(forms.Form):
    """Over-long input is not a field error: that would be a second, more
    specific message than the generic one every other refusal gets. It sets
    ``credentials_too_long`` instead and the view counts it as a failed login
    without hashing anything."""

    username = forms.CharField(
        label="Benutzername",
        required=False,
        widget=forms.TextInput(attrs={"maxlength": LOGIN_USERNAME_MAX_LENGTH}),
    )
    password = forms.CharField(
        label="Passwort",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"maxlength": LOGIN_PASSWORD_MAX_LENGTH}),
    )

    credentials_too_long = False

    def clean(self):
        cleaned = super().clean()
        self.credentials_too_long = (
            len(cleaned.get("username", "")) > LOGIN_USERNAME_MAX_LENGTH
            or len(cleaned.get("password", "")) > LOGIN_PASSWORD_MAX_LENGTH
        )
        return cleaned


class RequiredPasswordChangeForm(PasswordChangeForm):
    # Django's German catalogue addresses people impersonally or formally
    # ("Bitte ... eingeben", "Ihr ..."); the portal speaks "du" throughout.
    error_messages = {
        **PasswordChangeForm.error_messages,
        "password_mismatch": "Die beiden neuen Passwörter stimmen nicht überein.",
        "password_incorrect": "Dein aktuelles Passwort stimmt nicht. Gib es bitte noch einmal ein.",
    }

    def __init__(self, *args, locked=False, **kwargs):
        # ``locked``: too many wrong current passwords lately. The form then
        # refuses with the ordinary "wrong password" message and hashes nothing.
        self.locked = locked
        super().__init__(*args, **kwargs)
        self.fields["new_password2"].help_text = (
            "Gib dasselbe neue Passwort zur Bestätigung noch einmal ein."
        )

    def clean_old_password(self):
        if self.locked:
            raise forms.ValidationError(
                self.error_messages["password_incorrect"], code="password_incorrect"
            )
        return super().clean_old_password()

    def clean_new_password1(self):
        password = self.cleaned_data["new_password1"]
        if self.locked:
            return password
        if self.user.check_password(password):
            raise forms.ValidationError(
                "Das neue Passwort muss sich vom aktuellen Passwort unterscheiden."
            )
        return password


class _UsernameFormMixin:
    """Create and edit validate a name with the same rule (``usernames``)."""

    existing_user = None

    def clean_username(self):
        return usernames.clean_username(
            self.cleaned_data["username"], existing=self.existing_user
        )


class ManagedUserCreateForm(_UsernameFormMixin, forms.Form):
    username = forms.CharField(
        label="Benutzername",
        help_text=usernames.USERNAME_HELP_TEXT,
        # Over-long names get the validator's German message, not Django's.
        widget=forms.TextInput(attrs={"maxlength": usernames.USERNAME_MAX_LENGTH}),
    )
    temporary_password = forms.CharField(
        label="Temporäres Passwort", strip=False, widget=forms.PasswordInput
    )

    def clean_temporary_password(self):
        password = self.cleaned_data["temporary_password"]
        candidate = User(username=self.cleaned_data.get("username", ""))
        validate_password(password, candidate)
        return password


class ManagedUserForm(_UsernameFormMixin, forms.Form):
    """Edit an account. A plain form (not a ``ModelForm``) on purpose: the
    instance keeps its old name until the service saves it, so the audit log
    can record old -> new."""

    username = forms.CharField(
        label="Benutzername",
        help_text=usernames.USERNAME_HELP_TEXT,
        widget=forms.TextInput(attrs={"maxlength": usernames.USERNAME_MAX_LENGTH}),
    )
    is_active = forms.BooleanField(label="Aktiv", required=False)

    def __init__(self, *args, instance, **kwargs):
        kwargs.setdefault("initial", {"username": instance.username, "is_active": instance.is_active})
        super().__init__(*args, **kwargs)
        self.existing_user = instance


class TemporaryPasswordForm(forms.Form):
    temporary_password = forms.CharField(
        label="Temporäres Passwort", strip=False, widget=forms.PasswordInput
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_temporary_password(self):
        password = self.cleaned_data["temporary_password"]
        validate_password(password, self.user)
        return password
