import { api } from "@/lib/api";

export const metadata = { title: "Fonti e provenienza" };

type Data = {
  sources: { source: string; sourceLabel: string | null; triples: number }[];
  labels: Record<string, string>;
  stats: Record<string, number>;
};

const n = (v: number) => v.toLocaleString("it-IT");
const ROLE: Record<string, string> = {
  TMDB: "Film, cast, regia, generi e keyword.",
  Wikidata: "Metadati strutturati delle persone.",
  DBpedia: "Arricchimento federato (SERVICE): date di nascita.",
  Derived: "Co-star e collaborazioni calcolate con SPARQL.",
  Inferred: "Chiusura OWL RL, regole CONSTRUCT e SWRL.",
  LocalAnalysis: "Generi e gerarchie curati.",
  TvTropes: "Tropi e scene annotate (non più popolata).",
};

export default async function SourcesPage() {
  const data = await api<Data>("/api/sources");
  if (!data) return <div className="page-head"><h1>Backend non raggiungibile</h1></div>;
  const { sources, labels, stats } = data;
  return (
    <>
      <section className="page-head enter">
        <span className="eyebrow">Provenienza</span>
        <h1>Da dove arriva ogni dato</h1>
        <p>
          Ogni fonte è un named graph: nessuna reificazione, la provenienza di un’asserzione si legge con
          <code> GRAPH ?source</code>.
        </p>
      </section>
      <div className="container section">
        <div className="stat-grid">
          <div className="stat"><strong>{n(stats.triples)}</strong><span>triple totali</span></div>
          <div className="stat"><strong>{stats.named_graphs}</strong><span>named graph</span></div>
          <div className="stat"><strong>{n(stats.inferred_triples)}</strong><span>inferite</span></div>
          <div className="stat"><strong>{n(stats.films)}</strong><span>film</span></div>
        </div>
        <div className="source-grid">
          {sources.map((s) => {
            const id = s.source.split("#").pop() ?? s.source;
            return (
              <div key={s.source} className="panel">
                <p className="label">{id}</p>
                <h3>{labels[id] ?? s.sourceLabel ?? id}</h3>
                <p className="empty-inline">{ROLE[id] ?? ""}</p>
                <strong style={{ fontSize: "1.8rem", letterSpacing: "-0.04em" }}>{n(s.triples)}</strong>
                <span className="empty-inline">triple</span>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
