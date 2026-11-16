(function () {
  "use strict";

  const container = document.getElementById("network");
  const graph = window.CINETROPE_GRAPH;
  if (!container || !graph || !window.vis) {
    return;
  }

  const palette = {
    seed: { background: "#eceae4", border: "#eceae4", font: "#15181e" },
    recommendation: { background: "#f08a4b", border: "#f08a4b", font: "#1a0e05" },
    trope: { background: "#12302d", border: "#4fc3b8", font: "#bdeee9" },
    person: { background: "#1a2640", border: "#7aa2f0", font: "#c9d9fa" },
    genre: { background: "#38300f", border: "#e0b04a", font: "#f3dca0" },
    source: { background: "#1e2229", border: "#868b95", font: "#aeb2ba" },
    film: { background: "#16191e", border: "#eceae4", font: "#eceae4" },
    other: { background: "#1e2229", border: "#868b95", font: "#aeb2ba" }
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
          highlight: { background: colors.background, border: "#ffffff" },
          hover: { background: colors.background, border: "#ffffff" }
        },
        font: {
          color: colors.font,
          face: "Geist, Segoe UI, sans-serif",
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
        color: { color: "#3a3f49", highlight: "#f08a4b", hover: "#f08a4b" },
        font: {
          color: "#aeb2ba",
          size: 11,
          face: "Geist, Segoe UI, sans-serif",
          background: "#0e1013",
          strokeWidth: 0
        },
        smooth: { enabled: true, type: "continuous" },
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
        stabilization: { iterations: 120, updateInterval: 40 }
      },
      edges: { selectionWidth: 1.8 },
      nodes: { borderWidth: 1.5, shadow: false }
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
