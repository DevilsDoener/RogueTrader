from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password

from .models import User


class LoginForm(forms.Form):
    username = forms.CharField(max_length=User._meta.get_field("username").max_length)
    password = forms.CharField(strip=False, widget=forms.PasswordInput)


class ManagedUserCreateForm(forms.Form):
    username = forms.CharField(max_length=User._meta.get_field("username").max_length)
    temporary_password = forms.CharField(strip=False, widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("A user with that username already exists.")
        return username

    def clean_temporary_password(self):
        password = self.cleaned_data["temporary_password"]
        candidate = User(username=self.cleaned_data.get("username", ""))
        validate_password(password, candidate)
        return password


class ManagedUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "is_active")


class TemporaryPasswordForm(forms.Form):
    temporary_password = forms.CharField(strip=False, widget=forms.PasswordInput)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_temporary_password(self):
        password = self.cleaned_data["temporary_password"]
        validate_password(password, self.user)
        return password
