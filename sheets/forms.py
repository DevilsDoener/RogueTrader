"""Forms for owner-facing character management."""
from __future__ import annotations

from django import forms

from .models import CharacterSheet


class CharacterCreateForm(forms.ModelForm):
    """Creates a new character sheet. ``owner`` is set server-side by the view."""

    def __init__(self, *args, **kwargs):
        # Labels sit above their field, so no "Name:" colon.
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)

    class Meta:
        model = CharacterSheet
        fields = ("display_name",)
        labels = {"display_name": "Name"}
        error_messages = {"display_name": {"required": "Bitte einen Namen angeben."}}
