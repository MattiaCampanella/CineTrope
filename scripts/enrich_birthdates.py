"""Arricchisce i registi locali con le date di nascita da DBpedia via SERVICE."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

from rdflib import Graph, Literal, URIRef

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cinetrope.config import QUERY_DIR, RAW_DIR  # noqa: E402


def dbpedia_iri(name: str) -> URIRef:
    resource = quote(name.replace(" ", "_"), safe="-_.~")
    return URIRef(f"http://dbpedia.org/resource/{resource}")


def _iso_date(value: object) -> str | None:
    if not isinstance(value, Literal):
        return None
    text = str(value).strip()
    parts = text.split("-")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    return text


def fetch(directors: list[str]) -> tuple[dict[str, dict], list[str]]:
    query = (QUERY_DIR / "enrich_birthdates_service.rq").read_text(encoding="utf-8")
    values = " ".join(f"<{dbpedia_iri(name)}>" for name in directors)
    query = query.replace("{{VALUES}}", values)

    result = Graph().query(query)
    rows: list[Any] = [] if isinstance(result, bool) else list(result)
    iri_to_name = {str(dbpedia_iri(name)): name for name in directors}
    enriched: dict[str, dict] = {}
    for row in rows:
        person = row[0]
        birth_date = row[1]
        name = iri_to_name.get(str(person))
        date = _iso_date(birth_date)
        if name is None or date is None:
            continue
        enriched.setdefault(
            name,
            {
                "birthDate": date,
                "source": "DBpedia",
                "dbpedia": str(person),
            },
        )
    missing = sorted(set(directors) - set(enriched))
    return enriched, missing


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=RAW_DIR / "dbpedia_birthdates.json",
        help="File JSON materializzato (default: data/raw/dbpedia_birthdates.json).",
    )
    args = parser.parse_args()

    films = json.loads((RAW_DIR / "films.json").read_text(encoding="utf-8"))
    directors = sorted({name for film in films for name in film.get("directors", [])})
    enriched, missing = fetch(directors)
    if not enriched:
        raise SystemExit("Nessuna data trovata: il file esistente non è stato modificato.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(enriched, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    try:
        output_label = args.output.resolve().relative_to(ROOT)
    except ValueError:
        output_label = args.output
    print(f"Date trovate per {len(enriched)}/{len(directors)} registi.")
    if missing:
        print("Non trovate: " + ", ".join(missing))
    print(f"Risultato scritto in {output_label}")


if __name__ == "__main__":
    main()
