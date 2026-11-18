import Link from "next/link";

export function Footer() {
  return (
    <footer className="footer">
      <div>
        <strong>CineTrope</strong> · Ontologia OWL, regole SWRL, SPARQL e provenienza su named graph.
      </div>
      <div>
        Dati e immagini da TMDB. Questo prodotto usa l&apos;API TMDB ma non è approvato né
        certificato da TMDB.
      </div>
      <div>
        <Link href="/queries">Competency questions</Link> · <Link href="/sources">Provenienza</Link>
      </div>
    </footer>
  );
}
