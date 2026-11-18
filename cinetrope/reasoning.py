from __future__ import annotations

import logging
import time
from collections import Counter

from owlrl import DeductiveClosure, OWLRL_Semantics
from rdflib import OWL, RDF, BNode, Dataset, Graph

from .config import CT, RULES_DIR
from .swrl import apply_swrl, load_rule_graph

log = logging.getLogger(__name__)

DEFINED_CLASSES = (
    "MindBender",
    "SpeculativeFilm",
    "CollectionFilm",
    "SequelFilm",
    "MultiGenreFilm",
    "EnsembleFilm",
    "AuteurFilm",
    "AcclaimedFilm",
    "Blockbuster",
    "EpicFilm",
    "ClassicFilm",
    "ItalianFilm",
)


def _is_cinetrope(term) -> bool:
    return str(term).startswith(str(CT))


def _union_graph(dataset: Dataset) -> Graph:
    union = Graph()
    for graph_id in dataset.graphs():
        if graph_id == CT.Inferred:
            continue
        for triple in dataset.graph(graph_id):
            _, predicate, obj = triple
            # Gli allineamenti esterni (schema.org, DBpedia, ...) restano documentali:
            # farli espandere a owlrl duplicherebbe ogni tripla del catalogo.
            if (
                predicate in (OWL.equivalentClass, OWL.equivalentProperty)
                and not _is_cinetrope(obj)
                and not isinstance(obj, BNode)
            ):
                continue
            union.add(triple)
    return union


def apply_classification_rules(graph: Graph) -> dict:
    """Esegue le regole CONSTRUCT per le classi definite che OWL RL non calcola."""
    counts = {}
    for path in sorted(RULES_DIR.glob("*.rq")):
        added = 0
        for triple in graph.query(path.read_text(encoding="utf-8")).graph or []:
            if triple not in graph:
                graph.add(triple)
                added += 1
        counts[path.stem] = added
    return counts


def _run_owlrl(graph: Graph) -> None:
    DeductiveClosure(
        OWLRL_Semantics,
        rdfs_closure=True,
        axiomatic_triples=False,
        datatype_axioms=False,
    ).expand(graph)


# Relazioni simmetriche massive (~64k triple): owlrl impiega decine di minuti
# per chiuderle, mentre senza di esse l'inferenza dura ~30 s. Vengono tolte
# dall'input di owlrl e simmetrizzate a mano (stesso risultato).
HEAVY_SYMMETRIC = (CT.collaboratedWith, CT.coStarsWith)


def _split_heavy(graph: Graph) -> list[tuple]:
    heavy = [t for t in graph if t[1] in HEAVY_SYMMETRIC]
    for triple in heavy:
        graph.remove(triple)
    return heavy


def _restore_heavy(graph: Graph, heavy: list[tuple]) -> None:
    for subject, predicate, obj in heavy:
        graph.add((subject, predicate, obj))
        graph.add((obj, predicate, subject))


def run_reasoning(dataset: Dataset) -> dict:
    """Esegue OWL RL e SWRL, salvando tutte le nuove triple nel named graph :Inferred."""
    union = _union_graph(dataset)
    explicit = set(union)

    log.info(
        "reasoning: %d triple esplicite, avvio OWL RL (prima passata)", len(explicit)
    )
    started = time.time()
    heavy = _split_heavy(union)
    _run_owlrl(union)
    _restore_heavy(union, heavy)
    log.info(
        "reasoning: prima passata OWL RL in %.0fs, applico le regole SWRL",
        time.time() - started,
    )
    swrl_stats = apply_swrl(union, load_rule_graph())
    log.info("reasoning: SWRL %s, seconda passata OWL RL", swrl_stats)
    started = time.time()
    heavy = _split_heavy(union)
    _run_owlrl(union)
    _restore_heavy(union, heavy)
    log.info(
        "reasoning: seconda passata OWL RL in %.0fs, classi definite",
        time.time() - started,
    )
    rule_stats = apply_classification_rules(union)
    log.info("reasoning: classi definite da regole SPARQL %s", rule_stats)

    inferred = {
        (subject, predicate, obj)
        for subject, predicate, obj in (set(union) - explicit)
        if (_is_cinetrope(subject) or _is_cinetrope(predicate) or _is_cinetrope(obj))
        and not (predicate == OWL.sameAs and subject == obj)
        # equivalentClass anonime fanno comparire classi-restrizione come tipo.
        and not (predicate == RDF.type and isinstance(obj, BNode))
        and not isinstance(subject, BNode)
    }

    log.info("reasoning: %d triple inferite, le salvo in :Inferred", len(inferred))
    inferred_graph = dataset.graph(CT.Inferred)
    for triple in inferred:
        inferred_graph.add(triple)

    predicate_counts = Counter(
        str(predicate).split("#")[-1] for _, predicate, _ in inferred
    )
    return {
        "inferred_triples": len(inferred),
        "swrl_inferences": swrl_stats,
        "classification_rules": rule_stats,
        "defined_classes": {
            name: len(set(dataset.subjects(RDF.type, CT[name])))
            for name in DEFINED_CLASSES
        },
        "predicates": dict(predicate_counts.most_common(12)),
        "mindbenders": len(set(dataset.subjects(RDF.type, CT.MindBender))),
        "frequent_collaborator_links": sum(
            1
            for _ in dataset.graph(CT.Inferred).triples(
                (None, CT.hasFrequentCollaborator, None)
            )
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
            prefix + """
            SELECT ?film WHERE {
              ?film a :Film .
              FILTER NOT EXISTS { ?film :directedBy ?director }
            }
            """,
        ),
        (
            "missing_year",
            "Film senza anno di uscita",
            prefix + """
            SELECT ?film WHERE {
              ?film a :Film .
              FILTER NOT EXISTS { ?film :releaseYear ?year }
            }
            """,
        ),
        (
            "multiple_years",
            "Film con più anni di uscita",
            prefix + """
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
            prefix + """
            SELECT ?work WHERE {
              ?work a :Film, :SerieTV .
            }
            """,
        ),
        (
            "owl_nothing",
            "Individui classificati come owl:Nothing",
            prefix + """
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
            results.append(
                {"code": code, "label": label, "count": -1, "error": str(exc)}
            )
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
