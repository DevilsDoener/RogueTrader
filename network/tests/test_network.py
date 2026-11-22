"""Netzwerk: figures, connections, change log, graph JSON and pages.

Everything is shared between signed-in users; what must stay private are the
character sheets themselves -- the network only ever shows a main
character's name and player.
"""
from __future__ import annotations

import json

import pytest

from network.models import NetworkChange, NetworkFigure, NetworkLink
from network.nodes import character_key, figure_key
from tests.html import attr, has_attr, select, select_one, text, texts


@pytest.fixture
def main_character(character_factory, other_user):
    return character_factory(
        owner=other_user,
        display_name="Lucian",
        is_favorite=True,
        values={"c1_rank": "geheim"},
    )


@pytest.fixture
def figure(db):
    return NetworkFigure.objects.create(name="Elias Voss", faction="Navis Nobilite")


def _create(client, **data):
    payload = dict.fromkeys(("faction", "met_at", "description", "connect_to", "relation"), "")
    payload["name"] = "Kara"
    payload.update(data)
    return client.post("/network/figures/new/", payload)


# -- access ------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url",
    [
        "/network/",
        "/network/graph.json",
        "/network/history/",
        "/network/figures/new/",
        "/network/links/new/",
    ],
)
def test_every_page_requires_login(client, url):
    response = client.get(url)
    assert response.status_code == 302
    assert "/account/login/" in response.url


@pytest.mark.django_db
def test_primary_nav_links_the_network(client, owner):
    client.force_login(owner)
    html = client.get("/network/").content.decode()
    current = select(html, "nav#primary-nav a[aria-current=page]")
    assert [attr(link, "href") for link in current] == ["/network/"]


# -- creating figures --------------------------------------------------------


@pytest.mark.django_db
def test_create_figure_without_connection(client, owner):
    client.force_login(owner)
    response = _create(client, name="Kara", faction="Navis Nobilite", met_at="Port Wander")

    figure = NetworkFigure.objects.get(name="Kara")
    assert response.url == f"/network/figures/{figure.pk}/"
    assert (figure.faction, figure.met_at) == ("Navis Nobilite", "Port Wander")
    assert figure.created_by == owner
    assert not NetworkLink.objects.exists()
    change = NetworkChange.objects.get()
    assert (change.actor, change.action) == (owner, "created")
    assert (change.subject, change.label) == ("figure", "Kara")


@pytest.mark.django_db
def test_create_figure_connected_to_a_main_character(client, owner, main_character):
    client.force_login(owner)
    _create(client, connect_to=character_key(main_character), relation="schuldet Geld")

    link = NetworkLink.objects.get()
    assert link.source_figure.name == "Kara"
    assert link.target_character == main_character
    assert link.relation == "schuldet Geld"
    assert NetworkChange.objects.filter(subject="link", action="created").count() == 1


@pytest.mark.django_db
def test_create_figure_connected_to_a_figure(client, owner, figure):
    client.force_login(owner)
    _create(client, connect_to=figure_key(figure), relation="Schwester von")

    link = NetworkLink.objects.get()
    assert (link.source_figure.name, link.target_figure) == ("Kara", figure)
    assert link.relation == "Schwester von"


@pytest.mark.django_db
def test_name_is_required(client, owner):
    client.force_login(owner)
    response = _create(client, name="  ")
    assert response.status_code == 200
    assert not NetworkFigure.objects.exists()


@pytest.mark.django_db
def test_a_connection_needs_a_relation(client, owner, figure):
    client.force_login(owner)
    response = _create(client, connect_to=figure_key(figure), relation="")
    assert response.status_code == 200
    assert "Bitte die Beziehung angeben." in response.content.decode()
    assert NetworkFigure.objects.count() == 1


@pytest.mark.django_db
def test_a_relation_without_connection_is_refused(client, owner):
    client.force_login(owner)
    response = _create(client, relation="Bruder von")
    assert response.status_code == 200
    assert not NetworkFigure.objects.exists()


@pytest.mark.django_db
def test_a_character_that_is_not_a_favorite_cannot_be_picked(client, owner, character_factory):
    plain = character_factory(owner=owner, display_name="Zweitchar")
    client.force_login(owner)
    response = _create(client, connect_to=character_key(plain), relation="kennt")
    assert response.status_code == 200
    assert not NetworkFigure.objects.exists()


@pytest.mark.django_db
def test_unsafe_text_is_refused(client, owner):
    client.force_login(owner)
    response = _create(client, name="Kara‮")
    assert response.status_code == 200
    assert not NetworkFigure.objects.exists()


@pytest.mark.django_db
def test_description_may_span_several_lines(client, owner):
    client.force_login(owner)
    _create(client, description="Zeile eins\r\nZeile zwei")
    assert NetworkFigure.objects.get().description == "Zeile eins\nZeile zwei"


@pytest.mark.django_db
def test_connection_dropdown_lists_none_then_main_characters_then_figures(
    client, owner, main_character, figure
):
    client.force_login(owner)
    html = client.get("/network/figures/new/").content.decode()
    dropdown = select_one(html, "select[name=connect_to]")
    first = select(dropdown, "option")[0]
    assert (attr(first, "value"), text(first), has_attr(first, "selected")) == ("", "keine", True)
    assert [attr(group, "label") for group in select(dropdown, "optgroup")] == [
        "Hauptcharaktere",
        "Nebenfiguren",
    ]
    assert f"Lucian ({main_character.owner.username})" in texts(
        dropdown, "optgroup[label=Hauptcharaktere] option"
    )


@pytest.mark.django_db
def test_create_form_preselects_the_node_from_the_graph(client, owner, figure):
    client.force_login(owner)
    html = client.get(f"/network/figures/new/?zu={figure_key(figure)}").content.decode()
    chosen = select(html, "select[name=connect_to] option[selected]")
    assert [attr(option, "value") for option in chosen] == [figure_key(figure)]


# -- editing and deleting ----------------------------------------------------


@pytest.mark.django_db
def test_edit_logs_each_changed_field(client, owner, figure):
    client.force_login(owner)
    client.post(
        f"/network/figures/{figure.pk}/edit/",
        {
            "name": "Elias Voss",
            "faction": "Navis Nobilite",
            "met_at": "Footfall",
            "description": "",
        },
    )
    figure.refresh_from_db()
    assert figure.met_at == "Footfall"
    change = NetworkChange.objects.get()
    assert change.action == "updated"
    assert change.details == "Getroffen in: – → Footfall"


@pytest.mark.django_db
def test_saving_without_changes_logs_nothing(client, owner, figure):
    client.force_login(owner)
    client.post(
        f"/network/figures/{figure.pk}/edit/",
        {"name": "Elias Voss", "faction": "Navis Nobilite", "met_at": "", "description": ""},
    )
    assert not NetworkChange.objects.exists()


@pytest.mark.django_db
def test_deleting_a_figure_removes_its_connections_and_logs_them(
    client, owner, figure, main_character
):
    NetworkLink.objects.create(
        source_figure=figure, target_character=main_character, relation="dient"
    )
    client.force_login(owner)

    assert client.get(f"/network/figures/{figure.pk}/delete/").status_code == 200
    response = client.post(f"/network/figures/{figure.pk}/delete/")

    assert response.url == "/network/"
    assert not NetworkFigure.objects.exists()
    assert not NetworkLink.objects.exists()
    assert set(NetworkChange.objects.values_list("subject", "action")) == {
        ("figure", "deleted"),
        ("link", "deleted"),
    }


@pytest.mark.django_db
def test_any_signed_in_user_may_edit_anothers_figure(client, other_user, figure):
    figure.created_by = None
    figure.save()
    client.force_login(other_user)
    client.post(
        f"/network/figures/{figure.pk}/edit/",
        {"name": "Elias", "faction": "", "met_at": "", "description": ""},
    )
    figure.refresh_from_db()
    assert figure.name == "Elias"


# -- connections -------------------------------------------------------------


@pytest.mark.django_db
def test_link_between_main_character_and_figure(client, owner, figure, main_character):
    client.force_login(owner)
    response = client.post(
        "/network/links/new/",
        {
            "source": character_key(main_character),
            "relation": "Mentor von",
            "target": figure_key(figure),
        },
    )
    assert response.url == "/network/"
    link = NetworkLink.objects.get()
    assert (link.source_character, link.target_figure) == (main_character, figure)


@pytest.mark.django_db
def test_link_from_a_figure_returns_to_that_figure(client, owner, figure):
    other = NetworkFigure.objects.create(name="Kara")
    client.force_login(owner)
    response = client.post(
        "/network/links/new/",
        {"source": figure_key(figure), "relation": "Bruder von", "target": figure_key(other)},
    )
    assert response.url == f"/network/figures/{figure.pk}/"


@pytest.mark.django_db
def test_a_node_cannot_link_to_itself(client, owner, figure):
    client.force_login(owner)
    response = client.post(
        "/network/links/new/",
        {"source": figure_key(figure), "relation": "kennt", "target": figure_key(figure)},
    )
    assert response.status_code == 200
    assert not NetworkLink.objects.exists()


@pytest.mark.django_db
def test_removing_a_connection_returns_to_the_figure(client, owner, figure):
    other = NetworkFigure.objects.create(name="Kara")
    link = NetworkLink.objects.create(source_figure=figure, target_figure=other, relation="kennt")
    client.force_login(owner)

    response = client.post(f"/network/links/{link.pk}/delete/", {"figure": str(figure.pk)})

    assert response.url == f"/network/figures/{figure.pk}/"
    assert not NetworkLink.objects.exists()
    assert NetworkChange.objects.get().label == "Elias Voss → kennt → Kara"


@pytest.mark.django_db
def test_figure_page_lists_both_directions(client, owner, figure, main_character):
    kara = NetworkFigure.objects.create(name="Kara")
    NetworkLink.objects.create(
        source_figure=figure, target_character=main_character, relation="dient"
    )
    NetworkLink.objects.create(source_figure=kara, target_figure=figure, relation="Schwester von")
    client.force_login(owner)

    html = client.get(f"/network/figures/{figure.pk}/").content.decode()

    assert "dient" in html and "Lucian" in html
    assert "Schwester von" in html and "Kara" in html


# -- graph data and privacy --------------------------------------------------


@pytest.mark.django_db
def test_graph_json_shows_every_main_character_but_never_sheet_values(
    client, owner, main_character, figure
):
    NetworkLink.objects.create(
        source_figure=figure, target_character=main_character, relation="dient"
    )
    client.force_login(owner)

    data = client.get("/network/graph.json").json()

    nodes = {node["id"]: node for node in data["nodes"]}
    lucian = nodes[character_key(main_character)]
    assert lucian["kind"] == "main"
    assert lucian["player"] == main_character.owner.username
    assert lucian["url"] == ""  # someone else's sheet: no link
    assert "geheim" not in json.dumps(data)
    assert nodes[figure_key(figure)]["faction"] == "Navis Nobilite"
    assert data["edges"] == [
        {
            "id": str(NetworkLink.objects.get().pk),
            "from": figure_key(figure),
            "to": character_key(main_character),
            "label": "dient",
        }
    ]


@pytest.mark.django_db
def test_graph_json_links_your_own_main_character_to_its_sheet(client, owner, character_factory):
    mine = character_factory(owner=owner, display_name="Ich", is_favorite=True)
    client.force_login(owner)
    nodes = client.get("/network/graph.json").json()["nodes"]
    assert nodes[0]["url"] == f"/characters/{mine.pk}/"


@pytest.mark.django_db
def test_a_linked_former_favorite_stays_as_a_plain_character(client, owner, main_character, figure):
    NetworkLink.objects.create(
        source_figure=figure, target_character=main_character, relation="dient"
    )
    main_character.is_favorite = False
    main_character.save()
    client.force_login(owner)

    nodes = {n["id"]: n for n in client.get("/network/graph.json").json()["nodes"]}

    assert nodes[character_key(main_character)]["kind"] == "character"


@pytest.mark.django_db
def test_graph_page_loads_only_static_scripts(client, owner):
    client.force_login(owner)
    html = client.get("/network/").content.decode()
    assert "/static/vendor/vis-network/vis-network.min.js" in html
    assert "/static/js/network-graph.js" in html
    assert 'data-graph-url="/network/graph.json"' in html


@pytest.mark.django_db
def test_names_are_escaped_on_the_pages(client, owner):
    NetworkFigure.objects.create(name="<script>alert(1)</script>")
    client.force_login(owner)
    html = client.get("/network/").content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


@pytest.mark.django_db
def test_history_lists_changes_newest_first(client, owner):
    client.force_login(owner)
    _create(client, name="Erste")
    _create(client, name="Zweite")
    html = client.get("/network/history/").content.decode()
    assert html.index("Zweite") < html.index("Erste")
    assert "Figur angelegt" in html
