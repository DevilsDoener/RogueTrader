"""Every write to the network, each with its :class:`NetworkChange` entry.

Views never touch the models directly: create/update/delete go through these
functions so the change log can't be skipped. Every signed-in user may write
(the network is shared, like the ship); the views enforce sign-in.
"""
from __future__ import annotations

from django.db import transaction

from .models import NetworkChange, NetworkFigure, NetworkLink
from .nodes import NodeRef, character_label

#: Figure fields in log order, with their German labels.
FIGURE_FIELDS = (
    ("name", "Name"),
    ("faction", "Fraktion"),
    ("met_at", "Getroffen in"),
    ("description", "Beschreibung"),
)


def _log(actor, action, subject, label, details="") -> None:
    NetworkChange.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        subject=subject,
        label=label[:400],
        details=details,
    )


def _figure_details(figure: NetworkFigure) -> str:
    return "\n".join(
        f"{label}: {getattr(figure, name)}"
        for name, label in FIGURE_FIELDS
        if getattr(figure, name)
    )


def node_label(figure: NetworkFigure | None, character) -> str:
    return figure.name if figure is not None else character_label(character)


def link_label(link: NetworkLink) -> str:
    source = node_label(link.source_figure, link.source_character)
    target = node_label(link.target_figure, link.target_character)
    return f"{source} → {link.relation} → {target}"


def _new_link(actor, source: NodeRef, target: NodeRef, relation: str) -> NetworkLink:
    link = NetworkLink.objects.create(
        source_figure=source.figure,
        source_character=source.character,
        target_figure=target.figure,
        target_character=target.character,
        relation=relation,
        created_by=actor,
    )
    _log(actor, NetworkChange.Action.CREATED, NetworkChange.Subject.LINK, link_label(link))
    return link


@transaction.atomic
def create_figure(
    *, actor, data: dict, connect_to: NodeRef | None = None, relation: str = ""
) -> NetworkFigure:
    """A new figure, optionally connected straight away (figure -> relation -> node)."""
    figure = NetworkFigure.objects.create(
        created_by=actor, **{name: data.get(name, "") for name, _ in FIGURE_FIELDS}
    )
    _log(
        actor,
        NetworkChange.Action.CREATED,
        NetworkChange.Subject.FIGURE,
        figure.name,
        _figure_details(figure),
    )
    if connect_to is not None:
        _new_link(actor, NodeRef(figure=figure), connect_to, relation)
    return figure


@transaction.atomic
def update_figure(*, actor, figure: NetworkFigure, data: dict) -> NetworkFigure:
    """Save changed fields; logs "field: old → new" per change, nothing if unchanged."""
    figure = NetworkFigure.objects.select_for_update().get(pk=figure.pk)
    changes = []
    for name, label in FIGURE_FIELDS:
        new = data.get(name, "")
        old = getattr(figure, name)
        if new != old:
            changes.append(f"{label}: {old or '–'} → {new or '–'}")
            setattr(figure, name, new)
    if changes:
        figure.save()
        _log(
            actor,
            NetworkChange.Action.UPDATED,
            NetworkChange.Subject.FIGURE,
            figure.name,
            "\n".join(changes),
        )
    return figure


@transaction.atomic
def delete_figure(*, actor, figure: NetworkFigure) -> None:
    """Delete a figure; its connections go with it and are logged too."""
    links = NetworkLink.objects.filter(source_figure=figure) | NetworkLink.objects.filter(
        target_figure=figure
    )
    for link in links.select_related(
        "source_figure", "target_figure", "source_character__owner", "target_character__owner"
    ):
        _log(actor, NetworkChange.Action.DELETED, NetworkChange.Subject.LINK, link_label(link))
    _log(
        actor,
        NetworkChange.Action.DELETED,
        NetworkChange.Subject.FIGURE,
        figure.name,
        _figure_details(figure),
    )
    figure.delete()


@transaction.atomic
def create_link(*, actor, source: NodeRef, target: NodeRef, relation: str) -> NetworkLink:
    return _new_link(actor, source, target, relation)


@transaction.atomic
def delete_link(*, actor, link: NetworkLink) -> None:
    _log(actor, NetworkChange.Action.DELETED, NetworkChange.Subject.LINK, link_label(link))
    link.delete()
