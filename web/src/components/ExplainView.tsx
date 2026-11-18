"use client";
import { useState } from "react";
import type { Card, Derived, Explanation, SharedItem } from "@/lib/types";
import { ConnectionMap } from "./ConnectionMap";
import { GraphView } from "./GraphView";

export function ExplainView({
  seed,
  rec,
  shared,
  derived,
  graph,
}: {
  seed: Card;
  rec: Card;
  shared: Record<string, SharedItem[]>;
  derived: Derived[];
  graph: Explanation;
}) {
  const [tab, setTab] = useState<"map" | "rdf">("map");
  return (
    <div>
      <div className="seg tabs" role="tablist" aria-label="Vista della spiegazione">
        <button role="tab" aria-selected={tab === "map"} onClick={() => setTab("map")}>
          Mappa delle connessioni
        </button>
        <button role="tab" aria-selected={tab === "rdf"} onClick={() => setTab("rdf")}>
          Grafo RDF completo
        </button>
      </div>
      {tab === "map" ? (
        <ConnectionMap seed={seed} rec={rec} shared={shared} derived={derived} />
      ) : (
        <GraphView graph={graph} />
      )}
    </div>
  );
}
