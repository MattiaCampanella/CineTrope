from __future__ import annotations

import pytest

from cinetrope.config import CT
from cinetrope.etl import build_catalog
from cinetrope.store import CineTropeStore


@pytest.fixture(scope="session")
def store() -> CineTropeStore:
    return CineTropeStore.load_or_build()


def test_catalog(store: CineTropeStore) -> None:
    films = store.films()
    assert len(films) >= 80
    assert any(film["film"] == "TMDB27205" for film in films)
    assert len({film["film"] for film in films}) == len(films)
    inception = store.film("TMDB27205")
    assert inception is not None
    assert inception["title"] == "Inception"
    assert inception["year"] == "2010"
    assert inception["directors"][0]["id"] == "ChristopherNolan"
    assert inception["tropes"]


def test_dbpedia_service_enrichment() -> None:
    from rdflib import Literal, XSD

    dataset = build_catalog()
    expected = Literal("1970-07-30", datatype=XSD.date)
    assert (CT.ChristopherNolan, CT.birthDate, expected) in dataset.graph(CT.DBpedia)


def test_tmdb_provenance() -> None:
    from rdflib import RDF

    dataset = build_catalog()
    tmdb = dataset.graph(CT.TMDB)
    wikidata = dataset.graph(CT.Wikidata)

    assert (CT.TMDB27205, RDF.type, CT.Film) in tmdb
    assert (CT.TMDB27205, CT.directedBy, CT.ChristopherNolan) in tmdb
    assert (CT.TMDB27205, CT.directedBy, CT.ChristopherNolan) not in wikidata
    assert (CT.TMDB27205, CT.hasTrope, CT.dreams) in tmdb
    assert (CT.dreams, RDF.type, CT.Tropo) in tmdb


def test_genres_are_individuals_without_punning() -> None:
    from rdflib import OWL, RDF, RDFS

    dataset = build_catalog()
    local = dataset.graph(CT.LocalAnalysis)
    tmdb = dataset.graph(CT.TMDB)

    assert (CT.ScienceFiction, RDF.type, CT.Genere) in local
    assert (CT.ScienceFiction, RDF.type, OWL.Class) not in local
    assert (CT.ScienceFiction, RDFS.subClassOf, CT.SpeculativeFiction) not in local
    assert (CT.ScienceFiction, CT.subGenreOf, CT.SpeculativeFiction) in local
    assert (CT.SciFi, RDF.type, CT.Genere) not in local
    assert (CT.TMDB27205, CT.hasGenre, CT.ScienceFiction) in tmdb
    assert (CT.TMDB27205, CT.hasGenre, CT.SciFi) not in tmdb


def test_swrl_mindbenders(store: CineTropeStore) -> None:
    titles = {row["title"] for row in store.mindbenders()}
    assert len(titles) == store.stats()["mindbenders"]


def test_swrl_frequent_collaborators(store: CineTropeStore) -> None:
    pairs = store.frequent_collaborators()
    assert pairs


def test_recommendations(store: CineTropeStore) -> None:
    recommendations = store.recommendations("TMDB27205", limit=5)
    assert len(recommendations) == 5
    scores = [item["score"] for item in recommendations]
    assert scores == sorted(scores, reverse=True)
    assert recommendations[0]["shared_directors"]
    assert recommendations[0]["shared_genres"]


def test_explanation_construct_does_not_invent_shares(store: CineTropeStore) -> None:
    explanation = store.explanation("TMDB27205", "TMDB49026")
    predicates = {triple["predicate"] for triple in explanation["triples"]}
    assert "sharesGenreWith" in predicates
    assert explanation["recommendation_is_mindbender"] is False
    assert explanation["edge_count"] > 0
    assert "TMDB27205" in explanation["turtle"]


def test_provenance(store: CineTropeStore) -> None:
    sources = store.provenance("TMDB27205", "dreams")
    assert sources
    assert sources[0]["id"] == "TMDB"
    assert sources[0]["label"] == "TMDB"


def test_ontology_validation(store: CineTropeStore) -> None:
    report = store.build_report()
    assert report["validation"]
    assert all(check["count"] == 0 for check in report["validation"])
    assert report["reasoning"]["swrl_inferences"]["FrequentCollaboratorRule"] > 0


def test_competency_questions(store: CineTropeStore) -> None:
    questions = store.competency_questions()
    assert len(questions) == 9
    assert all(question["error"] is None for question in questions)
    by_id = {question["id"]: question for question in questions}
    assert len(by_id["cq1"]["rows"]) >= 0
    assert len(by_id["cq5"]["rows"]) == 5
    assert len(by_id["cq9"]["rows"]) > 0


def test_dataset_stats(store: CineTropeStore) -> None:
    stats = store.stats()
    assert stats["films"] >= 80
    assert stats["genres"] >= 19
    assert stats["inferred_triples"] > 0
    assert stats["mindbenders"] == 0
