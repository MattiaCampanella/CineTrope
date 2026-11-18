// Skeleton OLED mostrato durante la navigazione: la pagina risponde subito, i dati arrivano dopo.
export default function Loading() {
  return (
    <div aria-busy="true" aria-label="Caricamento">
      <div className="skeleton" style={{ height: "62vh", borderRadius: 0 }} />
      {[0, 1].map((row) => (
        <div key={row} style={{ padding: "48px var(--gutter) 0", display: "flex", gap: 14, overflow: "hidden" }}>
          {Array.from({ length: 8 }, (_, i) => (
            <div key={i} className="skeleton" style={{ flex: "0 0 auto", width: 180, aspectRatio: "2 / 3" }} />
          ))}
        </div>
      ))}
    </div>
  );
}
