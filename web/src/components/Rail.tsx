"use client";
import { useRef } from "react";
import type { Card } from "@/lib/types";
import { FilmCard } from "./FilmCard";

export function Rail({
  id,
  title,
  items,
  note,
}: {
  id: string;
  title: string;
  items: Card[];
  note?: string;
}) {
  const track = useRef<HTMLUListElement>(null);
  const scroll = (dir: 1 | -1) =>
    track.current?.scrollBy({ left: dir * track.current.clientWidth * 0.85, behavior: "smooth" });
  return (
    <section className="section" aria-labelledby={`rail-${id}`}>
      <div className="section-head">
        <div>
          <h2 id={`rail-${id}`}>{title}</h2>
          {note && <p>{note}</p>}
        </div>
      </div>
      <div className="rail">
        <button className="rail-btn prev" aria-label="Scorri indietro" onClick={() => scroll(-1)}>
          ‹
        </button>
        <ul className="rail-track" ref={track}>
          {items.map((film) => (
            <li key={film.id}>
              <FilmCard film={film} />
            </li>
          ))}
        </ul>
        <button className="rail-btn next" aria-label="Scorri avanti" onClick={() => scroll(1)}>
          ›
        </button>
      </div>
    </section>
  );
}
