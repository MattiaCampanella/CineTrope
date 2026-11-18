// Chiamate server-side verso il backend semantico (FastAPI). Il browser usa invece
// il rewrite /api/* di next.config.mjs. Nessuna cache di Next: il backend ha già le sue
// (lru) e così un errore momentaneo non resta congelato in una pagina prerenderizzata.
const BASE = process.env.CINETROPE_API ?? "http://127.0.0.1:8000";

export async function api<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export const PRIORITIES: Record<string, string> = {
  balanced: "Bilanciata",
  cast: "Priorità cast",
  director: "Priorità regia",
  tropes: "Priorità tropi",
  genres: "Priorità generi",
};
