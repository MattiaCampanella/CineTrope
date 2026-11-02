(function () {
  "use strict";

  const container = document.getElementById("network");
  const graph = window.CINETROPE_GRAPH;
  if (!container || !graph || !window.vis) {
    return;
  }

  const palette = {
    seed: { background: "#f5c451", border: "#fff1c9", font: "#1a1406" },
    recommendation: { background: "#e35d5d", border: "#ffd1d1", font: "#1c0808" },
    trope: { background: "#a78bfa", border: "#e4dbff", font: "#140b2b" },
    person: { background: "#4fd1c5", border: "#c8fff8", font: "#04201d" },
    genre: { background: "#f59e0b", border: "#ffe6b3", font: "#241604" },
    source: { background: "#64748b", border: "#d4dce7", font: "#f8fafc" },
    film: { background: "#60a5fa", border: "#d7e9ff", font: "#071b33" },
    other: { background: "#94a3b8", border: "#e2e8f0", font: "#0f172a" }
  };

  const shapes = {
    seed: "box",
    recommendation: "diamond",
    trope: "ellipse",
    person: "dot",
    genre: "hexagon",
    source: "database",
    film: "box",
    other: "dot"
  };

  const typeLabels = {
    seed: "Film scelto",
    recommendation: "Raccomandazione",
    trope: "Tropo narrativo",
    person: "Persona",
    genre: "Genere",
    source: "Named graph / fonte",
    film: "Film",
    other: "Risorsa"
  };

  const nodes = new vis.DataSet(
    graph.nodes.map(function (node) {
      const group = node.group || "other";
      const colors = palette[group] || palette.other;
      return {
        id: node.id,
        label: node.label,
        group: group,
        shape: shapes[group] || "dot",
        size: group === "seed" ? 30 : group === "recommendation" ? 26 : group === "source" ? 18 : 20,
        color: {
          background: colors.background,
          border: colors.border,
          highlight: { background: colors.border, border: "#ffffff" },
          hover: { background: colors.border, border: "#ffffff" }
        },
        font: {
          color: colors.font,
          face: "Inter, Segoe UI, sans-serif",
          size: group === "seed" || group === "recommendation" ? 16 : 13,
          strokeWidth: 0
        },
        title: typeLabels[group] || typeLabels.other
      };
    })
  );

  const edges = new vis.DataSet(
    graph.edges.map(function (edge) {
      return {
        id: edge.id,
        from: edge.from,
        to: edge.to,
        label: edge.label,
        arrows: { to: { enabled: true, scaleFactor: 0.65 } },
        color: { color: "rgba(203, 213, 225, 0.42)", highlight: "#f5c451", hover: "#f5c451" },
        font: {
          color: "#cbd5e1",
          size: 11,
          face: "Inter, Segoe UI, sans-serif",
          background: "rgba(9, 11, 17, 0.82)",
          strokeWidth: 0
        },
        smooth: { enabled: true, type: "dynamic" },
        width: 1.2
      };
    })
  );

  const network = new vis.Network(
    container,
    { nodes: nodes, edges: edges },
    {
      autoResize: true,
      interaction: { hover: true, tooltipDelay: 120, navigationButtons: false, keyboard: true },
      physics: {
        enabled: true,
        barnesHut: {
          gravitationalConstant: -9000,
          centralGravity: 0.22,
          springLength: 150,
          springConstant: 0.035,
          damping: 0.2,
          avoidOverlap: 0.25
        },
        stabilization: { iterations: 260, updateInterval: 30 }
      },
      edges: { selectionWidth: 1.8 },
      nodes: { borderWidth: 2, shadow: { enabled: true, color: "rgba(245, 196, 81, 0.2)", size: 12 } }
    }
  );

  const info = document.getElementById("node-info");
  network.on("click", function (params) {
    if (!params.nodes.length) {
      info.textContent = "Seleziona un nodo per leggerne il tipo e le relazioni.";
      return;
    }
    const nodeId = params.nodes[0];
    const node = nodes.get(nodeId);
    const connected = network.getConnectedEdges(nodeId).map(function (edgeId) {
      const edge = edges.get(edgeId);
      const otherId = edge.from === nodeId ? edge.to : edge.from;
      const other = nodes.get(otherId);
      return (edge.label || edge.predicate) + " · " + (other ? other.label : otherId);
    });
    info.textContent = "";
    const title = document.createElement("strong");
    title.textContent = node.label + " — " + (typeLabels[node.group] || typeLabels.other);
    info.appendChild(title);
    if (!connected.length) {
      const empty = document.createElement("span");
      empty.textContent = "Nessuna relazione visibile.";
      info.appendChild(empty);
      return;
    }
    const list = document.createElement("ul");
    connected.slice(0, 10).forEach(function (text) {
      const item = document.createElement("li");
      item.textContent = text;
      list.appendChild(item);
    });
    info.appendChild(list);
  });

  const fitButton = document.getElementById("fit-graph");
  const physicsButton = document.getElementById("toggle-physics");
  let physicsEnabled = true;

  network.once("stabilizationIterationsDone", function () {
    physicsEnabled = false;
    network.setOptions({ physics: { enabled: false } });
    if (physicsButton) {
      physicsButton.textContent = "Fisica off";
    }
  });

  if (fitButton) {
    fitButton.addEventListener("click", function () {
      network.fit({ animation: { duration: 500, easingFunction: "easeInOutQuad" } });
    });
  }
  if (physicsButton) {
    physicsButton.addEventListener("click", function () {
      physicsEnabled = !physicsEnabled;
      network.setOptions({ physics: { enabled: physicsEnabled } });
      physicsButton.textContent = physicsEnabled ? "Fisica on" : "Fisica off";
    });
  }
})();
