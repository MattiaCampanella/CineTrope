from __future__ import annotations

import json
from pathlib import Path

from rdflib import Dataset

from .config import CATALOG_PATH, CT, GENERATED_DIR, ONTOLOGY_DIR, RAW_DIR, SOURCE_GRAPHS, TMDB_PATH
from .queries import load_query, render_query


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


def _add_source_facts(dataset: Dataset, genres, tropes, keywords=()) -> None:
    from rdflib import OWL, RDF, RDFS

    graph = dataset.graph(CT.LocalAnalysis)
    for genre in genres:
        gid = ct_iri(genre["id"])
        graph.add((gid, RDF.type, OWL.Class))
        graph.add((gid, RDF.type, CT.Genere))
        graph.add((gid, RDFS.label, _literal(genre["label"])))
        for parent_id in genre.get("parents", []):
            parent = ct_iri(parent_id)
            graph.add((gid, RDFS.subClassOf, parent))
            graph.add((gid, CT.subGenreOf, parent))
        if genre.get("equivalentTo"):
            graph.add((gid, OWL.equivalentClass, ct_iri(genre["equivalentTo"])))

    for trope in tropes:
        tid = ct_iri(trope["id"])
        graph.add((tid, RDF.type, CT.Tropo))
        graph.add((tid, RDFS.label, _literal(trope["label"])))
        graph.add((tid, RDFS.comment, _literal(trope["description"])))

    for keyword in keywords:
        term = ct_iri(keyword["id"])
        target_type = CT.Tropo if keyword["category"] == "trope" else CT.ElementoDescrittivo
        graph.add((term, RDF.type, target_type))
        graph.add((term, RDFS.label, _literal(keyword["label"])))


def _literal(text: str):
    from rdflib import Literal

    return Literal(text, lang="it")


def _add_people(dataset: Dataset, films, people_meta, enrichment: dict | None = None) -> None:
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

    metadata_by_local = {slugify(name): data for name, data in people_meta.items()}
    enrichment_by_local = {slugify(name): data for name, data in (enrichment or {}).items()}
    catalog = dataset.graph(CT.Wikidata)
    for local, name in display_names.items():
        person = ct_iri(local)
        catalog.add((person, RDF.type, CT.Persona))
        catalog.add((person, RDFS.label, _literal(name)))
        for role in roles[local]:
            catalog.add((person, RDF.type, ct_iri(role)))

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
            target.add((person, CT.birthDate, Literal(metadata["birthDate"], datatype=XSD.date)))
            target.add((person, RDF.type, CT.Persona))
            target.add((person, RDFS.label, _literal(name)))


def _add_films(dataset: Dataset, films) -> None:
    from rdflib import RDF, RDFS, Literal, XSD

    wikidata = dataset.graph(CT.Wikidata)
    for film in films:
        work = ct_iri(film["id"])
        work_type = CT.SerieTV if film.get("type") == "SerieTV" else CT.Film
        wikidata.add((work, RDF.type, work_type))
        wikidata.add((work, RDFS.label, _literal(film["title"])))
        if film.get("year"):
            wikidata.add((work, CT.releaseYear, Literal(str(film["year"]), datatype=XSD.gYear)))

        for genre_id in film.get("genres", []):
            genre = ct_iri(genre_id)
            wikidata.add((work, CT.hasGenre, genre))
            wikidata.add((work, RDF.type, genre))

        for director in film.get("directors", []):
            wikidata.add((work, CT.directedBy, ct_iri(slugify(director))))
        for actor in film.get("cast", []):
            wikidata.add((work, CT.starring, ct_iri(slugify(actor))))

        for keyword in film.get("keywords", []):
            dataset.graph(CT.TMDB).add((work, CT.hasTrope, ct_iri(keyword["id"])))


def _add_derived_relations(dataset: Dataset, films) -> None:
    """Calcola co-presenze, collaborazioni e collaborazioni frequenti con SPARQL."""
    from rdflib import Graph

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
        keywords = [
            keyword
            for film in films
            for keyword in film.get("keywords", [])
        ]
        tropes = []
    people = _read_json("people.json")
    birthdates = _read_optional_json("dbpedia_birthdates.json")

    dataset = Dataset(default_union=True)
    _load_ontology(dataset)
    _add_source_facts(dataset, genres, tropes, keywords)
    _add_people(dataset, films, people, birthdates)
    _add_films(dataset, films)
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
