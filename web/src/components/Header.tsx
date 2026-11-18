"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/search", label: "Cerca" },
  { href: "/queries", label: "Query" },
  { href: "/sources", label: "Fonti" },
];

export function Header() {
  const path = usePathname();
  const [solid, setSolid] = useState(false);
  useEffect(() => {
    const onScroll = () => setSolid(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <header className="header" data-solid={solid}>
      <Link href="/" className="brand" aria-label="CineTrope, home">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="brand-mark" src="/favicon.svg" alt="" width={34} height={34} />
        <span>CineTrope</span>
      </Link>
      <nav className="nav" aria-label="Principale">
        {NAV.map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            aria-current={(href === "/" ? path === "/" : path.startsWith(href)) ? "page" : undefined}
          >
            {label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
