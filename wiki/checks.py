"""Startup checks for the wiki content tree.

A missing or unreadable chapter used to be a single ``WARNING`` in the log and
nothing else: the app booted, the wiki was quietly short a chapter (or empty),
and nobody found out until a player looked. These run under ``manage.py
check``, so a broken content mount fails the deploy instead.

Deliberately reported through the checks framework rather than raised during
parsing: ``WikiRepository.load()`` must keep skipping a broken file so one bad
chapter cannot take the whole wiki down at runtime.
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.checks import Error, Warning as CheckWarning

from .manifest import KNOWN_EXCLUDED

MISSING_FILE = "wiki.E001"
UNREADABLE_FILE = "wiki.E002"
MISSING_ROOT = "wiki.E003"
UNLISTED_FILE = "wiki.W001"


def check_wiki_content(app_configs, **kwargs):
    problems = []
    root = Path(settings.WIKI_CONTENT_ROOT)
    allowlist = tuple(settings.WIKI_CONTENT_ALLOWLIST)

    if not root.is_dir():
        return [
            Error(
                f"WIKI_CONTENT_ROOT does not exist: {root}",
                hint=(
                    "Point WIKI_CONTENT_ROOT at the directory holding the chapter "
                    "Markdown files. In Docker this is the read-only mount from "
                    "compose.yaml."
                ),
                id=MISSING_ROOT,
            )
        ]

    for filename in allowlist:
        path = root / filename
        if not path.is_file():
            problems.append(
                Error(
                    f"Allow-listed wiki chapter is missing: {filename}",
                    hint=f"Expected it at {path}.",
                    id=MISSING_FILE,
                )
            )
            continue
        try:
            path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            problems.append(
                Error(
                    f"Allow-listed wiki chapter is unreadable: {filename} "
                    f"({exc.__class__.__name__})",
                    id=UNREADABLE_FILE,
                )
            )

    # The other direction: a chapter added to content/ but never wired up is
    # invisible, and silently so.
    listed = set(allowlist)
    for path in sorted(root.glob("*.md")):
        if path.name in listed or path.name in KNOWN_EXCLUDED:
            continue
        problems.append(
            CheckWarning(
                f"Markdown file under WIKI_CONTENT_ROOT is not served: {path.name}",
                hint=(
                    "Add it to wiki/manifest.py to publish it, or to "
                    "KNOWN_EXCLUDED there if it is deliberately not a chapter."
                ),
                id=UNLISTED_FILE,
            )
        )

    return problems
