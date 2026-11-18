"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useRef, useState } from "react";
import type { Explanation } from "@/lib/types";

const PALETTE: Record<string, { bg: string; border: string; font: string; shape: string; label: string }> = {
  seed: { bg: "#f6f5f2", border: "#f6f5f2", font: "#000000", shape: "box", label: "Film scelto" },
  recommendation: { bg: "#ff7a2f", border: "#ff7a2f", font: "#1a0b02", shape: "box", label: "Raccomandazione" },
  trope: { bg: "#06231f", border: "#4fd1c5", font: "#bff3ee", shape: "dot", label: "Tropo" },
  person: { bg: "#0d1a38", border: "#7aa7ff", font: "#d3e1ff", shape: "dot", label: "Persona" },
  genre: { bg: "#2a2208", border: "#f0c24b", font: "#f7e3a6", shape: "dot", label: "Genere" },
  source: { bg: "#111111", border: "#7d7c85", font: "#b4b3ba", shape: "dot", label: "Named graph" },
  other: { bg: "#111111", border: "#7d7c85", font: "#b4b3ba", shape: "dot", label: "Risorsa" },
};
const FACE = "Geist, Segoe UI, sans-serif";
const HINT = "Seleziona un nodo: gli archi collegati mostrano il nome della relazione.";

type VisLib = { Network: new (el: HTMLElement, data: object, opts: object) => any; DataSet: new (items: object[]) => any };

// vis-network viene caricato come script UMD da /public: il bundle ESM compilato da Next
// non disegnava il canvas (verificato con un test isolato), l'UMD sì.
function loadVis(): Promise<VisLib> {
  const w = window as unknown as { vis?: VisLib };
  if (w.vis) return Promise.resolve(w.vis);
  return new Promise((resolve, reject) => {
    const el = document.createElement("script");
    el.src = "/vendor/vis-network.min.js";
    el.onload = () => (w.vis ? resolve(w.vis) : reject(new Error("vis non disponibile")));
    el.onerror = () => reject(new Error("vis-network non caricato"));
    document.head.appendChild(el);
  });
}

export function GraphView({ graph }: { graph: Explanation }) {
  const ref = useRef<HTMLDivElement>(null);
  const net = useRef<any>(null);
  const [info, setInfo] = useState(HINT);
  const [showSources, setShowSources] = useState(false);
  const [settling, setSettling] = useState(true);

  useEffect(() => {
    let destroyed = false;
    let network: any = null;
    setSettling(true);
    setInfo(HINT);

    (async () => {
      const { Network, DataSet } = await loadVis();
      if (destroyed || !ref.current) return;

      const keep = new Set(graph.nodes.filter((n) => showSources || n.group !== "source").map((n) => n.id));
      const nodeList = graph.nodes
        .filter((n) => keep.has(n.id))
        .map((n) => {
          const p = PALETTE[n.group] ?? PALETTE.other;
          const big = n.group === "seed" || n.group === "recommendation";
          return {
            id: n.id,
            label: n.label,
            group: n.group,
            shape: p.shape,
            size: big ? 22 : 11,
            margin: big ? 12 : 6,
            borderWidth: big ? 0 : 2,
            color: { background: p.bg, border: p.border, highlight: { background: p.bg, border: "#ffffff" }, hover: { background: p.bg, border: "#ffffff" } },
            font: { color: big ? p.font : "#d9d8de", face: FACE, size: big ? 17 : 12 },
            opacity: 1,
          };
        });
      const edgeList = graph.edges
        .filter((e) => keep.has(e.from) && keep.has(e.to))
        .map((e) => ({
          id: e.id,
          from: e.from,
          to: e.to,
          title: e.label,
          baseLabel: e.label,
          label: "",
          arrows: { to: { enabled: true, scaleFactor: 0.45 } },
          color: { color: "#2a2a30", highlight: "#ff7a2f", hover: "#ff7a2f" },
          font: { color: "#ff9a5c", size: 11, face: FACE, strokeWidth: 4, strokeColor: "#000000", align: "middle" },
          smooth: { enabled: true, type: "dynamic" },
          width: 1,
        }));
      const nodes = new DataSet(nodeList);
      const edges = new DataSet(edgeList);

      network = new Network(ref.current, { nodes, edges }, {
        autoResize: true,
        interaction: { hover: true, tooltipDelay: 150, keyboard: true, zoomView: true },
        // Il layout si assesta e poi si BLOCCA: niente deriva continua del grafo.
        physics: {
          solver: "forceAtlas2Based",
          forceAtlas2Based: { gravitationalConstant: -70, centralGravity: 0.012, springLength: 115, springConstant: 0.07, damping: 0.55, avoidOverlap: 0.8 },
          stabilization: { enabled: true, iterations: 320, updateInterval: 40, fit: true },
          minVelocity: 0.6,
          maxVelocity: 30,
        },
      });
      net.current = network;

      network.once("stabilizationIterationsDone", () => {
        network.setOptions({ physics: { enabled: false } });
        network.fit({ animation: { duration: 500, easingFunction: "easeInOutQuad" } });
        setSettling(false);
      });

      const highlight = (id: string | null) => {
        const connected = id ? new Set<string>([id, ...network.getConnectedNodes(id)]) : null;
        nodes.update(nodeList.map((n) => ({ id: n.id, opacity: !connected || connected.has(n.id) ? 1 : 0.12 })));
        edges.update(
          edgeList.map((e) => {
            const on = !id || e.from === id || e.to === id;
            return {
              id: e.id,
              label: id && on ? e.baseLabel : "",
              width: id && on ? 2 : 1,
              color: { color: !id ? "#2a2a30" : on ? "#ff7a2f" : "rgba(42,42,48,0.2)", highlight: "#ff7a2f", hover: "#ff7a2f" },
            };
          }),
        );
      };

      network.on("click", (params: { nodes: string[] }) => {
        const id = params.nodes[0] ?? null;
        highlight(id);
        if (!id) return setInfo(HINT);
        const node = graph.nodes.find((n) => n.id === id);
        const group = (PALETTE[node?.group ?? "other"] ?? PALETTE.other).label;
        const count = network.getConnectedNodes(id).length;
        setInfo(`${node?.label ?? ""} · ${group} · ${count} collegamenti`);
      });
    })().catch((e) => console.error("GraphView:", e));

    return () => {
      destroyed = true;
      net.current = null;
      network?.destroy();
    };
  }, [graph, showSources]);

  const relayout = () => {
    const n = net.current;
    if (!n) return;
    setSettling(true);
    n.setOptions({ physics: { enabled: true } });
    n.once("stabilizationIterationsDone", () => {
      n.setOptions({ physics: { enabled: false } });
      n.fit({ animation: { duration: 500 } });
      setSettling(false);
    });
    n.stabilize(200);
  };

  return (
    <div className="graph-wrap">
      <div className="graph-bar">
        <div className="legend">
          {(["seed", "recommendation", "trope", "person", "genre"] as const).map((k) => (
            <span key={k}>
              <i style={{ background: PALETTE[k].border }} />
              {PALETTE[k].label}
            </span>
          ))}
        </div>
        <div className="badge-row">
          <button className="btn btn-sm" aria-pressed={showSources} onClick={() => setShowSources((v) => !v)}>
            Fonti {showSources ? "visibili" : "nascoste"}
          </button>
          <button className="btn btn-sm" onClick={() => net.current?.fit({ animation: { duration: 400 } })}>
            Adatta
          </button>
          <button className="btn btn-sm" onClick={relayout} disabled={settling}>
            {settling ? "Assestamento…" : "Ricalcola layout"}
          </button>
        </div>
      </div>
      <div ref={ref} className="network" role="img" aria-label="Grafo RDF interattivo della spiegazione" />
      <div className="node-info">{info}</div>
    </div>
  );
}
