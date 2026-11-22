import Link from "next/link";
import { api } from "@/lib/api";
import type { Home } from "@/lib/types";
import { Poster } from "@/components/Poster";
import { Rail } from "@/components/Rail";

export const metadata = { title: "Raccomandazioni spiegabili" };

const NOTES: Record<string, string> = {
  awarded: "Classe definita con owl:hasValue su codice premio Wikidata (Oscar Best Picture).",
  acclaimed_blockbuster: "Intersezione di classi definite: AcclaimedFilm ⊓ Blockbuster (HermiT).",
  premio: "Inferita dalla regola SWRL EnsembleAwardRule (EnsembleFilm ∧ AcclaimedFilm ∧ ProfitableFilm).",
  profitable: "Datatype restriction su ROI ≥ 2.0 (incasso almeno doppio rispetto al budget, HermiT).",
  notable: "Unione chiusa di classi definite: AcclaimedFilm ⊔ AwardedFilm ⊔ Blockbuster (owl:unionOf).",
  acclaimed: "Voto medio TMDB ≥ 7.5 (datatype restriction xsd:minInclusive, HermiT).",
  blockbuster: "Incasso ≥ 500 milioni USD (datatype restriction, classificato da HermiT).",
  epic: "Durata ≥ 150 minuti (datatype restriction; complementare a StandardLengthFilm sotto OWA).",
  collection: "Appartiene a una collezione/franchise (someValuesFrom su classe nominata, HermiT).",
  ensemble: "Sette o più attori accreditati (datatype restriction castSize ≥ 7, HermiT).",
  tropes: "Più keyword narrative, più strade verso altri film.",
};

const n = (value: number) => value.toLocaleString("it-IT");

export default async function HomePage() {
  const home = await api<Home>("/api/home");
  if (!home) {
    return (
      <div className="page-head">
        <h1>Backend non raggiungibile</h1>
        <p>
          Il server semantico non risponde su 127.0.0.1:8000. Avvia tutto con <code>.\run.ps1</code>.
        </p>
      </div>
    );
  }
  const { hero, rows, stats } = home;
  const meta = [hero.year, hero.genres.slice(0, 3).join(" · "), hero.directors[0]].filter(Boolean);

  return (
    <>
      <section className="billboard" aria-label="In evidenza">
        <Poster className="billboard-bg" src={hero.backdrop ?? hero.poster} title={hero.title} eager />
        <div className="billboard-inner enter">
          <span className="eyebrow">In evidenza · grafo di conoscenza</span>
          <h1>{hero.title}</h1>
          <div className="meta-line">
            {meta.map((part, i) => (
              <span key={part} style={{ display: "contents" }}>
                {i > 0 && <span className="dot" />}
                <span>{part}</span>
              </span>
            ))}
          </div>
          <div className="cta-row">
            <Link href={`/film/${hero.id}`} className="btn btn-primary">
              ▶ Scopri film simili
            </Link>
            <Link href="/search" className="btn">
              Cerca un film
            </Link>
          </div>
        </div>
      </section>

      {rows.map((row) => (
        <Rail key={row.id} id={row.id} title={row.title} items={row.items} note={NOTES[row.id]} />
      ))}

      <section className="moment" aria-labelledby="moment-title">
        <h2 id="moment-title">
          Ogni film è un grafo. Ogni consiglio ha <em>una prova</em>.
        </h2>
        <div className="stat-grid">
          <div className="stat"><strong>{n(stats.films)}</strong><span>film</span></div>
          <div className="stat"><strong>{n(stats.tropes)}</strong><span>tropi narrativi</span></div>
          <div className="stat"><strong>{n(stats.inferred_triples)}</strong><span>triple inferite</span></div>
          <div className="stat"><strong>{stats.named_graphs}</strong><span>named graph di provenienza</span></div>
        </div>
        <div className="cta-row">
          <Link href="/queries" className="btn">Competency questions</Link>
          <Link href="/sources" className="btn">Da dove arrivano i dati</Link>
        </div>
      </section>
    </>
  );
}
