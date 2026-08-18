"""Small template helpers for rendering sheet viewer overlays."""
from __future__ import annotations

from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    """Look up ``key`` in ``mapping`` (a dict) -- Django templates can't do
    variable-keyed lookups on their own."""
    if not mapping:
        return None
    return mapping.get(key)
