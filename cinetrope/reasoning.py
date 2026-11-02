from __future__ import annotations

from collections import Counter

from owlrl import DeductiveClosure, OWLRL_Semantics
from rdflib import Dataset, Graph, OWL, RDF, RDFS

from .config import CT
from .swrl import apply_swrl, load_rule_graph


def _is_cinetrope(term) -> bool:
    return str(term).startswith(str(CT))


def _union_graph(dataset: Dataset) -> Graph:
    union = Graph()
    for graph_id in dataset.graphs():
        if graph_id == CT.Inferred:
            continue
        for triple in dataset.graph(graph_id):
            union.add(triple)
    return union


def _run_owlrl(graph: Graph) -> None:
    DeductiveClosure(OWLRL_Semantics, rdfs_closure=True, axiomatic_triples=False, datatype_axioms=False).expand(graph)


def run_reasoning(dataset: Dataset) -> dict:
    """Esegue OWL RL e SWRL, salvando tutte le nuove triple nel named graph :Inferred."""
    union = _union_graph(dataset)
    explicit = set(union)

    _run_owlrl(union)
    swrl_stats = apply_swrl(union, load_rule_graph())
    _run_owlrl(union)

    inferred = {
        (subject, predicate, obj)
        for subject, predicate, obj in (set(union) - explicit)
        if (_is_cinetrope(subject) or _is_cinetrope(predicate) or _is_cinetrope(obj))
        and not (predicate == OWL.sameAs and subject == obj)
    }

    inferred_graph = dataset.graph(CT.Inferred)
    for triple in inferred:
        inferred_graph.add(triple)

    predicate_counts = Counter(str(predicate).split("#")[-1] for _, predicate, _ in inferred)
    return {
        "inferred_triples": len(inferred),
        "swrl_inferences": swrl_stats,
        "predicates": dict(predicate_counts.most_common(12)),
        "mindbenders": len(set(dataset.subjects(RDF.type, CT.MindBender))),
        "frequent_collaborator_links": sum(
            1 for _ in dataset.graph(CT.Inferred).triples((None, CT.hasFrequentCollaborator, None))
        ),
    }


def validation_checks(dataset: Dataset) -> list[dict]:
    """Controlli espliciti che integrano le restrizioni OWL durante l'ETL.

    Il reasoner OWL RL non implementa tutte le cardinalità qualificate; questi
    controlli servono a segnalare dati mancanti o incoerenti prima della demo.
    Non correggono automaticamente i dati (Open World Assumption).
    """
    prefix = """
        PREFIX : <http://example.org/cinetrope#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
    """
    checks = [
        (
            "missing_director",
            "Film senza regista",
            prefix
            + """
            SELECT ?film WHERE {
              ?film a :Film .
              FILTER NOT EXISTS { ?film :directedBy ?director }
            }
            """,
        ),
        (
            "missing_year",
            "Film senza anno di uscita",
            prefix
            + """
            SELECT ?film WHERE {
              ?film a :Film .
              FILTER NOT EXISTS { ?film :releaseYear ?year }
            }
            """,
        ),
        (
            "multiple_years",
            "Film con più anni di uscita",
            prefix
            + """
            SELECT ?film (COUNT(DISTINCT ?year) AS ?n) WHERE {
              ?film a :Film ; :releaseYear ?year .
            }
            GROUP BY ?film
            HAVING (COUNT(DISTINCT ?year) > 1)
            """,
        ),
        (
            "film_and_series",
            "Risorse classificate sia Film sia SerieTV",
            prefix
            + """
            SELECT ?work WHERE {
              ?work a :Film, :SerieTV .
            }
            """,
        ),
        (
            "owl_nothing",
            "Individui classificati come owl:Nothing",
            prefix
            + """
            SELECT ?resource WHERE {
              ?resource a owl:Nothing .
            }
            """,
        ),
    ]

    results = []
    for code, label, query in checks:
        try:
            rows = list(dataset.query(query))
        except Exception as exc:  # pragma: no cover - difesa per query diagnostiche
            results.append({"code": code, "label": label, "count": -1, "error": str(exc)})
            continue
        results.append(
            {
                "code": code,
                "label": label,
                "count": len(rows),
                "rows": [_first_row_value(row) for row in rows[:10]],
            }
        )
    return results


def _first_row_value(row) -> str:
    values = list(row)
    return str(values[0]) if values else ""
