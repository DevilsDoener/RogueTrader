"""The Netzwerk graph in a real browser, under the portal's CSP.

vis-network is vendored as its *peer* build precisely because the standalone
build injects a <style> element, which ``style-src 'self'`` refuses. This
pins that the page draws without a single policy violation, that the legend
and side panel are filled from graph.json, and that a node click shows it.
"""
from __future__ import annotations

import pytest

from network.models import NetworkFigure, NetworkLink

from .conftest import login_via_browser
from .test_csp import _Watch

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def small_network(owner, character_factory):
    lucian = character_factory(owner=owner, display_name="Lucian", is_favorite=True)
    kara = NetworkFigure.objects.create(
        name="Kara Voss", faction="Navis Nobilite", met_at="Port Wander", description="Navigatorin"
    )
    NetworkLink.objects.create(
        source_figure=kara, target_character=lucian, relation="schuldet Geld"
    )
    return {"lucian": lucian, "kara": kara}


def test_graph_draws_without_csp_violations(page, live_server, owner, small_network):
    watch = _Watch(page)
    login_via_browser(page, live_server, username=owner.username)

    page.goto(f"{live_server.url}/network/")
    page.wait_for_selector("#network-canvas canvas")
    page.wait_for_selector("#network-legend li")

    watch.assert_clean("network graph")
    legend = page.inner_text("#network-legend")
    assert "Hauptcharakter" in legend
    assert "Navis Nobilite" in legend


def test_clicking_a_node_fills_the_side_panel(page, live_server, owner, small_network):
    login_via_browser(page, live_server, username=owner.username)
    page.goto(f"{live_server.url}/network/")
    page.wait_for_selector("#network-canvas canvas")
    page.wait_for_function("() => window.__networkGraph !== undefined")

    # Hit-testing a moving physics layout with the mouse is flaky; emit the
    # click vis-network would emit for that node instead.
    kara_id = f"f:{small_network['kara'].pk}"
    page.evaluate(
        "(id) => { window.__networkGraph.emit('click', {nodes: [id], edges: []}); }", kara_id
    )

    page.wait_for_selector(".network-panel-title")
    panel = page.inner_text("#network-panel")
    assert "Kara Voss" in panel
    assert "Port Wander" in panel
    assert "schuldet Geld" in panel
    assert "Figur öffnen" in panel
