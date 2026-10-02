"""The one username rule for every way an account can get a name.

New names are restricted to ASCII ``[A-Za-z0-9@.+_-]`` (Django's username
characters without the Unicode letters): that rules out zero-width, bidi and
control characters as well as look-alike letters from other scripts
(Cyrillic ``а`` for Latin ``a``) without a homoglyph table. Names are compared
case-insensitively, so ``Alice`` is taken once ``alice`` exists.

A name an account already has stays valid as it is, even if it predates this
rule -- only a *changed* name has to pass.
"""
import re

from django.core.exceptions import ValidationError

from .models import User

USERNAME_MAX_LENGTH = User._meta.get_field("username").max_length
USERNAME_HELP_TEXT = (
    f"Bis zu {USERNAME_MAX_LENGTH} Zeichen: Buchstaben (A-Z), Ziffern und @ . + - _"
)

_ALLOWED_USERNAME = re.compile(r"[A-Za-z0-9@.+_-]+")


def clean_username(value: str, *, existing=None) -> str:
    """Return the trimmed name or raise ``ValidationError`` (German, "du").

    ``existing`` is the account being edited: its own, unchanged name is
    returned untouched and is never reported as a duplicate of itself.
    """
    username = (value or "").strip()
    if not username:
        raise ValidationError("Dieses Feld ist zwingend erforderlich.", code="required")
    if existing is not None and username == existing.username:
        return username
    if len(username) > USERNAME_MAX_LENGTH:
        raise ValidationError(
            f"Der Benutzername darf höchstens {USERNAME_MAX_LENGTH} Zeichen lang sein.",
            code="max_length",
        )
    if not _ALLOWED_USERNAME.fullmatch(username):
        raise ValidationError(
            "Der Benutzername darf nur Buchstaben (A-Z), Ziffern und @ . + - _ enthalten. "
            "Leerzeichen, Umlaute und andere Sonderzeichen gehen hier nicht.",
            code="invalid",
        )
    clashes = User.objects.filter(username__iexact=username)
    if existing is not None:
        clashes = clashes.exclude(pk=existing.pk)
    if clashes.exists():
        raise ValidationError("Dieser Benutzername ist bereits vergeben.", code="unique")
    return username
