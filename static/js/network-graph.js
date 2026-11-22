/*
 * Netzwerk graph (network/templates/network/graph.html): fetches graph.json
 * and draws it with the vendored vis-network (static/vendor/vis-network).
 *
 * Main characters are large brass nodes, figures are coloured by faction,
 * characters a connection still points at although they are no longer a
 * favourite are small and muted. Clicking a node fills the side panel;
 * double-clicking opens its page. Every text from the server goes into the
 * DOM through textContent only -- node labels are drawn on the canvas.
 */
(function () {
  "use strict";

  var canvas = document.getElementById("network-canvas");
  var panel = document.getElementById("network-panel");
  var legend = document.getElementById("network-legend");
  if (!canvas || !panel || typeof vis === "undefined" || !vis.Network || !vis.DataSet) {
    return;
  }

  var styles = getComputedStyle(document.documentElement);
  function token(name, fallback) {
    return styles.getPropertyValue(name).trim() || fallback;
  }

  var GOLD = token("--rt-gold", "#b08d57");
  var GOLD_BRIGHT = token("--rt-gold-bright", "#dcb877");
  var TEXT = token("--rt-text", "#e9e4d5");
  var MUTED = token("--rt-text-muted", "#a7bab2");
  var BG = token("--rt-bg", "#0a1815");
  var PANEL = token("--rt-panel-raised", "#1a3b32");
  var BORDER = token("--rt-border-strong", "#3c6357");
  var FONT = getComputedStyle(document.body).fontFamily;

  /* Muted, clearly distinct hues that sit on the blue-green shell. Factions
     get them in alphabetical order, so a faction keeps its colour as long as
     no new faction sorts in front of it. */
  var PALETTE = ["#6f9fc0", "#c07a6f", "#86b07c", "#a98bc8", "#c9a45a", "#5fb5a8", "#c27fa3", "#9aa36a"];
  var NO_FACTION = "Ohne Fraktion";
  var KIND_LABELS = { main: "Hauptcharakter", character: "Charakter", figure: "Figur" };

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text) {
      node.textContent = text;
    }
    return node;
  }

  /* Same-site page links only: the URLs come from our own JSON, but the
     check keeps a stray value from ever becoming a javascript: link. */
  function isSafeUrl(url) {
    return typeof url === "string" && url.charAt(0) === "/" && url.charAt(1) !== "/" && url.indexOf("\\") === -1;
  }

  function factionColors(nodes) {
    var names = [];
    nodes.forEach(function (node) {
      if (node.kind === "figure") {
        var name = node.faction || NO_FACTION;
        if (names.indexOf(name) === -1) {
          names.push(name);
        }
      }
    });
    names.sort(function (a, b) {
      if (a === NO_FACTION) return 1;
      if (b === NO_FACTION) return -1;
      return a.localeCompare(b, "de");
    });
    var colors = {};
    names.forEach(function (name, index) {
      colors[name] = name === NO_FACTION ? MUTED : PALETTE[index % PALETTE.length];
    });
    return colors;
  }

  function visNode(node, colors) {
    if (node.kind === "main") {
      return {
        id: node.id,
        label: node.label,
        shape: "dot",
        size: 26,
        borderWidth: 3,
        color: { background: GOLD, border: GOLD_BRIGHT, highlight: { background: GOLD_BRIGHT, border: TEXT } },
        font: { color: TEXT, size: 18, face: FONT, strokeWidth: 4, strokeColor: BG },
        mass: 3,
      };
    }
    if (node.kind === "character") {
      return {
        id: node.id,
        label: node.label,
        shape: "dot",
        size: 14,
        borderWidth: 2,
        color: { background: PANEL, border: GOLD, highlight: { background: PANEL, border: GOLD_BRIGHT } },
        font: { color: MUTED, size: 14, face: FONT, strokeWidth: 3, strokeColor: BG },
      };
    }
    var color = colors[node.faction || NO_FACTION];
    return {
      id: node.id,
      label: node.label,
      shape: "dot",
      size: 14,
      borderWidth: 2,
      color: { background: color, border: BG, highlight: { background: color, border: TEXT } },
      font: { color: TEXT, size: 14, face: FONT, strokeWidth: 3, strokeColor: BG },
    };
  }

  function visEdge(edge) {
    return {
      id: edge.id,
      from: edge.from,
      to: edge.to,
      label: edge.label,
      arrows: { to: { enabled: true, scaleFactor: 0.6 } },
      color: { color: BORDER, highlight: GOLD_BRIGHT, hover: GOLD },
      width: 1.5,
      font: { color: MUTED, size: 12, face: FONT, strokeWidth: 3, strokeColor: BG, align: "middle" },
      smooth: { type: "continuous" },
    };
  }

  function renderLegend(nodes, colors) {
    if (!legend) {
      return;
    }
    legend.textContent = "";
    if (nodes.some(function (n) { return n.kind === "main"; })) {
      var main = el("li", "network-legend-item");
      main.appendChild(el("span", "network-dot is-main"));
      main.appendChild(document.createTextNode("Hauptcharakter"));
      legend.appendChild(main);
    }
    Object.keys(colors).forEach(function (name) {
      var item = el("li", "network-legend-item");
      var dot = el("span", "network-dot");
      dot.style.backgroundColor = colors[name];
      item.appendChild(dot);
      item.appendChild(document.createTextNode(name));
      legend.appendChild(item);
    });
  }

  function hint(text) {
    panel.textContent = "";
    panel.appendChild(el("p", "network-panel-hint", text));
  }

  function connectionsOf(id, data, byId) {
    var rows = [];
    data.edges.forEach(function (edge) {
      if (edge.from === id && byId[edge.to]) {
        rows.push("→ " + edge.label + " " + byId[edge.to].label);
      } else if (edge.to === id && byId[edge.from]) {
        rows.push("← " + byId[edge.from].label + " ist „" + edge.label + "“");
      }
    });
    return rows;
  }

  function showNode(node, data, byId) {
    panel.textContent = "";
    panel.appendChild(el("h2", "network-panel-title", node.label));
    var meta = KIND_LABELS[node.kind] || "";
    if (node.player) {
      meta += " · " + node.player;
    }
    panel.appendChild(el("p", "network-panel-kind", meta));

    var facts = el("dl", "network-facts");
    [["Fraktion", node.faction], ["Getroffen in", node.metAt]].forEach(function (pair) {
      if (pair[1]) {
        var row = el("div");
        row.appendChild(el("dt", "", pair[0]));
        row.appendChild(el("dd", "", pair[1]));
        facts.appendChild(row);
      }
    });
    if (facts.childNodes.length) {
      panel.appendChild(facts);
    }
    if (node.description) {
      panel.appendChild(el("p", "network-panel-description", node.description));
    }

    var rows = connectionsOf(node.id, data, byId);
    if (rows.length) {
      var list = el("ul", "network-panel-links");
      rows.forEach(function (text) {
        list.appendChild(el("li", "", text));
      });
      panel.appendChild(list);
    }

    var actions = el("div", "network-panel-actions");
    if (isSafeUrl(node.url)) {
      var open = el("a", "button", node.kind === "figure" ? "Figur öffnen" : "Bogen öffnen");
      open.href = node.url;
      actions.appendChild(open);
    }
    var createUrl = canvas.getAttribute("data-create-url");
    if (isSafeUrl(createUrl)) {
      var add = el("a", "button link-button", "Neue Figur verbunden");
      add.href = createUrl + "?zu=" + encodeURIComponent(node.id);
      actions.appendChild(add);
    }
    panel.appendChild(actions);
  }

  function draw(data) {
    if (!data.nodes.length) {
      canvas.appendChild(el("p", "network-canvas-empty", "Noch leer – leg die erste Figur an oder markiere deinen Charakter als Favorit."));
      return;
    }
    var colors = factionColors(data.nodes);
    var byId = {};
    data.nodes.forEach(function (node) {
      byId[node.id] = node;
    });
    renderLegend(data.nodes, colors);

    var network = new vis.Network(
      canvas,
      {
        nodes: new vis.DataSet(data.nodes.map(function (n) { return visNode(n, colors); })),
        edges: new vis.DataSet(data.edges.map(visEdge)),
      },
      {
        autoResize: true,
        interaction: { hover: true, tooltipDelay: 3600000, navigationButtons: false, keyboard: false },
        physics: {
          solver: "barnesHut",
          barnesHut: { gravitationalConstant: -6000, springLength: 160, springConstant: 0.03, avoidOverlap: 0.4 },
          stabilization: { iterations: 250 },
        },
        layout: { improvedLayout: true },
      }
    );

    // Exposed for the e2e test, which needs node positions to click on them.
    window.__networkGraph = network;

    network.on("click", function (params) {
      if (params.nodes.length && byId[params.nodes[0]]) {
        showNode(byId[params.nodes[0]], data, byId);
      }
    });
    network.on("doubleClick", function (params) {
      var node = params.nodes.length && byId[params.nodes[0]];
      if (node && isSafeUrl(node.url)) {
        window.location.assign(node.url);
      }
    });
  }

  fetch(canvas.getAttribute("data-graph-url"), {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  })
    .then(function (response) {
      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }
      return response.json();
    })
    .then(draw)
    .catch(function () {
      hint("Der Graph konnte nicht geladen werden. Die Liste unten zeigt alle Figuren.");
    });
})();
