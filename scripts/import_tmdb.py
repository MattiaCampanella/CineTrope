"""Importa il catalogo TMDB e sostituisce le annotazioni manuali."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cinetrope.config import FILMS_PATH, TMDB_PATH
from cinetrope.tmdb import fetch_discover, fetch_movie, require_api_key, write_records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", action="append", help="Film da cercare; ripetibile.")
    parser.add_argument("--discover-pages", type=int, default=0, help="Pagine TMDB da importare.")
    parser.add_argument("--start-page", type=int, default=1, help="Prima pagina TMDB da importare.")
    parser.add_argument("--target", type=int, default=500, help="Numero massimo di film TMDB da mantenere.")
    parser.add_argument("--skip-existing", action="store_true", help="Non reimportare i titoli già in films.json.")
    args = parser.parse_args()

    if not args.title and not args.discover_pages:
        parser.error("specifica almeno --title o --discover-pages")

    api_key = require_api_key()
    existing = json.loads(FILMS_PATH.read_text(encoding="utf-8"))
    previous = json.loads(TMDB_PATH.read_text(encoding="utf-8")) if TMDB_PATH.exists() else []
    existing_tmdb = previous or [film for film in existing if film.get("tmdb_id") is not None]
    titles = [] if args.skip_existing else [
        film["title"] for film in existing_tmdb
    ]
    titles.extend(args.title or [])
    unique = {}
    for record in existing_tmdb:
        if record.get("tmdb_id") is not None:
            record["id"] = f"TMDB{record['tmdb_id']}"
            unique[str(record["tmdb_id"])] = record
    records = [fetch_movie(title, api_key) for title in dict.fromkeys(titles)]
    for record in records:
        if record.get("tmdb_id") is not None:
            record["id"] = f"TMDB{record['tmdb_id']}"
            unique[str(record["tmdb_id"])] = record
    if args.discover_pages:
        for page in range(args.start_page, args.start_page + args.discover_pages):
            if len(unique) >= args.target:
                break
            for record in fetch_discover(api_key, pages=1, start_page=page):
                if record.get("tmdb_id") is not None:
                    record["id"] = f"TMDB{record['tmdb_id']}"
                    unique[str(record["tmdb_id"])] = record
                    if len(unique) >= args.target:
                        break
    unique = dict(list(unique.items())[:args.target])
    TMDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_records(TMDB_PATH, list(unique.values()))
    series = [film for film in existing if film.get("type") == "SerieTV"]
    sanitized = list(unique.values()) + series
    FILMS_PATH.write_text(json.dumps(sanitized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Scritti {len(unique)} film TMDB in {TMDB_PATH}")


if __name__ == "__main__":
    main()
