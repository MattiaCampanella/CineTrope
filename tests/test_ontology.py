from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from rdflib import OWL, RDF

from cinetrope.config import CT
from cinetrope.search import build_query
from cinetrope.store import CineTropeStore

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def store() -> CineTropeStore:
    return CineTropeStore.load_or_build()


def _validate_tbox():
    spec = importlib.util.spec_from_file_location(
        "pipeline", ROOT / "scripts" / "pipeline.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tbox_has_no_problems() -> None:
    module = _validate_tbox()
    problems = module.check(module.load_tbox())
    assert {name: items for name, items in problems.items() if items} == {}


def test_tbox_declares_advanced_axioms() -> None:
    module = _validate_tbox()
    graph = module.load_tbox()
    assert (CT.subGenreOf, RDF.type, OWL.TransitiveProperty) in graph
    assert (CT.hasAncestorGenre, OWL.propertyChainAxiom, None) in graph
    assert (CT.MindBender, OWL.equivalentClass, None) in graph
    assert (CT.releaseYear, RDF.type, OWL.FunctionalProperty) in graph
    assert (CT.OperaAudiovisiva, OWL.hasKey, None) in graph


def test_dl_axioms_are_not_in_the_dataset(store: CineTropeStore) -> None:
    ontology = store.dataset.graph(CT.Ontology)
    assert (CT.releaseYear, RDF.type, OWL.FunctionalProperty) not in ontology
    assert (CT.hasAncestorGenre, OWL.propertyChainAxiom, None) in ontology


def test_ancestor_genre_chain_is_inferred(store: CineTropeStore) -> None:
    assert (None, CT.hasAncestorGenre, CT.SpeculativeFiction) in store.dataset.graph(
        CT.Inferred
    )


def test_defined_classes_reported(store: CineTropeStore) -> None:
    counts = store.build_report()["reasoning"]["defined_classes"]
    assert counts["MindBender"] == store.stats()["mindbenders"]
    assert counts["MultiGenreFilm"] > 0


def test_relation_and_search(store: CineTropeStore) -> None:
    relation = store.relation("TMDB27205", "TMDB49026")
    assert relation["shared"] and "derived" in relation
    result = store.search({"title": "inception"})
    assert any(row["id"] == "TMDB27205" for row in result["results"])
    assert store.suggest("incep")[0]["label"].lower().startswith("incep")


def test_query_builder_rejects_unsafe_input() -> None:
    with pytest.raises(ValueError):
        build_query({"genre": "x> } DROP"})
    with pytest.raises(ValueError):
        build_query({"class": "NotAClass"})
    assert '\\"' in build_query({"title": 'a"b'})
