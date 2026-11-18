"use client";
import { useState } from "react";

type Meta = { id: string; title: string; question: string; note: string };
type Result = { columns: string[]; rows: Record<string, unknown>[]; query_text: string; error: string | null };

export function QueryList({ items }: { items: Meta[] }) {
  const [open, setOpen] = useState<string | null>(null);
  const [cache, setCache] = useState<Record<string, Result | "loading">>({});

  async function toggle(id: string) {
    setOpen(open === id ? null : id);
    if (open === id || cache[id]) return;
    setCache((c) => ({ ...c, [id]: "loading" }));
    const res = await fetch(`/api/queries/${id}`);
    const data = (await res.json()) as Result;
    setCache((c) => ({ ...c, [id]: data }));
  }

  return (
    <div className="acc">
      {items.map((cq) => {
        const result = cache[cq.id];
        return (
          <div key={cq.id} className="acc-item">
            <button onClick={() => toggle(cq.id)} aria-expanded={open === cq.id}>
              <span>
                <span className="acc-id">{cq.id.toUpperCase()}</span>
                <h3 style={{ fontSize: "1.15rem", marginTop: 4 }}>{cq.title}</h3>
                <p className="empty-inline" style={{ marginTop: 4 }}>{cq.question}</p>
              </span>
              <span aria-hidden="true">{open === cq.id ? "−" : "+"}</span>
            </button>
            {open === cq.id && (
              <div className="acc-body">
                <p style={{ color: "var(--ink-2)" }}>{cq.note}</p>
                {result === "loading" || !result ? (
                  <div className="skeleton" style={{ height: 120 }} />
                ) : result.error ? (
                  <pre>{result.error}</pre>
                ) : (
                  <>
                    <div className="table-wrap">
                      <table>
                        <thead><tr>{result.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                        <tbody>
                          {result.rows.length === 0 && (
                            <tr><td colSpan={result.columns.length || 1}>Nessun risultato (alcune CQ richiedono il reimport TMDB).</td></tr>
                          )}
                          {result.rows.map((row, i) => (
                            <tr key={i}>{result.columns.map((c) => <td key={c}>{String(row[c] ?? "")}</td>)}</tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <details>
                      <summary style={{ cursor: "pointer", color: "var(--ink-2)", marginBottom: 10 }}>Query SPARQL</summary>
                      <pre>{result.query_text}</pre>
                    </details>
                  </>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
