import Link from "next/link";
import { notFound } from "next/navigation";
import { api, PRIORITIES } from "@/lib/api";
import type { FilmPage, Item } from "@/lib/types";
import { Avatar, Poster } from "@/components/Poster";

type Props = { params: Promise<{ id: string }>; searchParams: Promise<{ priority?: string }> };

export async function generateMetadata({ params }: Props) {
  const { id } = await params;
  const page = await api<FilmPage>(`/api/film/${id}`);
  return { title: page?.film.title ?? "Film" };
}

function Chips({ items, kind, max = 6 }: { items: Item[]; kind: string; max?: number }) {
  if (!items.length) return <p className="empty-inline">Nessuno in comune.</p>;
  return (
    <div className="chip-row">
      {items.slice(0, max).map((i) => (
        <span key={i.id} className={`chip chip-${kind}`}>{i.label}</span>
      ))}
      {items.length > max && <span className="chip">+{items.length - max}</span>}
    </div>
  );
}

export default async function FilmPageRoute({ params, searchParams }: Props) {
  const { id } = await params;
  const { priority: raw } = await searchParams;
  const priority = raw && raw in PRIORITIES ? raw : "balanced";
  const page = await api<FilmPage>(`/api/film/${id}?priority=${priority}`);
  if (!page) notFound();
  const { film, recommendations } = page;

  return (
    <>
      <section className="film-hero">
        {film.backdrop && (
          <Poster className="film-hero-bg" src={film.backdrop} title={film.title} eager />
        )}
        <div className="film-hero-grid">
          <Poster src={film.poster} title={film.title} eager />
          <div className="film-hero-copy enter">
            <span className="eyebrow">Raccomandazioni per</span>
            <h1>
              {film.title}
              {film.year && <small>{film.year}</small>}
            </h1>
            <div className="badge-row">
              <span className="badge">{film.type}</span>
              {film.classes.map((c) => (
                <span key={c} className="badge badge-accent">{c}</span>
              ))}
              {film.genres.map((g) => (
                <span key={g.id} className="badge">{g.label}</span>
              ))}
            </div>
            <div>
              <p className="label">Regia e cast</p>
              <div className="people">
                {[...film.directors, ...film.actors.slice(0, 5)].map((p) => (
                  <span key={p.id} className="person">
                    <Avatar src={p.photo} name={p.label} />
                    {p.label}
                  </span>
                ))}
              </div>
            </div>
            <div>
              <p className="label">Tropi · {film.tropes.length}</p>
              <div className="chip-row">
                {film.tropes.slice(0, 14).map((t) => (
                  <span key={t.id} className="chip chip-trope">{t.label}</span>
                ))}
                {film.tropes.length > 14 && <span className="chip">+{film.tropes.length - 14}</span>}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="container section" aria-labelledby="recs-title">
        <div className="section-head" style={{ padding: 0 }}>
          <div>
            <p className="eyebrow">Top 5</p>
            <h2 id="recs-title">Perché questi film</h2>
          </div>
          <nav className="seg" aria-label="Priorità delle raccomandazioni">
            {Object.entries(PRIORITIES).map(([key, label]) => (
              <Link key={key} href={`/film/${film.id}?priority=${key}`} aria-current={key === priority} scroll={false}>
                {label}
              </Link>
            ))}
          </nav>
        </div>

        <ol className="rec-list">
          {recommendations.map((rec, i) => (
            <li key={rec.id} className="rec">
              <span className="rec-rank" aria-hidden="true">{i + 1}</span>
              <Link href={`/film/${rec.id}`} aria-label={rec.title}>
                <Poster src={rec.poster} title={rec.title} />
              </Link>
              <div className="rec-body">
                <div className="rec-top">
                  <div>
                    <h3><Link href={`/film/${rec.id}`}>{rec.title}</Link></h3>
                    <p>{[rec.year, rec.genres?.slice(0, 3).join(" · ")].filter(Boolean).join(" · ")}</p>
                  </div>
                  <div className="score"><strong>{rec.score}</strong><span>punti</span></div>
                </div>
                <div className="shared-grid">
                  <div><h4>Tropi condivisi<b>{rec.shared_tropes_count}</b></h4><Chips items={rec.shared_tropes} kind="trope" /></div>
                  <div><h4>Regia<b>{rec.shared_directors_count}</b></h4><Chips items={rec.shared_directors} kind="person" /></div>
                  <div><h4>Cast<b>{rec.shared_actors_count}</b></h4><Chips items={rec.shared_actors} kind="person" max={4} /></div>
                  <div><h4>Generi<b>{rec.shared_genres_count}</b></h4><Chips items={rec.shared_genres} kind="genre" /></div>
                </div>
                <div className="rec-foot">
                  <div className="badge-row">
                    {Object.entries(rec.source_summary ?? {}).map(([src, count]) => (
                      <span key={src} className="badge">{src} · {count}</span>
                    ))}
                  </div>
                  <Link href={`/explain/${film.id}/${rec.id}`} className="btn btn-sm">Esplora il grafo →</Link>
                </div>
              </div>
            </li>
          ))}
        </ol>
        {recommendations.length === 0 && <p className="empty-inline">Nessuna raccomandazione disponibile.</p>}
      </section>
    </>
  );
}
