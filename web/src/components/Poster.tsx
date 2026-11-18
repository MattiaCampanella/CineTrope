"use client";
import { useState } from "react";

// Colore deterministico dal titolo: il segnaposto tipografico resta elegante anche senza immagini.
function tint(title: string) {
  let h = 0;
  for (const ch of title) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return `linear-gradient(155deg, hsl(${h} 34% 17%), hsl(${(h + 40) % 360} 40% 5%))`;
}

export function Poster({
  src,
  title,
  className = "poster",
  eager = false,
}: {
  src: string | null;
  title: string;
  className?: string;
  eager?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  return (
    <div className={className}>
      <div className="art-fallback" style={{ background: tint(title) }}>
        <span>{title}</span>
      </div>
      {src && !failed && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={title}
          loading={eager ? "eager" : "lazy"}
          decoding="async"
          onError={() => setFailed(true)}
        />
      )}
    </div>
  );
}

export function Avatar({ src, name }: { src: string | null; name: string }) {
  const [failed, setFailed] = useState(false);
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("");
  return (
    <span className="avatar">
      {initials}
      {src && !failed && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" loading="lazy" onError={() => setFailed(true)} />
      )}
    </span>
  );
}
