"use client";
import Link from "next/link";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Card, Derived, SharedItem } from "@/lib/types";
import { Poster } from "./Poster";

const GROUPS = [
  { key: "directors", label: "Regia", kind: "person" },
  { key: "actors", label: "Cast", kind: "person" },
  { key: "genres", label: "Generi", kind: "genre" },
  { key: "tropes", label: "Tropi", kind: "trope" },
] as const;

const COLOR: Record<string, string> = { person: "#7aa7ff", genre: "#f0c24b", trope: "#4fd1c5" };
const SOURCE_NAMES: Record<string, string> = {
  TMDB: "TMDB",
  Wikidata: "Wikidata",
  DBpedia: "DBpedia",
  Derived: "Dati derivati",
  Inferred: "Inferenze",
  LocalAnalysis: "Analisi locale",
};

type Path = { id: string; d: string; kind: string };

function CardSide({ film, side, refEl }: { film: Card; side: "left" | "right"; refEl: React.Ref<HTMLAnchorElement> }) {
  return (
    <Link href={`/film/${film.id}`} className={`cmap-card cmap-${side}`} ref={refEl}>
      <Poster src={film.poster} title={film.title} />
      <strong>{film.title}</strong>
      <span>{[film.year, film.genres.slice(0, 2).join(" · ")].filter(Boolean).join(" · ")}</span>
    </Link>
  );
}

export function ConnectionMap({
  seed,
  rec,
  shared,
  derived,
}: {
  seed: Card;
  rec: Card;
  shared: Record<string, SharedItem[]>;
  derived: Derived[];
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const left = useRef<HTMLAnchorElement>(null);
  const right = useRef<HTMLAnchorElement>(null);
  const chips = useRef<Record<string, HTMLButtonElement | null>>({});
  const [paths, setPaths] = useState<Path[]>([]);
  const [hover, setHover] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const items = GROUPS.flatMap((g) =>
    (shared[g.key] ?? []).map((item) => ({ ...item, uid: `${g.key}:${item.id}`, group: g.label, kind: g.kind })),
  );

  const measure = useCallback(() => {
    const w = wrap.current, l = left.current, r = right.current;
    if (!w || !l || !r) return;
    const wr = w.getBoundingClientRect(), lr = l.getBoundingClientRect(), rr = r.getBoundingClientRect();
    const posterL = l.querySelector(".poster")?.getBoundingClientRect() ?? lr;
    const posterR = r.querySelector(".poster")?.getBoundingClientRect() ?? rr;
    const n = items.length;
    const spread = (box: DOMRect, i: number) =>
      box.top - wr.top + 18 + (n > 1 ? ((box.height - 36) * i) / (n - 1) : (box.height - 36) / 2);
    const next: Path[] = [];
    items.forEach((item, i) => {
      const el = chips.current[item.uid];
      if (!el) return;
      const c = el.getBoundingClientRect();
      const cy = c.top - wr.top + c.height / 2;
      const x1 = posterL.right - wr.left, y1 = spread(posterL, i);
      const x2 = c.left - wr.left;
      const x3 = c.right - wr.left;
      const x4 = posterR.left - wr.left, y4 = spread(posterR, i);
      const k1 = (x2 - x1) * 0.55, k2 = (x4 - x3) * 0.55;
      next.push({ id: item.uid, kind: item.kind, d: `M${x1},${y1} C${x1 + k1},${y1} ${x2 - k1},${cy} ${x2},${cy}` });
      next.push({ id: item.uid, kind: item.kind, d: `M${x3},${cy} C${x3 + k2},${cy} ${x4 - k2},${y4} ${x4},${y4}` });
    });
    setPaths(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shared]);

  useLayoutEffect(() => {
    measure();
    const ro = new ResizeObserver(measure);
    if (wrap.current) ro.observe(wrap.current);
    window.addEventListener("resize", measure);
    // le immagini cambiano l'altezza delle card dopo il primo layout
    const t = setTimeout(measure, 400);
    const t2 = setTimeout(measure, 1500);
    return () => { ro.disconnect(); window.removeEventListener("resize", measure); clearTimeout(t); clearTimeout(t2); };
  }, [measure]);

  useEffect(() => { void document.fonts?.ready.then(measure); }, [measure]);

  const focus = hover ?? selected;
  const chosen = items.find((i) => i.uid === selected);

  return (
    <div>
      <div className="cmap" ref={wrap}>
        <svg className="cmap-svg" aria-hidden="true">
          {paths.map((p, i) => (
            <path
              key={i}
              d={p.d}
              fill="none"
              stroke={COLOR[p.kind]}
              strokeWidth={focus === p.id ? 2.5 : 1.2}
              strokeOpacity={focus ? (focus === p.id ? 0.95 : 0.07) : 0.34}
              style={{ transition: "stroke-opacity .25s, stroke-width .25s" }}
            />
          ))}
        </svg>

        <CardSide film={seed} side="left" refEl={left} />

        <div className="cmap-lane">
          {GROUPS.map((g) => {
            const list = shared[g.key] ?? [];
            return (
              <section key={g.key} className="cmap-group" aria-label={g.label}>
                <h4>
                  {g.label} <b>{list.length}</b>
                </h4>
                {list.length === 0 ? (
                  <p className="empty-inline">Nessun elemento in comune.</p>
                ) : (
                  <div className="cmap-chips">
                    {list.map((item) => {
                      const uid = `${g.key}:${item.id}`;
                      return (
                        <button
                          key={uid}
                          ref={(el) => { chips.current[uid] = el; }}
                          className="cmap-chip"
                          style={{ ["--c" as string]: COLOR[g.kind] }}
                          aria-pressed={selected === uid}
                          onMouseEnter={() => setHover(uid)}
                          onMouseLeave={() => setHover(null)}
                          onFocus={() => setHover(uid)}
                          onBlur={() => setHover(null)}
                          onClick={() => setSelected(selected === uid ? null : uid)}
                        >
                          {item.label}
                        </button>
                      );
                    })}
                  </div>
                )}
              </section>
            );
          })}
        </div>

        <CardSide film={rec} side="right" refEl={right} />
      </div>

      <div className="cmap-detail" aria-live="polite">
        {chosen ? (
          <>
            <p className="label">{chosen.group}</p>
            <h3>{chosen.label}</h3>
            <p className="empty-inline">
              Asserito in:{" "}
              {chosen.sources.length
                ? chosen.sources.map((s) => SOURCE_NAMES[s] ?? s).join(" · ")
                : "fonte non disponibile"}
            </p>
          </>
        ) : (
          <p className="empty-inline">
            Passa il mouse o clicca un elemento per evidenziare il percorso e leggere da quale named graph proviene.
          </p>
        )}
      </div>

      {derived.length > 0 && (
        <section className="cmap-derived" aria-label="Legami derivati">
          <p className="label">Legami derivati dal ragionamento</p>
          <ul>
            {derived.map((d, i) => (
              <li key={i}>
                <strong>{d.via}</strong>
                <span>{d.relation}</span>
                <small>{d.rule}</small>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
