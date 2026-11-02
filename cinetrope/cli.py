from __future__ import annotations

import argparse
import json
import sys

from .queries import COMPETENCY_QUESTIONS
from .store import CineTropeStore


def _print_table(rows: list[dict], columns: list[str]) -> None:
    if not rows:
        print("Nessun risultato.")
        return
    widths = {
        column: max(len(column), *(len(str(row.get(column, ""))) for row in rows))
        for column in columns
    }
    header = "  ".join(column.ljust(widths[column]) for column in columns)
    print(header)
    print("  ".join("-" * widths[column] for column in columns))
    for row in rows:
        print("  ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns))


def _cmd_list(store: CineTropeStore) -> None:
    films = store.films()
    print(f"{len(films)} film nel catalogo\n")
    for film in films:
        year = film.get("year") or "----"
        directors = film.get("directors") or "regia n.d."
        print(f"{film['title']} ({year}) · {film['film']} · {film.get('tropeCount', 0)} tropi · {directors}")


def _cmd_recommend(store: CineTropeStore, seed: str, limit: int, as_json: bool) -> None:
    film = store.film(seed)
    if film is None:
        raise SystemExit(f"Film non trovato: {seed}")
    recommendations = store.recommendations(seed, limit=limit)
    if as_json:
        print(json.dumps({"seed": film, "recommendations": recommendations}, indent=2, ensure_ascii=False))
        return
    print(f"\n{film['title']} ({film.get('year') or '----'})")
    print(f"Regia: {', '.join(item['label'] for item in film['directors']) or 'n.d.'}")
    print(f"Tropi: {', '.join(item['label'] for item in film['tropes']) or 'n.d.'}\n")
    for index, rec in enumerate(recommendations, 1):
        print(f"{index}. {rec['title']} ({rec.get('year') or '----'}) — {rec['score']} punti")
        if rec["shared_tropes"]:
            print(f"   Tropi: {', '.join(item['label'] for item in rec['shared_tropes'])}")
        if rec["shared_directors"]:
            print(f"   Regia: {', '.join(item['label'] for item in rec['shared_directors'])}")
        if rec["shared_actors"]:
            print(f"   Cast: {', '.join(item['label'] for item in rec['shared_actors'][:5])}")
        if rec["shared_genres"]:
            print(f"   Generi: {', '.join(item['label'] for item in rec['shared_genres'])}")
        if rec["source_summary"]:
            sources = ", ".join(f"{name} ({count})" for name, count in rec["source_summary"].items())
            print(f"   Fonti: {sources}")
        print(f"   Grafo: /explanation/{seed}/{rec['id']}")


def _cmd_explain(store: CineTropeStore, seed: str, rec: str, as_json: bool) -> None:
    if store.film(seed) is None or store.film(rec) is None:
        raise SystemExit("Film non trovato nel catalogo.")
    explanation = store.explanation(seed, rec)
    if as_json:
        print(json.dumps(explanation, indent=2, ensure_ascii=False))
        return
    print(f"\n{seed} -> {rec}")
    print(f"{explanation['node_count']} nodi, {explanation['edge_count']} archi, {explanation['triple_count']} triple")
    if explanation["recommendation_is_mindbender"]:
        print("La raccomandazione è un MindBender inferito dalle regole SWRL.")
    print("\nArchi:")
    for edge in explanation["edges"]:
        print(f"  {edge['from']} --{edge['label']}--> {edge['to']}")
    print("\nTriple:")
    for triple in explanation["triples"]:
        print(f"  {triple['subject']} {triple['predicate']} {triple['object']}")


def _cmd_cq(store: CineTropeStore, cq_id: str | None, as_json: bool) -> None:
    questions = store.competency_questions()
    if cq_id:
        questions = [cq for cq in questions if cq["id"].lower() == cq_id.lower()]
        if not questions:
            available = ", ".join(cq["id"] for cq in COMPETENCY_QUESTIONS)
            raise SystemExit(f"Competency question sconosciuta: {cq_id}. Disponibili: {available}")
    if as_json:
        print(json.dumps(questions, indent=2, ensure_ascii=False))
        return
    for cq in questions:
        print(f"\n[{cq['id'].upper()}] {cq['title']} — {cq['question']}")
        if cq["error"]:
            print(f"Errore: {cq['error']}")
            continue
        _print_table(cq["rows"], cq["columns"])
        print(f"{len(cq['rows'])} righe")


def _cmd_stats(store: CineTropeStore, as_json: bool) -> None:
    stats = store.stats()
    if as_json:
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return
    for key in ("films", "series", "people", "tropes", "genres", "sources", "triples", "named_graphs", "inferred_triples", "mindbenders", "frequent_collaborator_pairs"):
        print(f"{key}: {stats.get(key)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cinetrope",
        description="CineTrope: recommender semantico spiegabile per film.",
    )
    parser.add_argument("--rebuild", action="store_true", help="Ricostruisce il triple store prima del comando.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("build", help="Costruisce ETL, inferenze e report di validazione.")
    subparsers.add_parser("list", help="Elenca i film del catalogo.")
    stats = subparsers.add_parser("stats", help="Mostra le statistiche del knowledge graph.")
    stats.add_argument("--json", action="store_true", help="Output JSON.")

    recommend = subparsers.add_parser("recommend", help="Mostra cinque raccomandazioni per un film.")
    recommend.add_argument("seed", help="ID locale del film, ad esempio Inception.")
    recommend.add_argument("--limit", type=int, default=5, help="Numero di raccomandazioni (default 5).")
    recommend.add_argument("--json", action="store_true", help="Output JSON.")

    explain = subparsers.add_parser("explain", help="Mostra il grafo di spiegazione tra due film.")
    explain.add_argument("seed", help="ID del film di partenza.")
    explain.add_argument("rec", help="ID del film raccomandato.")
    explain.add_argument("--json", action="store_true", help="Output JSON.")

    cq = subparsers.add_parser("cq", help="Esegue tutte le competency questions o una sola.")
    cq.add_argument("cq_id", nargs="?", help="ID della competency question, ad esempio cq1.")
    cq.add_argument("--json", action="store_true", help="Output JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "build":
        store = CineTropeStore.rebuild()
        print(json.dumps(store.stats(), indent=2, ensure_ascii=False))
        return 0

    store = CineTropeStore.load_or_build(rebuild=args.rebuild)

    if args.command == "list":
        _cmd_list(store)
    elif args.command == "recommend":
        _cmd_recommend(store, args.seed, args.limit, args.json)
    elif args.command == "explain":
        _cmd_explain(store, args.seed, args.rec, args.json)
    elif args.command == "cq":
        _cmd_cq(store, args.cq_id, args.json)
    elif args.command == "stats":
        _cmd_stats(store, getattr(args, "json", False))
    else:  # pragma: no cover - argparse impedisce questo ramo
        parser.error(f"Comando sconosciuto: {args.command}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
