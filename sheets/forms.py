"""Forms for owner-facing character management."""
from __future__ import annotations

from django import forms

from .models import CharacterSheet


class CharacterCreateForm(forms.ModelForm):
    """Creates a new character sheet. ``owner`` is set server-side by the view."""

    class Meta:
        model = CharacterSheet
        fields = ("display_name",)
        labels = {"display_name": "Name"}
