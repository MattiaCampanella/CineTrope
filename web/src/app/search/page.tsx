"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { Card } from "@/lib/types";
import { FilmCard } from "@/components/FilmCard";

const CLASSES: [string, string][] = [
  ["AcclaimedFilm", "Acclamati (≥ 7.5)"],
  ["Blockbuster", "Blockbuster (≥ 500M $)"],
  ["AcclaimedBlockbuster", "Blockbuster acclamati"],
  ["ProfitableFilm", "Profittevoli (ROI ≥ 2×)"],
  ["BoxOfficeFlop", "Flop al botteghino"],
  ["NotableFilm", "Notevoli (owl:unionOf)"],
  ["EpicFilm", "Kolossal (≥ 150 min)"],
  ["StandardLengthFilm", "Durata standard (¬Epic)"],
  ["CollectionFilm", "Franchise"],
  ["MultiGenreFilm", "Multigenere (≥ 3 generi)"],
  ["EnsembleFilm", "Film corali (≥ 7 attori)"],
  ["AwardedFilm", "Oscar Miglior Film"],
  ["PremioFilm", "Corali acclamati (SWRL)"],
];

type Suggestion = { label: string; kind: string; id: string };

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [cls, setCls] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [results, setResults] = useState<Card[] | null>(null);
  const [suggest, setSuggest] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const seq = useRef(0);

  // Ricerca con debounce; il numero d'ordine scarta le risposte superate.
  useEffect(() => {
    if (!q && !cls && !from && !to) {
      setResults(null);
      return;
    }
    const id = ++seq.current;
    const t = setTimeout(async () => {
      setLoading(true);
      const params = new URLSearchParams({ limit: "60" });
      if (q) params.set("title", q);
      if (cls) params.set("cls", cls);
      if (from) params.set("year_from", from);
      if (to) params.set("year_to", to);
      try {
        const res = await fetch(`/api/search?${params}`);
        const data = await res.json();
        if (id === seq.current) setResults(res.ok ? data.results : []);
      } finally {
        if (id === seq.current) setLoading(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [q, cls, from, to]);

  useEffect(() => {
    if (q.trim().length < 2) return setSuggest([]);
    const t = setTimeout(async () => {
      const res = await fetch(`/api/suggest?q=${encodeURIComponent(q)}`);
      if (res.ok) setSuggest(((await res.json()) as Suggestion[]).filter((s) => s.kind === "film").slice(0, 6));
    }, 120);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <>
      <section className="search-hero enter">
        <h1 style={{ fontSize: "clamp(2.2rem,5vw,4rem)", letterSpacing: "-0.045em" }}>Cerca un film</h1>
        <div className="suggest">
          <input
            className="search-input"
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Titolo, per esempio Inception"
            aria-label="Titolo del film"
            autoFocus
            autoComplete="off"
          />
          {suggest.length > 0 && (
            <div className="suggest-list" role="listbox">
              {suggest.map((s) => (
                <Link key={s.id} href={`/film/${s.id}`} role="option" aria-selected={false}>
                  <span>{s.label}</span>
                  <small>Apri</small>
                </Link>
              ))}
            </div>
          )}
        </div>
        <div className="filters" role="group" aria-label="Classi definite">
          {CLASSES.map(([value, label]) => (
            <button
              key={value}
              className="filter"
              aria-pressed={cls === value}
              onClick={() => setCls(cls === value ? "" : value)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="filters">
          <input className="filter" style={{ width: 130 }} type="number" placeholder="Anno da" value={from} onChange={(e) => setFrom(e.target.value)} aria-label="Anno da" />
          <input className="filter" style={{ width: 130 }} type="number" placeholder="Anno a" value={to} onChange={(e) => setTo(e.target.value)} aria-label="Anno a" />
        </div>
        <p className="empty-inline" aria-live="polite">
          {loading ? "Cerco…" : results ? `${results.length} risultati` : "Scrivi un titolo o scegli una classe: le classi sono definite nell’ontologia."}
        </p>
      </section>

      {results && (
        <ul className="grid">
          {results.map((film) => (
            <li key={film.id}><FilmCard film={film} /></li>
          ))}
        </ul>
      )}
    </>
  );
}
