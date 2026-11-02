"""API applicativa per catalogo, raccomandazioni, spiegazioni e provenienza."""

from __future__ import annotations

import json
from collections import Counter, defaultdict

from rdflib import Graph, Literal, RDF, RDFS, URIRef, Dataset

from .config import (
    CATALOG_PATH,
    CT,
    GENERATED_DIR,
    REPORT_PATH,
    SOURCE_GRAPHS,
    SOURCE_LABELS,
    STORE_PATH,
)
from .etl import build_catalog, dataset_stats
from .queries import COMPETENCY_QUESTIONS, load_query, render_named_query, render_query
from .reasoning import run_reasoning, validation_checks

GROUPS = ("tropes", "directors", "actors", "genres")
KIND_TO_GROUP = {"trope": "tropes", "director": "directors", "actor": "actors", "genre": "genres"}

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

SKIP_PREDICATES = {RDF.type, CT.sharesTropeWith, CT.sharesDirectorWith, CT.sharesActorWith, CT.sharesGenreWith}


def local_name(term) -> str:
    text = str(term)
    namespace = str(CT)
    if text.startswith(namespace):
        return text[len(namespace):]
    return text


def _json_value(term):
    if term is None:
        return None
    if isinstance(term, Literal):
        return term.value if term.datatype is None and term.language is None else str(term)
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
        dataset = build_catalog(write=True)
        reasoning_report = run_reasoning(dataset)
        checks = validation_checks(dataset)
        report = {
            "reasoning": reasoning_report,
            "validation": checks,
            "stats": dataset_stats(dataset),
        }
        dataset.serialize(destination=STORE_PATH, format="trig")
        REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return cls(dataset)

    def build_report(self) -> dict:
        if REPORT_PATH.exists():
            return json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        return {}

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def _execute(self, query_name: str, iri_params=None, raw_params=None):
        query = render_named_query(query_name, iri_params=iri_params, raw_params=raw_params)
        return self.dataset.query(query)

    def _dict_rows(self, result) -> list[dict]:
        columns = [str(variable) for variable in (result.vars or [])]
        rows = []
        for row in result:
            rows.append({column: _json_value(row[index]) for index, column in enumerate(columns)})
        return rows

    def query_rows(self, query_name: str, iri_params=None, raw_params=None) -> list[dict]:
        return self._dict_rows(self._execute(query_name, iri_params=iri_params, raw_params=raw_params))

    def _label(self, node) -> str:
        labels = sorted(self.dataset.objects(node, RDFS.label), key=str)
        if labels:
            return str(labels[0])
        return local_name(node)

    def _exists(self, subject, predicate, obj) -> bool:
        return (subject, predicate, obj) in self.dataset

    # ------------------------------------------------------------------
    # Catalogo e dettaglio film
    # ------------------------------------------------------------------
    def films(self) -> list[dict]:
        return self.query_rows("01_films.rq")

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
        directors = [{"id": local_name(value), "label": self._label(value)} for value in self.dataset.objects(iri, CT.directedBy)]
        actors = [{"id": local_name(value), "label": self._label(value)} for value in self.dataset.objects(iri, CT.starring)]
        genres = [{"id": local_name(value), "label": self._label(value)} for value in self.dataset.objects(iri, CT.hasGenre)]

        tropes = []
        for trope in sorted(set(self.dataset.objects(iri, CT.hasTrope)), key=lambda node: self._label(node)):
            tropes.append(
                {
                    "id": local_name(trope),
                    "label": self._label(trope),
                    "sources": self.sources_for(iri, CT.hasTrope, trope),
                }
            )

        elements = []
        for element in sorted(set(self.dataset.objects(iri, CT.hasElement)), key=lambda node: self._label(node)):
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
            "is_mindbender": self._exists(iri, RDF.type, CT.MindBender),
        }

    # ------------------------------------------------------------------
    # Provenienza
    # ------------------------------------------------------------------
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
        return _dedupe([{"id": row["source"], "label": row["label"]} for row in rows if row.get("source")])

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

    def source_stats(self) -> list[dict]:
        return self.query_rows("08_source_stats.rq")

    # ------------------------------------------------------------------
    # Raccomandazioni e spiegazioni
    # ------------------------------------------------------------------
    def shared_details(self, seed_id: str, rec_id: str) -> dict:
        rows = self.query_rows(
            "13_shared_details.rq",
            iri_params={"seed": seed_id, "rec": rec_id},
        )
        grouped: dict[str, dict] = {group: {} for group in GROUPS}
        source_counter: Counter = Counter()
        for row in rows:
            group = KIND_TO_GROUP.get(str(row.get("kind")))
            if group is None:
                continue
            key = row.get("value")
            if not key:
                continue
            item = grouped[group].setdefault(
                key,
                {"id": key, "label": row.get("label") or key, "sources": set()},
            )
            if row.get("source"):
                source = row["source"]
                item["sources"].add(source)
                source_counter[source] += 1
        result = {}
        for group in GROUPS:
            items = []
            for item in sorted(grouped[group].values(), key=lambda entry: entry["label"]):
                items.append(
                    {
                        "id": item["id"],
                        "label": item["label"],
                        "sources": sorted(item["sources"]),
                    }
                )
            result[group] = items
        result["source_summary"] = dict(source_counter.most_common())
        return result

    def recommendations(self, seed_id: str, limit: int = 5, priority: str = "balanced") -> list[dict]:
        weights = {
            "balanced": (3, 2, 2, 5),
            "cast": (3, 2, 6, 3),
            "director": (3, 6, 2, 3),
            "tropes": (6, 2, 2, 3),
            "genres": (3, 2, 2, 8),
        }
        trope_weight, director_weight, actor_weight, genre_weight = weights.get(priority, weights["balanced"])
        rows = self.query_rows(
            "03_recommendations.rq",
            iri_params={"seed": seed_id},
            raw_params={
                "limit": limit,
                "trope_weight": trope_weight,
                "director_weight": director_weight,
                "actor_weight": actor_weight,
                "genre_weight": genre_weight,
            },
        )
        recommendations = []
        for row in rows:
            rec_id = row["film"]
            if not rec_id or rec_id == seed_id:
                continue
            details = self.shared_details(seed_id, rec_id)
            recommendations.append(
                {
                    "id": rec_id,
                    "title": row.get("title") or rec_id,
                    "year": row.get("year"),
                    "score": _int(row.get("score")),
                    "shared_tropes_count": _int(row.get("sharedTropes")),
                    "shared_directors_count": _int(row.get("sharedDirectors")),
                    "shared_actors_count": _int(row.get("sharedActors")),
                    "shared_genres_count": _int(row.get("sharedGenres")),
                    "shared_tropes": details["tropes"],
                    "shared_directors": details["directors"],
                    "shared_actors": details["actors"],
                    "shared_genres": details["genres"],
                    "source_summary": details["source_summary"],
                }
            )
        return recommendations

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
            "recommendation_is_mindbender": self._exists(rec_iri, RDF.type, CT.MindBender),
        }

    def _node_group(self, node, seed_iri, rec_iri) -> str:
        if node == seed_iri:
            return "seed"
        if node == rec_iri:
            return "recommendation"
        types = set(self.dataset.objects(node, RDF.type)) if isinstance(node, URIRef) else set()
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

    def competency_questions(self) -> list[dict]:
        return [self.competency_question(cq) for cq in COMPETENCY_QUESTIONS]

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

    def mindbenders(self) -> list[dict]:
        return self.query_rows("06_mindbender.rq")

    def frequent_collaborators(self) -> list[dict]:
        return self.query_rows("07_frequent_collaborators.rq")

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
