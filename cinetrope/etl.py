from __future__ import annotations

import json
import logging

from rdflib import Dataset

from .config import (
    CATALOG_PATH,
    CT,
    GENERATED_DIR,
    ONTOLOGY_DIR,
    RAW_DIR,
    SCHEMA_DIR,
    SOURCE_GRAPHS,
)
from .queries import load_query

log = logging.getLogger(__name__)


def slugify(value: str) -> str:
    """Converte un nome leggibile in un identificatore locale stabile."""
    import unicodedata

    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(ch for ch in ascii_value if ch.isalnum())
    if not cleaned:
        raise ValueError(f"Impossibile creare un identificatore da {value!r}")
    return cleaned


def ct_iri(local_name: str):
    return CT[local_name]


def normalize_genre_id(genre_id: str) -> str:
    return "ScienceFiction" if genre_id == "SciFi" else genre_id


def _read_json(name: str):
    with (RAW_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_optional_json(name: str) -> dict:
    path = RAW_DIR / name
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_ontology(dataset: Dataset) -> None:
    graph = dataset.graph(CT.Ontology)
    graph.parse(ONTOLOGY_DIR / "cinetrope.ttl", format="turtle")
    # dl-axioms.ttl resta fuori dal dataset: OWL RL ne genererebbe sameAs spuri.
    for module in sorted(SCHEMA_DIR.glob("*.ttl")):
        if module.stem != "dl-axioms":
            graph.parse(module, format="turtle")


def _add_source_facts(dataset: Dataset, genres, tropes, keywords=()) -> None:
    from rdflib import RDF, RDFS

    local = dataset.graph(CT.LocalAnalysis)
    for genre in genres:
        gid = ct_iri(normalize_genre_id(genre["id"]))
        local.add((gid, RDF.type, CT.Genere))
        local.add((gid, RDFS.label, _literal(genre["label"])))
        for parent_id in genre.get("parents", []):
            parent = ct_iri(normalize_genre_id(parent_id))
            local.add((gid, CT.subGenreOf, parent))

    for trope in tropes:
        tid = ct_iri(trope["id"])
        local.add((tid, RDF.type, CT.Tropo))
        local.add((tid, RDFS.label, _literal(trope["label"])))
        local.add((tid, RDFS.comment, _literal(trope["description"])))

    tmdb = dataset.graph(CT.TMDB)
    for keyword in keywords:
        term = ct_iri(keyword["id"])
        target_type = (
            CT.Tropo if keyword["category"] == "trope" else CT.ElementoDescrittivo
        )
        tmdb.add((term, RDF.type, target_type))
        tmdb.add((term, RDFS.label, _literal(keyword["label"])))


def _literal(text: str):
    from rdflib import Literal

    return Literal(text, lang="it")


def _add_people(
    dataset: Dataset, films, people_meta, enrichment: dict | None = None
) -> None:
    from rdflib import RDF, RDFS, Literal

    roles: dict[str, set[str]] = {}
    display_names: dict[str, str] = {}
    for film in films:
        for person in film.get("directors", []):
            local = slugify(person)
            display_names[local] = person
            roles.setdefault(local, set()).add("Regista")
        for person in film.get("cast", []):
            local = slugify(person)
            display_names[local] = person
            roles.setdefault(local, set()).add("Attore")

    profiles = {
        slugify(name): path
        for film in films
        for name, path in film.get("profiles", {}).items()
    }
    metadata_by_local = {slugify(name): data for name, data in people_meta.items()}
    enrichment_by_local = {
        slugify(name): data for name, data in (enrichment or {}).items()
    }
    catalog = dataset.graph(CT.TMDB)
    for local, name in display_names.items():
        person = ct_iri(local)
        catalog.add((person, RDF.type, CT.Persona))
        catalog.add((person, RDFS.label, _literal(name)))
        for role in roles[local]:
            catalog.add((person, RDF.type, ct_iri(role)))
        if local in profiles:
            catalog.add((person, CT.profilePath, Literal(profiles[local])))

        metadata = dict(metadata_by_local.get(local, {}))
        enriched = enrichment_by_local.get(local)
        if enriched and enriched.get("birthDate"):
            metadata["birthDate"] = enriched["birthDate"]
            metadata["source"] = enriched.get("source", "DBpedia")

        if metadata.get("birthDate"):
            from rdflib import XSD

            source_name = metadata.get("source", "Wikidata")
            source = SOURCE_GRAPHS.get(source_name, CT.Wikidata)
            target = dataset.graph(source)
            target.add(
                (
                    person,
                    CT.birthDate,
                    Literal(metadata["birthDate"], datatype=XSD.date),
                )
            )
            target.add((person, RDF.type, CT.Persona))
            target.add((person, RDFS.label, _literal(name)))


_NUMERIC_FIELDS = {
    "runtime": ("runtime", "integer"),
    "vote_average": ("voteAverage", "decimal"),
    "vote_count": ("voteCount", "integer"),
    "budget": ("budget", "integer"),
    "revenue": ("revenue", "integer"),
    "popularity": ("popularity", "decimal"),
    "tmdb_id": ("tmdbId", "integer"),
}
_TEXT_FIELDS = {
    "overview": "overview",
    "tagline": "tagline",
    "imdb_id": "imdbId",
    "poster_path": "posterPath",
    "backdrop_path": "backdropPath",
}


def _add_film_details(dataset: Dataset, work, film: dict) -> None:
    """Campi TMDB opzionali (assenti nei dati vecchi: vengono semplicemente saltati)."""
    from rdflib import RDF, RDFS, XSD, Literal

    tmdb = dataset.graph(CT.TMDB)
    for key, (prop, kind) in _NUMERIC_FIELDS.items():
        value = film.get(key)
        if value in (None, "", 0):
            continue
        tmdb.add((work, CT[prop], Literal(value, datatype=getattr(XSD, kind))))
    for key, prop in _TEXT_FIELDS.items():
        if film.get(key):
            tmdb.add((work, CT[prop], Literal(film[key])))
    if film.get("release_date"):
        tmdb.add(
            (work, CT.releaseDate, Literal(film["release_date"], datatype=XSD.date))
        )
    if film.get("original_language"):
        lang = ct_iri("Lang_" + film["original_language"])
        tmdb.add((lang, RDF.type, CT.Lingua))
        tmdb.add((lang, CT.isoCode, Literal(film["original_language"])))
        tmdb.add((work, CT.originalLanguage, lang))
    for country in film.get("countries", []):
        node = ct_iri("Country_" + country["iso"])
        tmdb.add((node, RDF.type, CT.Paese))
        tmdb.add((node, CT.isoCode, Literal(country["iso"])))
        if country.get("name"):
            tmdb.add((node, RDFS.label, Literal(country["name"], lang="en")))
        tmdb.add((work, CT.originCountry, node))
    for company in film.get("companies", []):
        node = ct_iri("Studio" + str(company["id"]))
        tmdb.add((node, RDF.type, CT.Studio))
        tmdb.add((node, RDFS.label, Literal(company["name"])))
        tmdb.add((work, CT.producedBy, node))
    collection = film.get("collection")
    if collection:
        node = ct_iri("Collection" + str(collection["id"]))
        tmdb.add((node, RDF.type, CT.Collezione))
        tmdb.add((node, RDFS.label, Literal(collection["name"])))
        tmdb.add((work, CT.partOfCollection, node))


def _add_films(dataset: Dataset, films) -> None:
    from rdflib import RDF, RDFS, XSD, Literal

    tmdb = dataset.graph(CT.TMDB)
    for film in films:
        work = ct_iri(film["id"])
        work_type = CT.SerieTV if film.get("type") == "SerieTV" else CT.Film
        tmdb.add((work, RDF.type, work_type))
        tmdb.add((work, RDFS.label, _literal(film["title"])))
        if film.get("year"):
            tmdb.add(
                (work, CT.releaseYear, Literal(str(film["year"]), datatype=XSD.gYear))
            )

        _add_film_details(dataset, work, film)

        for genre_id in film.get("genres", []):
            genre = ct_iri(normalize_genre_id(genre_id))
            tmdb.add((work, CT.hasGenre, genre))

        for director in film.get("directors", []):
            tmdb.add((work, CT.directedBy, ct_iri(slugify(director))))
        for actor in film.get("cast", []):
            tmdb.add((work, CT.starring, ct_iri(slugify(actor))))

        for keyword in film.get("keywords", []):
            tmdb.add((work, CT.hasTrope, ct_iri(keyword["id"])))


def _add_derived_relations(dataset: Dataset, films) -> None:
    """Calcola co-presenze, collaborazioni e collaborazioni frequenti con SPARQL."""

    derived = dataset.graph(CT.Derived)

    for query_name in ("derive_co_stars.rq", "derive_collaborations.rq"):
        result = dataset.query(load_query(query_name))
        if result.graph is not None:
            for triple in result.graph:
                derived.add(triple)

    frequent = dataset.query(load_query("detect_frequent_collaboration.rq"))
    if frequent.graph is not None:
        for triple in frequent.graph:
            derived.add(triple)

    # Le varianti simmetriche esplicite rendono leggibile il grafo anche senza reasoner.
    # coStarsWith è lasciata in una sola direzione per mostrare l'inferenza OWL.
    for p1, p2 in list(derived.subject_objects(CT.collaboratedWith)):
        derived.add((p2, CT.collaboratedWith, p1))
    for p1, p2 in list(derived.subject_objects(CT.frequentCollaboration)):
        derived.add((p2, CT.frequentCollaboration, p1))


def build_catalog(write: bool = False) -> Dataset:
    """Costruisce il dataset esplicito, separando le fonti in named graph."""
    log.info("etl: leggo i JSON in data/raw")
    films = _read_json("films.json")
    genres = _read_json("genres.json")
    tropes = _read_optional_json("tropes.json") or []
    keywords = []
    tmdb_records = _read_optional_json("tmdb.json")
    if isinstance(tmdb_records, list) and tmdb_records:
        manual_series = [film for film in films if film.get("type") == "SerieTV"]
        films_by_tmdb_id = {}
        for record in tmdb_records:
            if record.get("tmdb_id") is not None:
                record["id"] = f"TMDB{record['tmdb_id']}"
                films_by_tmdb_id[str(record["tmdb_id"])] = record
        films = list(films_by_tmdb_id.values()) + manual_series
        keywords = [keyword for film in films for keyword in film.get("keywords", [])]
        tropes = []
    if not keywords:
        # tmdb.json è gitignored: senza di esso le keyword restano comunque in films.json.
        keywords = [k for film in films for k in film.get("keywords", [])]
    people = _read_json("people.json")
    birthdates = _read_optional_json("dbpedia_birthdates.json")

    dataset = Dataset(default_union=True)
    log.info(
        "etl: carico l'ontologia e le fonti (%d film, %d keyword)",
        len(films),
        len(keywords),
    )
    _load_ontology(dataset)
    _add_source_facts(dataset, genres, tropes, keywords)
    log.info("etl: aggiungo persone e film")
    _add_people(dataset, films, people, birthdates)
    _add_films(dataset, films)
    log.info("etl: relazioni derivate con SPARQL (co-star, collaborazioni)")
    _add_derived_relations(dataset, films)

    if write:
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        dataset.serialize(destination=CATALOG_PATH, format="trig")
    return dataset


def dataset_stats(dataset: Dataset) -> dict:
    from rdflib import RDF

    films = set(dataset.subjects(RDF.type, CT.Film))
    series = set(dataset.subjects(RDF.type, CT.SerieTV))
    people = set(dataset.subjects(RDF.type, CT.Persona))
    tropes = set(dataset.subjects(RDF.type, CT.Tropo))
    genres = set(dataset.subjects(RDF.type, CT.Genere))
    sources = set(dataset.subjects(RDF.type, CT.Fonte))
    return {
        "films": len(films),
        "series": len(series),
        "people": len(people),
        "tropes": len(tropes),
        "genres": len(genres),
        "sources": len(sources),
        "triples": sum(len(dataset.graph(graph_id)) for graph_id in dataset.graphs()),
        "named_graphs": len(list(dataset.graphs())),
    }
