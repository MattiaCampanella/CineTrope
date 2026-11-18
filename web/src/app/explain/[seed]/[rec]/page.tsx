import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import type { Card, Explanation, Relation } from "@/lib/types";
import { ExplainView } from "@/components/ExplainView";

type Props = { params: Promise<{ seed: string; rec: string }> };

export const metadata = { title: "Spiegazione" };

export default async function ExplainPage({ params }: Props) {
  const { seed, rec } = await params;
  const [a, b, graph, relation] = await Promise.all([
    api<Card>(`/api/card/${seed}`),
    api<Card>(`/api/card/${rec}`),
    api<Explanation>(`/api/explanation/${seed}/${rec}`),
    api<Relation>(`/api/relation/${seed}/${rec}`),
  ]);
  if (!a || !b || !graph) notFound();

  return (
    <>
      <section className="page-head enter">
        <Link href={`/film/${seed}`} className="eyebrow">← Torna alle raccomandazioni</Link>
        <h1>
          {a.title} <span style={{ color: "var(--ink-3)" }}>→</span> {b.title}
        </h1>
        <p>
          Cosa lega i due film e da quale named graph proviene ogni dato. Le curve sono le asserzioni condivise; i legami
          derivati arrivano dal ragionamento (property chain e regole SWRL).
        </p>
        <div className="badge-row">
          <span className="badge">{graph.node_count} nodi</span>
          <span className="badge">{graph.edge_count} archi</span>
          <span className="badge">{graph.triple_count} triple</span>
        </div>
      </section>
      <div className="container section">
        <ExplainView
          seed={a}
          rec={b}
          shared={relation?.shared ?? {}}
          derived={relation?.derived ?? []}
          graph={graph}
        />
      </div>
    </>
  );
}
