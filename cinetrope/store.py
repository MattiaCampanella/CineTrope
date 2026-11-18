"""API applicativa per catalogo, raccomandazioni, spiegazioni e provenienza."""

from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from functools import lru_cache

from rdflib import RDF, RDFS, Dataset, Graph, Literal, URIRef
from tqdm import tqdm

from .config import (
    CT,
    GENERATED_DIR,
    IMAGES_PATH,
    REPORT_PATH,
    STORE_PATH,
    TMDB_IMAGE_BASE,
)
from .etl import build_catalog, dataset_stats
from .queries import COMPETENCY_QUESTIONS, render_named_query, render_query
from .reasoning import DEFINED_CLASSES, run_reasoning, validation_checks
from .search import SuggestIndex
from .search import search as search_films

GROUPS = ("tropes", "directors", "actors", "genres")
KIND_TO_GROUP = {
    "trope": "tropes",
    "director": "directors",
    "actor": "actors",
    "genre": "genres",
}

EDGE_LABELS = {
    CT.recommends: "raccomanda",
    CT.recommendedBecause: "perché",
    CT.hasTrope: "usa tropo",
    CT.hasElement: "elemento descrittivo",
    CT.directedBy: "diretto da",
    CT.starring: "interpretato da",
    CT.hasGenre: "genere",
    CT.assertedIn: "fonte",
}

SKIP_PREDICATES = {
    RDF.type,
    CT.sharesTropeWith,
    CT.sharesDirectorWith,
    CT.sharesActorWith,
    CT.sharesGenreWith,
}


log = logging.getLogger(__name__)


def image_url(path, size: str) -> str | None:
    """URL del CDN TMDB (hotlink dal browser) oppure None se il percorso manca."""
    return f"{TMDB_IMAGE_BASE}{size}{path}" if path else None


def local_name(term) -> str:
    text = str(term)
    namespace = str(CT)
    if text.startswith(namespace):
        return text[len(namespace) :]
    return text


def _json_value(term):
    if term is None:
        return None
    if isinstance(term, Literal):
        return (
            term.value if term.datatype is None and term.language is None else str(term)
        )
    if isinstance(term, URIRef):
        return local_name(term)
    return str(term)


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class CineTropeStore:
    def __init__(self, dataset: Dataset):
        self.dataset = dataset
        # Il parser SPARQL di rdflib (pyparsing) non è thread-safe: il warm-up e le
        # richieste web in parallelo ne corrompono lo stato e ogni query poi fallisce
        # con "TypeError: <lambda>() missing 1 required positional argument".
        lock = threading.RLock()
        unlocked_query = dataset.query

        def locked_query(*args, **kwargs):
            with lock:
                return unlocked_query(*args, **kwargs)

        dataset.query = locked_query

    # ------------------------------------------------------------------
    # Caricamento e costruzione
    # ------------------------------------------------------------------
    @classmethod
    def load_or_build(cls, rebuild: bool = False) -> "CineTropeStore":
        if STORE_PATH.exists() and not rebuild:
            dataset = Dataset(default_union=True)
            dataset.parse(STORE_PATH, format="trig")
            return cls(dataset)
        return cls.rebuild()

    @classmethod
    def rebuild(cls) -> "CineTropeStore":
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        log.info("store: avvio la build completa")
        steps = tqdm(total=3, desc="Store: ETL", unit="fase")
        dataset = build_catalog(write=True)
        steps.update()
        steps.set_description("Store: inferenza OWL RL + SWRL")
        reasoning_report = run_reasoning(dataset)
        steps.update()
        steps.set_description("Store: validazione")
        checks = validation_checks(dataset)
        steps.update()
        steps.close()
        report = {
            "reasoning": reasoning_report,
            "validation": checks,
            "stats": dataset_stats(dataset),
        }
        log.info("store: serializzo %s", STORE_PATH)
        dataset.serialize(destination=STORE_PATH, format="trig")
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return cls(dataset)

    def build_report(self) -> dict:
        if REPORT_PATH.exists():
            return json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        return {}

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def _execute(self, query_name: str, iri_params=None, raw_params=None):
        query = render_named_query(
            query_name, iri_params=iri_params, raw_params=raw_params
        )
        return self.dataset.query(query)

    def _dict_rows(self, result) -> list[dict]:
        columns = [str(variable) for variable in (result.vars or [])]
        rows = []
        for row in result:
            rows.append(
                {
                    column: _json_value(row[index])
                    for index, column in enumerate(columns)
                }
            )
        return rows

    def query_rows(
        self, query_name: str, iri_params=None, raw_params=None
    ) -> list[dict]:
        return self._dict_rows(
            self._execute(query_name, iri_params=iri_params, raw_params=raw_params)
        )

    def _label(self, node) -> str:
        labels = sorted(self.dataset.objects(node, RDFS.label), key=str)
        if labels:
            return str(labels[0])
        return local_name(node)

    @property
    def _images(self) -> dict:
        """Overlay di data/raw/images.json (scripts/fetch_images.py): nessun rebuild necessario."""
        if not hasattr(self, "_images_cache"):
            try:
                self._images_cache = json.loads(IMAGES_PATH.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._images_cache = {}
        return self._images_cache

    def _path(self, node, predicate, key: str):
        stored = next(self.dataset.objects(node, predicate), None)
        if stored is not None:
            return str(stored)
        tmdb_id = next(self.dataset.objects(node, CT.tmdbId), None)
        entry = self._images.get(str(tmdb_id)) if tmdb_id is not None else None
        if entry is None:  # fallback: id locale TMDB<id>
            entry = self._images.get(local_name(node).removeprefix("TMDB"))
        return entry.get(key) if entry else None

    def poster_of(self, film_id: str, size: str = "w342") -> str | None:
        return image_url(self._path(CT[film_id], CT.posterPath, "poster_path"), size)

    def _photo(self, person) -> str | None:
        name = str(self._label(person))
        for entry in self._images.values():
            path = entry.get("profiles", {}).get(name)
            if path:
                return image_url(path, "w185")
        return image_url(
            next(self.dataset.objects(person, CT.profilePath), None), "w185"
        )

    def _exists(self, subject, predicate, obj) -> bool:
        return (subject, predicate, obj) in self.dataset

    # ------------------------------------------------------------------
    # Catalogo e dettaglio film
    # ------------------------------------------------------------------
    @lru_cache(maxsize=1024)
    def films(self) -> list[dict]:
        return self.query_rows("01_films.rq")

    @lru_cache(maxsize=1024)
    def film(self, film_id: str) -> dict | None:
        iri = CT[film_id]
        if not (
            self._exists(iri, RDF.type, CT.Film)
            or self._exists(iri, RDF.type, CT.SerieTV)
        ):
            return None

        title = self._label(iri)
        year = next(self.dataset.objects(iri, CT.releaseYear), None)
        work_type = "SerieTV" if self._exists(iri, RDF.type, CT.SerieTV) else "Film"
        directors = [
            {
                "id": local_name(value),
                "label": self._label(value),
                "photo": self._photo(value),
            }
            for value in self.dataset.objects(iri, CT.directedBy)
        ]
        actors = [
            {
                "id": local_name(value),
                "label": self._label(value),
                "photo": self._photo(value),
            }
            for value in self.dataset.objects(iri, CT.starring)
        ]
        genres = [
            {"id": local_name(value), "label": self._label(value)}
            for value in self.dataset.objects(iri, CT.hasGenre)
        ]

        tropes = []
        for trope in sorted(
            set(self.dataset.objects(iri, CT.hasTrope)),
            key=lambda node: self._label(node),
        ):
            tropes.append(
                {
                    "id": local_name(trope),
                    "label": self._label(trope),
                    "sources": self._source_items("tropes", film_id, local_name(trope)),
                }
            )

        elements = []
        for element in sorted(
            set(self.dataset.objects(iri, CT.hasElement)),
            key=lambda node: self._label(node),
        ):
            elements.append(
                {
                    "id": local_name(element),
                    "label": self._label(element),
                    "sources": self.sources_for(iri, CT.hasElement, element),
                }
            )

        return {
            "id": film_id,
            "iri": str(iri),
            "title": title,
            "year": str(year) if year is not None else None,
            "type": work_type,
            "directors": _dedupe(directors),
            "actors": _dedupe(actors),
            "genres": _dedupe(genres),
            "tropes": tropes,
            "elements": elements,
            "poster": self.poster_of(film_id),
            "backdrop": image_url(
                self._path(iri, CT.backdropPath, "backdrop_path"), "w1280"
            ),
            "is_mindbender": self._exists(iri, RDF.type, CT.MindBender),
            "classes": [
                name
                for name in DEFINED_CLASSES
                if self._exists(iri, RDF.type, CT[name])
            ],
        }

    # ------------------------------------------------------------------
    # Provenienza
    # ------------------------------------------------------------------
    @lru_cache(maxsize=1024)
    def sources_for(self, subject, predicate, obj) -> list[dict]:
        query = render_query(
            """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?source ?label WHERE {
              GRAPH ?source { {{SUBJECT}} {{PREDICATE}} {{OBJECT}} }
              ?source rdfs:label ?label .
            }
            ORDER BY ?label
            """,
            iri_params={},
        )
        query = query.replace("{{SUBJECT}}", f"<{subject}>")
        query = query.replace("{{PREDICATE}}", f"<{predicate}>")
        query = query.replace("{{OBJECT}}", f"<{obj}>")
        rows = self._dict_rows(self.dataset.query(query))
        return _dedupe(
            [
                {"id": row["source"], "label": row["label"]}
                for row in rows
                if row.get("source")
            ]
        )

    @lru_cache(maxsize=1024)
    def provenance(self, film_id: str, trope_id: str) -> list[dict]:
        rows = self.query_rows(
            "05_provenance_assertion.rq",
            iri_params={"film": film_id, "trope": trope_id},
        )
        return [
            {
                "id": row.get("source"),
                "label": row.get("sourceLabel") or row.get("source"),
                "source": row.get("source"),
                "sourceLabel": row.get("sourceLabel"),
            }
            for row in rows
        ]

    @lru_cache(maxsize=1024)
    def source_stats(self) -> list[dict]:
        # Stesso risultato di 08_source_stats.rq (che impiega ~24 s su rdflib) ma con
        # un conteggio diretto per named graph: millisecondi.
        rows = []
        for graph in self.dataset.graphs():
            if (graph.identifier, RDF.type, CT.Fonte) not in self.dataset.graph(
                CT.Ontology
            ):
                continue
            label = next(self.dataset.objects(graph.identifier, RDFS.label), None)
            rows.append(
                {
                    "source": str(graph.identifier),
                    "sourceLabel": str(label) if label is not None else None,
                    "triples": len(graph),
                }
            )
        return sorted(rows, key=lambda row: -row["triples"])

    # ------------------------------------------------------------------
    # Raccomandazioni e spiegazioni
    # ------------------------------------------------------------------
    _GROUP_PREDICATES = {
        "tropes": CT.hasTrope,
        "directors": CT.directedBy,
        "actors": CT.starring,
        "genres": CT.hasGenre,
    }

    def _fast_index(self) -> dict:
        """Indici film<->valore per gruppo e fonte di ogni asserzione, costruiti una sola volta.

        Sostituiscono 03_recommendations.rq e 13_shared_details.rq nel sito: stesso punteggio
        e stesso ordinamento, ma in millisecondi invece di secondi per film.
        """
        if hasattr(self, "_fi"):
            return self._fi
        by_film = {g: {} for g in self._GROUP_PREDICATES}
        by_value = {g: {} for g in self._GROUP_PREDICATES}
        sources: dict[tuple, set] = {}
        for graph in self.dataset.graphs():
            if not str(graph.identifier).startswith(str(CT)):
                continue
            src = local_name(graph.identifier)
            for group, predicate in self._GROUP_PREDICATES.items():
                for subject, obj in graph.subject_objects(predicate):
                    film, value = local_name(subject), local_name(obj)
                    by_film[group].setdefault(film, set()).add(value)
                    by_value[group].setdefault(value, set()).add(film)
                    sources.setdefault((group, film, value), set()).add(src)
        self._fi = {
            "by_film": by_film,
            "by_value": by_value,
            "sources": sources,
            "labels": {},
        }
        return self._fi

    def _fast_label(self, value_id: str) -> str:
        labels = self._fast_index()["labels"]
        if value_id not in labels:
            labels[value_id] = self._label(CT[value_id])
        return labels[value_id]

    def _source_items(self, group: str, film_id: str, value_id: str) -> list[dict]:
        names = sorted(
            self._fast_index()["sources"].get((group, film_id, value_id), ())
        )
        return [{"id": n, "label": self._fast_label(n)} for n in names]

    @lru_cache(maxsize=4096)
    def shared_details(self, seed_id: str, rec_id: str) -> dict:
        index = self._fast_index()
        result: dict = {}
        source_counter: Counter = Counter()
        for group in GROUPS:
            seed_values = index["by_film"][group].get(seed_id, set())
            rec_values = index["by_film"][group].get(rec_id, set())
            items = []
            for value in seed_values & rec_values:
                names = sorted(index["sources"].get((group, rec_id, value), ()))
                source_counter.update(names)
                items.append(
                    {"id": value, "label": self._fast_label(value), "sources": names}
                )
            result[group] = sorted(items, key=lambda item: item["label"])
        result["source_summary"] = dict(source_counter.most_common())
        return result

    @lru_cache(maxsize=1024)
    def recommendations(
        self, seed_id: str, limit: int = 5, priority: str = "balanced"
    ) -> list[dict]:
        weights = {
            "balanced": (3, 2, 2, 5),
            "cast": (3, 2, 6, 3),
            "director": (3, 6, 2, 3),
            "tropes": (6, 2, 2, 3),
            "genres": (3, 2, 2, 8),
        }
        trope_w, director_w, actor_w, genre_w = weights.get(
            priority, weights["balanced"]
        )
        index = self._fast_index()
        cards = self.cards()
        counts: dict[str, list[int]] = {}
        for position, group in enumerate(GROUPS):
            for value in index["by_film"][group].get(seed_id, ()):
                for film in index["by_value"][group].get(value, ()):
                    if film != seed_id and film in cards:
                        counts.setdefault(film, [0, 0, 0, 0])[position] += 1
        scored = []
        for film, (tropes, directors, actors, genres) in counts.items():
            score = (
                tropes * trope_w
                + directors * director_w
                + actors * actor_w
                + genres * genre_w
            )
            scored.append(
                (
                    -score,
                    -tropes,
                    cards[film]["title"],
                    film,
                    (tropes, directors, actors, genres),
                )
            )
        scored.sort()
        recommendations = []
        for negative_score, _, _, film, (tropes, directors, actors, genres) in scored[
            :limit
        ]:
            details = self.shared_details(seed_id, film)
            recommendations.append(
                {
                    "id": film,
                    "title": cards[film]["title"],
                    "year": cards[film]["year"],
                    "score": -negative_score,
                    "shared_tropes_count": tropes,
                    "shared_directors_count": directors,
                    "shared_actors_count": actors,
                    "shared_genres_count": genres,
                    "shared_tropes": details["tropes"],
                    "shared_directors": details["directors"],
                    "shared_actors": details["actors"],
                    "shared_genres": details["genres"],
                    "source_summary": details["source_summary"],
                }
            )
        return recommendations

    @lru_cache(maxsize=1)
    def cards(self) -> dict[str, dict]:
        """Schede film leggere costruite con lookup diretti sui triple (millisecondi)."""
        ds = self.dataset
        cards: dict[str, dict] = {}
        for film in set(ds.subjects(RDF.type, CT.Film)):
            title = next(ds.objects(film, RDFS.label), None)
            if title is None:
                continue
            year = next(ds.objects(film, CT.releaseYear), None)
            fid = local_name(film)
            cards[fid] = {
                "id": fid,
                "title": str(title),
                "year": str(year) if year is not None else None,
                "genres": sorted(
                    {self._label(g) for g in ds.objects(film, CT.hasGenre)}
                ),
                "directors": sorted(
                    {self._label(d) for d in ds.objects(film, CT.directedBy)}
                ),
                "tropeCount": len(set(ds.objects(film, CT.hasTrope))),
                "classes": [
                    c for c in DEFINED_CLASSES if (film, RDF.type, CT[c]) in ds
                ],
                "poster": self.poster_of(fid),
                "backdrop": image_url(
                    self._path(film, CT.backdropPath, "backdrop_path"), "w1280"
                ),
            }
        return cards

    @lru_cache(maxsize=1)
    def home(self) -> dict:
        cards = self.cards()
        ranked = sorted(cards.values(), key=lambda c: (-c["tropeCount"], c["title"]))

        def pick(predicate, limit=20):
            return [c for c in ranked if predicate(c)][:limit]

        hero = cards.get("TMDB27205") or ranked[0]
        used = {hero["id"]}  # ogni film compare in una sola categoria

        def take(predicate, limit=20):
            chosen = [c for c in ranked if c["id"] not in used and predicate(c)][:limit]
            used.update(c["id"] for c in chosen)
            return chosen

        specs = [
            ("tropes", "I più ricchi di tropi", lambda c: True),
            (
                "speculative",
                "Narrativa speculativa",
                lambda c: "SpeculativeFilm" in c["classes"],
            ),
            ("ensemble", "Film corali", lambda c: "EnsembleFilm" in c["classes"]),
            (
                "auteur",
                "Registi con collaboratori fissi",
                lambda c: "AuteurFilm" in c["classes"],
            ),
            ("classic", "Classici", lambda c: "ClassicFilm" in c["classes"]),
        ]
        genre_counts: Counter = Counter(g for c in cards.values() for g in c["genres"])
        specs += [
            (f"genre-{genre}", genre, lambda c, g=genre: g in c["genres"])
            for genre, _ in genre_counts.most_common(6)
        ]
        rows = [{"id": i, "title": t, "items": take(p)} for i, t, p in specs]
        return {"hero": hero, "rows": [r for r in rows if len(r["items"]) >= 4]}

    @lru_cache(maxsize=1024)
    def film_page(self, film_id: str, priority: str = "balanced") -> dict | None:
        film = self.film(film_id)
        if film is None:
            return None
        cards = self.cards()
        recs = [
            {
                **rec,
                **{k: v for k, v in cards.get(rec["id"], {}).items() if k not in rec},
            }
            for rec in self.recommendations(film_id, limit=5, priority=priority)
        ]
        return {"film": film, "recommendations": recs}

    @lru_cache(maxsize=1024)
    def relation(self, a_id: str, b_id: str) -> dict:
        """Spiega perché due opere sono collegate, anche tramite relazioni derivate."""
        a, b = CT[a_id], CT[b_id]
        if self.film(a_id) is None or self.film(b_id) is None:
            return {}
        derived = []
        if self._exists(a, CT.sameDirectorAs, b):
            for d in set(self.dataset.objects(a, CT.directedBy)) & set(
                self.dataset.objects(b, CT.directedBy)
            ):
                derived.append(
                    {
                        "relation": "sameDirectorAs",
                        "via": self._label(d),
                        "via_id": local_name(d),
                        "rule": "property chain directedBy ∘ directorOf",
                    }
                )
        for g in set(self.dataset.objects(a, CT.hasAncestorGenre)) & set(
            self.dataset.objects(b, CT.hasAncestorGenre)
        ):
            derived.append(
                {
                    "relation": "hasAncestorGenre",
                    "via": self._label(g),
                    "via_id": local_name(g),
                    "rule": "property chain hasGenre ∘ subGenreOf",
                }
            )
        for c in set(self.dataset.objects(a, CT.partOfCollection)) & set(
            self.dataset.objects(b, CT.partOfCollection)
        ):
            derived.append(
                {
                    "relation": "sameCollectionAs",
                    "via": self._label(c),
                    "via_id": local_name(c),
                    "rule": "property chain partOfCollection ∘ hasPart",
                }
            )
        for d1 in self.dataset.objects(a, CT.directedBy):
            for p in self.dataset.objects(d1, CT.hasFrequentCollaborator):
                if (b, CT.starring, p) in self.dataset or (
                    b,
                    CT.directedBy,
                    p,
                ) in self.dataset:
                    derived.append(
                        {
                            "relation": "hasFrequentCollaborator",
                            "via": f"{self._label(d1)} ↔ {self._label(p)}",
                            "via_id": local_name(p),
                            "rule": "SWRL FrequentCollaboratorRule",
                        }
                    )
        return {
            "seed": a_id,
            "target": b_id,
            "shared": self.shared_details(a_id, b_id),
            "derived": derived,
        }

    def search(self, filters: dict, limit: int = 50) -> dict:
        result = search_films(self.dataset, filters, limit)
        cards = self.cards()
        result["results"] = [cards.get(row["id"], row) for row in result["results"]]
        return result

    @property
    def _suggest_index(self) -> SuggestIndex:
        if not hasattr(self, "_index"):
            self._index = SuggestIndex(self.dataset)
        return self._index

    def suggest(self, query: str) -> list[dict]:
        return self._suggest_index.suggest(query)

    @lru_cache(maxsize=1024)
    def explanation(self, seed_id: str, rec_id: str) -> dict:
        result = self._execute(
            "04_explanation_construct.rq",
            iri_params={"seed": seed_id, "rec": rec_id},
        )
        graph = result.graph if result.graph is not None else Graph()
        return self._graph_to_payload(graph, seed_id, rec_id)

    def _graph_to_payload(self, graph: Graph, seed_id: str, rec_id: str) -> dict:
        seed_iri = CT[seed_id]
        rec_iri = CT[rec_id]
        nodes: dict[str, dict] = {}

        def add_node(node):
            if not isinstance(node, (URIRef, Literal)):
                return
            node_id = str(node)
            if node_id in nodes:
                return
            group = self._node_group(node, seed_iri, rec_iri)
            label = self._label(node) if isinstance(node, URIRef) else str(node)
            nodes[node_id] = {
                "id": node_id,
                "label": label,
                "group": group,
                "title": label,
            }

        edges = []
        seen_edges = set()
        for subject, predicate, obj in graph:
            if isinstance(obj, Literal):
                continue
            if not isinstance(predicate, URIRef):
                continue
            if predicate in SKIP_PREDICATES:
                continue
            label = EDGE_LABELS.get(predicate)
            if label is None:
                continue
            add_node(subject)
            add_node(obj)
            key = (str(subject), str(predicate), str(obj))
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append(
                {
                    "id": "|".join(key),
                    "from": str(subject),
                    "to": str(obj),
                    "label": label,
                    "predicate": local_name(predicate),
                }
            )

        triples = [
            {
                "subject": local_name(subject),
                "predicate": local_name(predicate),
                "object": local_name(obj),
            }
            for subject, predicate, obj in graph
        ]
        turtle = graph.serialize(format="turtle")
        return {
            "seed": seed_id,
            "recommendation": rec_id,
            "nodes": list(nodes.values()),
            "edges": edges,
            "triples": triples,
            "turtle": turtle,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "triple_count": len(triples),
            "seed_is_mindbender": self._exists(seed_iri, RDF.type, CT.MindBender),
            "recommendation_is_mindbender": self._exists(
                rec_iri, RDF.type, CT.MindBender
            ),
        }

    def _node_group(self, node, seed_iri, rec_iri) -> str:
        if node == seed_iri:
            return "seed"
        if node == rec_iri:
            return "recommendation"
        types = (
            set(self.dataset.objects(node, RDF.type))
            if isinstance(node, URIRef)
            else set()
        )
        if CT.Fonte in types:
            return "source"
        if CT.Tropo in types:
            return "trope"
        if CT.Genere in types:
            return "genre"
        if CT.Persona in types or CT.Regista in types or CT.Attore in types:
            return "person"
        if CT.Film in types or CT.MindBender in types:
            return "film"
        return "other"

    # ------------------------------------------------------------------
    # Competency questions e statistiche
    # ------------------------------------------------------------------
    def competency_question(self, cq: dict) -> dict:
        try:
            query = render_named_query(
                cq["query"],
                iri_params=cq.get("iri_params"),
                raw_params=cq.get("raw_params"),
            )
            result = self.dataset.query(query)
            rows = self._dict_rows(result)
            columns = [str(variable) for variable in (result.vars or [])]
            return {
                **cq,
                "query_text": query.strip(),
                "columns": columns,
                "rows": rows,
                "error": None,
            }
        except Exception as exc:
            return {
                **cq,
                "query_text": "",
                "columns": [],
                "rows": [],
                "error": str(exc),
            }

    @lru_cache(maxsize=64)
    def competency_question_by_id(self, cq_id: str) -> dict | None:
        cq = next((c for c in COMPETENCY_QUESTIONS if c["id"] == cq_id), None)
        return self.competency_question(cq) if cq else None

    @lru_cache(maxsize=1024)
    def competency_questions(self) -> list[dict]:
        return [self.competency_question(cq) for cq in COMPETENCY_QUESTIONS]

    @lru_cache(maxsize=1024)
    def stats(self) -> dict:
        base = dataset_stats(self.dataset)
        inferred = self.dataset.graph(CT.Inferred)
        mindbenders = len(set(self.dataset.subjects(RDF.type, CT.MindBender)))
        frequent_pairs = sum(
            1
            for person1, person2 in inferred.subject_objects(CT.hasFrequentCollaborator)
            if str(person1) < str(person2)
        )
        return {
            **base,
            "inferred_triples": len(inferred),
            "mindbenders": mindbenders,
            "frequent_collaborator_pairs": frequent_pairs,
            "build_report": self.build_report(),
        }

    @lru_cache(maxsize=1024)
    def mindbenders(self) -> list[dict]:
        return self.query_rows("06_mindbender.rq")

    @lru_cache(maxsize=1024)
    def frequent_collaborators(self) -> list[dict]:
        return self.query_rows("07_frequent_collaborators.rq")

    @lru_cache(maxsize=1024)
    def genre_hierarchy(self) -> list[dict]:
        return self.query_rows("09_genre_hierarchy.rq")


def _dedupe(items: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for item in items:
        key = item.get("id") or item.get("label")
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
