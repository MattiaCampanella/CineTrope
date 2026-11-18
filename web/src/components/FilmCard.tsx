"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Poster } from "./Poster";
import type { Card } from "@/lib/types";

// Niente prefetch automatico: con decine di locandine visibili intasava il backend e il
// click reale restava in coda. Si precarica solo al passaggio del mouse.
export function FilmCard({ film }: { film: Card }) {
  const router = useRouter();
  const href = `/film/${film.id}`;
  return (
    <Link
      href={href}
      prefetch={false}
      onMouseEnter={() => router.prefetch(href)}
      onFocus={() => router.prefetch(href)}
      className="card"
      aria-label={`${film.title}${film.year ? ` (${film.year})` : ""}`}
    >
      <Poster src={film.poster} title={film.title} />
      <div className="card-info" aria-hidden="true">
        <span className="card-title">{film.title}</span>
        <span className="card-sub">
          {[film.year, film.genres.slice(0, 2).join(" · ")].filter(Boolean).join(" · ")}
        </span>
      </div>
    </Link>
  );
}
