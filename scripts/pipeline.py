"""Entry point unico della pipeline dati: fetch, validazione TBox, ETL, reasoning e store.

Ogni sottocomando è un passo; i passi già completati vengono saltati (usa --force per rifarli).

    pipeline.py all                       # fetch + validate + store, saltando quello che c'è già
    pipeline.py fetch --discover-pages 25 # tmdb + images + birthdates
    pipeline.py tmdb --title Inception    # un solo passo, con i suoi parametri
    pipeline.py store --force             # ricostruisce lo store anche se aggiornato

Passi: tmdb, images, birthdates (fetch di rete), validate (TBox), dataset (solo ETL),
       store (ETL + OWL RL + SWRL + validazione). Log anche in data/generated/pipeline.log.
"""

from __future__ import annotations

import argparse
import json
import logging
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

from rdflib import OWL, RDF, RDFS, BNode, Graph, Literal, URIRef
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cinetrope.config import (  # noqa: E402
    CT,
    FILMS_PATH,
    GENERATED_DIR,
    IMAGES_PATH,
    ONTOLOGY_DIR,
    QUERY_DIR,
    RAW_DIR,
    SCHEMA_DIR,
    STORE_PATH,
    TMDB_PATH,
)

log = logging.getLogger("pipeline")
BIRTHDATES_PATH = RAW_DIR / "dbpedia_birthdates.json"


# ======================================================================
# TMDB: catalogo (ex import_tmdb.py)
# ======================================================================
def cmd_tmdb(args: argparse.Namespace) -> bool:
    from cinetrope.tmdb import (
        _request,
        fetch_movie,
        is_complete,
        require_api_key,
        write_records,
    )

    explicit = bool(args.title)
    if TMDB_PATH.exists() and not args.force and not explicit:
        count = len(json.loads(TMDB_PATH.read_text(encoding="utf-8")))
        log.info(
            "tmdb: salto, %s esiste già (%d film). Usa --force per reimportare.",
            TMDB_PATH.name,
            count,
        )
        return True
    if not explicit and not args.discover_pages:
        log.info("tmdb: nessun --title né --discover-pages, niente da importare.")
        return True

    api_key = require_api_key()
    existing = (
        json.loads(FILMS_PATH.read_text(encoding="utf-8"))
        if FILMS_PATH.exists()
        else []
    )
    previous = (
        json.loads(TMDB_PATH.read_text(encoding="utf-8")) if TMDB_PATH.exists() else []
    )
    existing_tmdb = previous or [f for f in existing if f.get("tmdb_id") is not None]
    log.info(
        "tmdb: %d film già noti, target %d, %d pagine da esplorare",
        len(existing_tmdb),
        args.target,
        args.discover_pages,
    )

    unique: dict[str, dict] = {}
    excluded: list[str] = []
    failed: list[str] = []

    def add(record: dict) -> None:
        if record.get("tmdb_id") is None:
            return
        if not is_complete(record):  # senza regista o anno fallirebbe la validazione
            excluded.append(str(record.get("title", record["tmdb_id"])))
            return
        record["id"] = f"TMDB{record['tmdb_id']}"
        unique[str(record["tmdb_id"])] = record

    for record in existing_tmdb:
        add(record)

    titles = [] if args.skip_existing else [f["title"] for f in existing_tmdb]
    titles.extend(args.title or [])
    for title in tqdm(
        list(dict.fromkeys(titles)), desc="TMDB: aggiorno i film noti", unit="film"
    ):
        try:
            add(fetch_movie(title, api_key))
        except Exception as exc:
            failed.append(title)
            log.warning("tmdb: %r non aggiornato (%s)", title, exc)

    if args.discover_pages:
        bar = tqdm(
            total=args.target,
            initial=min(len(unique), args.target),
            desc="TMDB: scopro nuovi film",
            unit="film",
        )
        for page in range(args.start_page, args.start_page + args.discover_pages):
            if len(unique) >= args.target:
                break
            bar.set_postfix(pagina=page)
            results = _request(
                "/discover/movie",
                api_key,
                language="it-IT",
                sort_by="popularity.desc",
                page=page,
            )["results"]
            for movie in results:
                if len(unique) >= args.target:
                    break
                before = len(unique)
                try:
                    add(fetch_movie(movie["title"], api_key))
                except Exception as exc:
                    failed.append(movie["title"])
                    log.warning("tmdb: %r saltato (%s)", movie["title"], exc)
                bar.update(len(unique) - before)
        bar.close()

    unique = dict(list(unique.items())[: args.target])
    TMDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_records(TMDB_PATH, list(unique.values()))
    series = [f for f in existing if f.get("type") == "SerieTV"]
    FILMS_PATH.write_text(
        json.dumps(list(unique.values()) + series, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    log.info(
        "tmdb: scritti %d film in %s e %s", len(unique), TMDB_PATH, FILMS_PATH.name
    )
    if excluded:
        log.warning(
            "tmdb: esclusi %d film senza regista o anno: %s",
            len(excluded),
            ", ".join(excluded),
        )
    if failed:
        log.warning("tmdb: %d richieste fallite (rilancia per riprovare)", len(failed))
    return True


# ======================================================================
# TMDB: immagini (ex fetch_images.py)
# ======================================================================
def _fetch_images_for(tmdb_id: int, api_key: str) -> dict:
    from cinetrope.tmdb import _request

    details = _request(
        f"/movie/{tmdb_id}", api_key, language="en-US", append_to_response="credits"
    )
    credits = details.get("credits", {})
    people = [p for p in credits.get("crew", []) if p.get("job") == "Director"]
    people += credits.get("cast", [])[:10]
    return {
        "poster_path": details.get("poster_path"),
        "backdrop_path": details.get("backdrop_path"),
        "profiles": {
            p["name"]: p["profile_path"] for p in people if p.get("profile_path")
        },
    }


def cmd_images(args: argparse.Namespace) -> bool:
    from cinetrope.tmdb import require_api_key

    if not FILMS_PATH.exists():
        log.error("images: manca %s, esegui prima il passo tmdb.", FILMS_PATH)
        return False
    films = json.loads(FILMS_PATH.read_text(encoding="utf-8"))
    images = (
        json.loads(IMAGES_PATH.read_text(encoding="utf-8"))
        if IMAGES_PATH.exists() and not args.force
        else {}
    )
    todo = [
        f["tmdb_id"]
        for f in films
        if f.get("tmdb_id") and str(f["tmdb_id"]) not in images
    ]
    if args.limit:
        todo = todo[: args.limit]
    if not todo:
        log.info(
            "images: salto, tutti i %d film hanno già le immagini. Usa --force per rifarle.",
            len(images),
        )
        return True
    log.info("images: %d film da scaricare (%d già presenti)", len(todo), len(images))
    api_key = require_api_key()

    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(_fetch_images_for, tmdb_id, api_key): tmdb_id
            for tmdb_id in todo
        }
        for future in tqdm(
            as_completed(futures),
            total=len(futures),
            desc="TMDB: poster e foto",
            unit="film",
        ):
            tmdb_id = futures[future]
            try:
                images[str(tmdb_id)] = future.result()
            except Exception as exc:  # rete o 404: si riprova alla prossima esecuzione
                failed.append((tmdb_id, str(exc)))

    IMAGES_PATH.write_text(
        json.dumps(images, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    with_poster = sum(1 for v in images.values() if v.get("poster_path"))
    log.info(
        "images: scritto %s (%d film, %d con poster)",
        IMAGES_PATH.name,
        len(images),
        with_poster,
    )
    if failed:
        log.warning(
            "images: %d falliti, rilancia per riprovare: %s", len(failed), failed[:5]
        )
    return not failed


# ======================================================================
# DBpedia: date di nascita (ex enrich_birthdates.py)
# ======================================================================
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


def _birthdates_chunk(chunk: list[str]) -> dict[str, dict]:
    query = (QUERY_DIR / "enrich_birthdates_service.rq").read_text(encoding="utf-8")
    query = query.replace(
        "{{VALUES}}", " ".join(f"<{dbpedia_iri(name)}>" for name in chunk)
    )
    result = Graph().query(query)
    iri_to_name = {str(dbpedia_iri(name)): name for name in chunk}
    found: dict[str, dict] = {}
    for person, birth_date in [] if isinstance(result, bool) else list(result):
        name = iri_to_name.get(str(person))
        date = _iso_date(birth_date)
        if name and date:
            found.setdefault(
                name, {"birthDate": date, "source": "DBpedia", "dbpedia": str(person)}
            )
    return found


def cmd_birthdates(args: argparse.Namespace) -> bool:
    output: Path = args.output
    if output.exists() and not args.force:
        count = len(json.loads(output.read_text(encoding="utf-8")))
        log.info(
            "birthdates: salto, %s esiste già (%d registi). Usa --force per rifare la query.",
            output.name,
            count,
        )
        return True
    if not FILMS_PATH.exists():
        log.error("birthdates: manca %s, esegui prima il passo tmdb.", FILMS_PATH)
        return False

    films = json.loads(FILMS_PATH.read_text(encoding="utf-8"))
    directors = sorted({n for f in films for n in f.get("directors", [])})
    chunks = [
        directors[i : i + args.chunk] for i in range(0, len(directors), args.chunk)
    ]
    log.info(
        "birthdates: %d registi in %d richieste a DBpedia (timeout %ds ciascuna)",
        len(directors),
        len(chunks),
        args.timeout,
    )

    enriched: dict[str, dict] = (
        json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    )
    socket.setdefaulttimeout(args.timeout)  # rdflib non espone un timeout per SERVICE
    failed_chunks = succeeded = 0
    for chunk in tqdm(chunks, desc="DBpedia: date di nascita", unit="richiesta"):
        try:
            enriched.update(_birthdates_chunk(chunk))
            succeeded += 1
        except Exception as exc:
            failed_chunks += 1
            log.warning(
                "birthdates: richiesta fallita (%s: %s)", type(exc).__name__, exc
            )
            if not succeeded and failed_chunks >= 2:  # endpoint giù: inutile insistere
                break

    if not succeeded:
        log.error(
            "birthdates: DBpedia non raggiungibile, nessun file scritto. "
            "L'ETL userà le date già presenti in people.json."
        )
        return False
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(enriched, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    missing = sorted(set(directors) - set(enriched))
    log.info(
        "birthdates: date per %d/%d registi, scritto %s",
        len(enriched),
        len(directors),
        output.name,
    )
    if missing:
        log.info("birthdates: non trovate per %d registi", len(missing))
    if failed_chunks:
        log.warning(
            "birthdates: %d richieste su %d fallite, rilancia con --force",
            failed_chunks,
            len(chunks),
        )
    return not failed_chunks


# ======================================================================
# Validazione statica della TBox (ex validate_tbox.py)
# ======================================================================
def load_tbox() -> Graph:
    graph = Graph()
    graph.parse(ONTOLOGY_DIR / "cinetrope.ttl", format="turtle")
    for module in sorted(SCHEMA_DIR.glob("*.ttl")):
        graph.parse(module, format="turtle")
    return graph


def _ct(term) -> bool:
    return isinstance(term, URIRef) and str(term).startswith(str(CT))


def check(graph: Graph) -> dict[str, list[str]]:
    classes = {s for s in graph.subjects(RDF.type, OWL.Class) if _ct(s)}
    props = {
        s
        for t in (OWL.ObjectProperty, OWL.DatatypeProperty)
        for s in graph.subjects(RDF.type, t)
        if _ct(s)
    }
    problems: dict[str, list[str]] = {
        "label_it_missing": [],
        "label_en_missing": [],
        "comment_missing_on_defined": [],
        "missing_domain_or_range": [],
        "inverse_not_reciprocal": [],
        "dangling_reference": [],
        "subclass_cycle": [],
    }
    for term in classes | props:
        langs = {lit.language for lit in graph.objects(term, RDFS.label)}
        if "it" not in langs:
            problems["label_it_missing"].append(str(term))
        if "en" not in langs:
            problems["label_en_missing"].append(str(term))
    for cls in classes:
        if (cls, OWL.equivalentClass, None) in graph and not any(
            isinstance(o, BNode) for o in graph.objects(cls, OWL.equivalentClass)
        ):
            continue
        if (
            any(isinstance(o, BNode) for o in graph.objects(cls, OWL.equivalentClass))
            and (cls, RDFS.comment, None) not in graph
        ):
            problems["comment_missing_on_defined"].append(str(cls))
    for prop in props:
        if (prop, RDFS.domain, None) not in graph or (
            prop,
            RDFS.range,
            None,
        ) not in graph:
            if not (
                (prop, OWL.equivalentProperty, None) in graph
                and (prop, RDFS.domain, None) in graph
            ) and prop not in (CT.name, CT.tmdbId, CT.imdbId, CT.isoCode):
                problems["missing_domain_or_range"].append(str(prop))
        for inv in graph.objects(prop, OWL.inverseOf):
            if (inv, OWL.inverseOf, prop) not in graph and (
                prop,
                OWL.inverseOf,
                inv,
            ) not in graph:
                problems["inverse_not_reciprocal"].append(f"{prop} / {inv}")
    declared = (
        classes
        | props
        | set(graph.subjects(RDF.type, CT.Fonte))
        | set(graph.subjects(RDF.type, CT.Paese))
    )
    for predicate in (RDFS.domain, RDFS.range):
        for _, _, o in graph.triples((None, predicate, None)):
            if _ct(o) and o not in declared:
                problems["dangling_reference"].append(str(o))
    for cls in classes:
        seen, stack = set(), list(graph.objects(cls, RDFS.subClassOf))
        while stack:
            node = stack.pop()
            if node == cls:
                problems["subclass_cycle"].append(str(cls))
                break
            if node in seen or isinstance(node, BNode):
                continue
            seen.add(node)
            stack.extend(graph.objects(node, RDFS.subClassOf))
    return problems


def cmd_validate(args: argparse.Namespace) -> bool:
    log.info("validate: carico la TBox da %s", SCHEMA_DIR)
    problems = check(load_tbox())
    for name, items in problems.items():
        (log.info if not items else log.warning)(
            "validate: %s %s: %d", "OK" if not items else "KO", name, len(items)
        )
        for item in sorted(set(items))[:10]:
            log.warning("validate:     %s", item)
    return not any(problems.values())


# ======================================================================
# ETL / reasoning / store (ex build_dataset.py e build_store.py)
# ======================================================================
def _inputs_mtime() -> float:
    """Ultima modifica di dati, ontologia, query e codice che alimentano lo store."""
    paths = [*RAW_DIR.glob("*.json"), *ONTOLOGY_DIR.rglob("*"), *QUERY_DIR.rglob("*")]
    paths += (ROOT / "cinetrope").glob("*.py")
    return max((p.stat().st_mtime for p in paths if p.is_file()), default=0.0)


def cmd_dataset(args: argparse.Namespace) -> bool:
    from cinetrope.etl import build_catalog, dataset_stats

    log.info("dataset: ETL dei JSON in named graph (senza inferenza)")
    started = time.time()
    stats = dataset_stats(build_catalog(write=True))
    log.info("dataset: fatto in %.0fs, scritto catalog.trig", time.time() - started)
    for key, value in stats.items():
        log.info("dataset:   %s = %s", key, value)
    return True


def cmd_store(args: argparse.Namespace) -> bool:
    from cinetrope.store import CineTropeStore

    if STORE_PATH.exists() and not args.force:
        if STORE_PATH.stat().st_mtime >= _inputs_mtime():
            log.info(
                "store: salto, %s è più recente di dati, ontologia, query e codice. "
                "Usa --force per ricostruirlo.",
                STORE_PATH.name,
            )
            return True
        log.info("store: dati o ontologia modificati dopo l'ultima build, ricostruisco")
    log.info("store: ETL, OWL RL, SWRL e validazione (circa 3 minuti)")
    started = time.time()
    store = CineTropeStore.rebuild()
    log.info("store: costruito in %.0fs, scritto %s", time.time() - started, STORE_PATH)
    for key, value in store.stats().items():
        log.info("store:   %s = %s", key, value)
    for check_ in store.build_report().get("validation", []):
        (log.info if not check_["count"] else log.warning)(
            "store: validazione %s: %d", check_["label"], check_["count"]
        )
    return True


# ======================================================================
# Gruppi di passi e CLI
# ======================================================================
def cmd_fetch(args: argparse.Namespace) -> bool:
    results = [cmd_tmdb(args), cmd_images(args), cmd_birthdates(args)]
    return all(results)


def cmd_all(args: argparse.Namespace) -> bool:
    ok = True
    for step in (cmd_fetch, cmd_validate, cmd_store):
        # I fallimenti di rete o i warning della TBox non bloccano la build dello store.
        ok &= step(args)
    return ok


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--force",
        action="store_true",
        help="Rifà il passo anche se i dati ci sono già.",
    )
    common.add_argument("-v", "--verbose", action="store_true", help="Log di debug.")

    tmdb = argparse.ArgumentParser(add_help=False)
    group = tmdb.add_argument_group("tmdb")
    group.add_argument("--title", action="append", help="Film da cercare; ripetibile.")
    group.add_argument(
        "--discover-pages",
        type=int,
        default=25,
        help="Pagine TMDB da esplorare (default 25).",
    )
    group.add_argument("--start-page", type=int, default=1, help="Prima pagina TMDB.")
    group.add_argument(
        "--target", type=int, default=500, help="Numero massimo di film (default 500)."
    )
    group.add_argument(
        "--skip-existing",
        action="store_true",
        help="Non riaggiorna i film già nel catalogo.",
    )

    images = argparse.ArgumentParser(add_help=False)
    group = images.add_argument_group("images")
    group.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Massimo di film di cui scaricare le immagini.",
    )
    group.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Richieste TMDB in parallelo (default 8).",
    )

    birth = argparse.ArgumentParser(add_help=False)
    group = birth.add_argument_group("birthdates")
    group.add_argument(
        "--output", type=Path, default=BIRTHDATES_PATH, help="File JSON materializzato."
    )
    group.add_argument(
        "--chunk",
        type=int,
        default=25,
        help="Registi per richiesta a DBpedia (default 25).",
    )
    group.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in secondi per richiesta (default 30).",
    )

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="passo")
    steps = [
        (
            "tmdb",
            cmd_tmdb,
            [common, tmdb],
            "Catalogo, keyword e cast da TMDB (serve TMDB_API_KEY)",
        ),
        (
            "images",
            cmd_images,
            [common, images],
            "Poster, sfondi e foto da TMDB (serve TMDB_API_KEY)",
        ),
        (
            "birthdates",
            cmd_birthdates,
            [common, birth],
            "Date di nascita dei registi da DBpedia",
        ),
        (
            "fetch",
            cmd_fetch,
            [common, tmdb, images, birth],
            "tmdb + images + birthdates",
        ),
        ("validate", cmd_validate, [common], "Controlli statici sulla TBox"),
        ("dataset", cmd_dataset, [common], "Solo ETL: catalog.trig senza inferenza"),
        ("store", cmd_store, [common], "ETL + OWL RL + SWRL + validazione: store.trig"),
        ("all", cmd_all, [common, tmdb, images, birth], "fetch + validate + store"),
    ]
    for name, func, parents, help_text in steps:
        sub.add_parser(
            name, parents=parents, help=help_text, description=help_text
        ).set_defaults(func=func)
    return parser


def setup_logging(verbose: bool) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S"
    )
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logfile = logging.FileHandler(GENERATED_DIR / "pipeline.log", encoding="utf-8")
    logfile.setFormatter(fmt)
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO, handlers=[console, logfile]
    )


def main() -> int:
    args = build_parser().parse_args()
    setup_logging(args.verbose)
    log.info("passo: %s%s", args.command, " (--force)" if args.force else "")
    started = time.time()
    with logging_redirect_tqdm():
        try:
            ok = args.func(args)
        except KeyboardInterrupt:
            log.error("interrotto dall'utente")
            return 130
        except Exception:
            log.exception("passo %s fallito", args.command)
            return 1
    log.info(
        "passo %s %s in %.0fs",
        args.command,
        "completato" if ok else "terminato con avvisi",
        time.time() - started,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
