"""Forms for owner-facing character management."""
from __future__ import annotations

from django import forms

from .models import CharacterSheet


class CharacterCreateForm(forms.ModelForm):
    """Creates a new character sheet. ``owner`` is set server-side by the view."""

    class Meta:
        model = CharacterSheet
        fields = ("display_name",)

    def clean_display_name(self) -> str:
        display_name = self.cleaned_data["display_name"].strip()
        if not display_name:
            raise forms.ValidationError("Display name is required.")
        return display_name
