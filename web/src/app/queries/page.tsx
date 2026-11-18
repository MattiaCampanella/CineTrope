import { api } from "@/lib/api";
import { QueryList } from "@/components/QueryList";

export const metadata = { title: "Competency questions" };

type Meta = { id: string; title: string; question: string; note: string };

export default async function QueriesPage() {
  const list = (await api<Meta[]>("/api/queries")) ?? [];
  return (
    <>
      <section className="page-head enter">
        <span className="eyebrow">SPARQL</span>
        <h1>Competency questions</h1>
        <p>
          Le domande a cui l’ontologia deve saper rispondere. Ogni risposta è una query SPARQL eseguita sullo store: apri una
          scheda per lanciarla.
        </p>
      </section>
      <div className="container section">
        <QueryList items={list} />
      </div>
    </>
  );
}
