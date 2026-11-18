import Link from "next/link";

export default function NotFound() {
  return (
    <section className="page-head enter">
      <span className="eyebrow">404</span>
      <h1>Questo film non è nel catalogo</h1>
      <p>La pagina cercata non esiste o il film non è stato importato.</p>
      <div className="cta-row">
        <Link href="/" className="btn btn-primary">Torna alla home</Link>
        <Link href="/search" className="btn">Cerca un film</Link>
      </div>
    </section>
  );
}
