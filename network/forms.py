"""Forms for figures and connections.

Text is stripped and checked with the same rules as sheet fields
(:mod:`sheets.textsafety`); only the description may span several lines.
"""
from __future__ import annotations

from django import forms

from sheets.textsafety import unsafe_text_problem

from .models import (
    DESCRIPTION_MAX_LENGTH,
    FACTION_MAX_LENGTH,
    MET_AT_MAX_LENGTH,
    NAME_MAX_LENGTH,
    RELATION_MAX_LENGTH,
)
from .nodes import NO_CONNECTION, node_choices, resolve

UNSAFE_TEXT = "Der Text enthält ungültige Zeichen."
RELATION_REQUIRED = "Bitte die Beziehung angeben."
RELATION_WITHOUT_CONNECTION = "Wähle eine Verbindung oder lass die Beziehung leer."
UNKNOWN_NODE = "Diese Auswahl gibt es nicht (mehr)."
SAME_NODE = "Eine Figur kann nicht mit sich selbst verbunden sein."


def _safe(value: str, *, multiline: bool = False) -> str:
    checked = value.replace("\r\n", "\n").replace("\n", "") if multiline else value
    if unsafe_text_problem(checked):
        raise forms.ValidationError(UNSAFE_TEXT)
    return value.replace("\r\n", "\n") if multiline else value


class _NoSuffixForm(forms.Form):
    """Labels sit above their fields, so no "Name:" colon."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)


class FigureForm(_NoSuffixForm):
    name = forms.CharField(label="Name", max_length=NAME_MAX_LENGTH)
    faction = forms.CharField(
        label="Fraktion",
        max_length=FACTION_MAX_LENGTH,
        required=False,
        widget=forms.TextInput(attrs={"list": "network-factions", "autocomplete": "off"}),
    )
    met_at = forms.CharField(label="Getroffen in", max_length=MET_AT_MAX_LENGTH, required=False)
    description = forms.CharField(
        label="Beschreibung",
        max_length=DESCRIPTION_MAX_LENGTH,
        required=False,
        widget=forms.Textarea(attrs={"rows": 5}),
    )

    def clean_name(self):
        return _safe(self.cleaned_data["name"])

    def clean_faction(self):
        return _safe(self.cleaned_data["faction"])

    def clean_met_at(self):
        return _safe(self.cleaned_data["met_at"])

    def clean_description(self):
        return _safe(self.cleaned_data["description"], multiline=True)


class FigureCreateForm(FigureForm):
    """A new figure plus its optional first connection ("keine" is allowed)."""

    connect_to = forms.ChoiceField(label="Verbindung zu", required=False)
    relation = forms.CharField(
        label="Beziehung",
        max_length=RELATION_MAX_LENGTH,
        required=False,
        help_text="Liest sich von der neuen Figur aus, z. B. „Schwester von“.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["connect_to"].choices = node_choices(include_none=True)

    def clean_relation(self):
        return _safe(self.cleaned_data["relation"])

    def clean(self):
        cleaned = super().clean()
        key = cleaned.get("connect_to", NO_CONNECTION)
        relation = cleaned.get("relation", "")
        cleaned["connect_node"] = None
        if key:
            node = resolve(key)
            if node is None:
                self.add_error("connect_to", UNKNOWN_NODE)
            elif not relation and "relation" not in self.errors:
                self.add_error("relation", RELATION_REQUIRED)
            cleaned["connect_node"] = node
        elif relation:
            self.add_error("relation", RELATION_WITHOUT_CONNECTION)
        return cleaned


class LinkForm(_NoSuffixForm):
    """One connection: source -> relation -> target, both from the node list."""

    source = forms.ChoiceField(label="Von")
    relation = forms.CharField(label="Beziehung", max_length=RELATION_MAX_LENGTH)
    target = forms.ChoiceField(label="Zu")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = node_choices(include_none=False)
        self.fields["source"].choices = choices
        self.fields["target"].choices = choices

    def clean_relation(self):
        return _safe(self.cleaned_data["relation"])

    def clean(self):
        cleaned = super().clean()
        source_key, target_key = cleaned.get("source"), cleaned.get("target")
        for name, key in (("source", source_key), ("target", target_key)):
            if key:
                node = resolve(key)
                if node is None:
                    self.add_error(name, UNKNOWN_NODE)
                cleaned[f"{name}_node"] = node
        if source_key and source_key == target_key:
            self.add_error("target", SAME_NODE)
        return cleaned
