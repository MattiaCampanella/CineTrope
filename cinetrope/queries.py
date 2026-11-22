from __future__ import annotations

from pathlib import Path
from typing import Any

from rdflib import URIRef

from .config import CT, QUERY_DIR


def load_query(name: str) -> str:
    path = Path(name)
    if not path.is_absolute():
        filename = name if name.endswith(".rq") else f"{name}.rq"
        path = QUERY_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Query non trovata: {path}")
    return path.read_text(encoding="utf-8")


def to_iri(value: Any) -> URIRef:
    if isinstance(value, URIRef):
        return value
    text = str(value)
    if (
        text.startswith("http://")
        or text.startswith("https://")
        or text.startswith("urn:")
    ):
        return URIRef(text)
    return CT[text]


def render_query(
    text: str,
    iri_params: dict[str, Any] | None = None,
    raw_params: dict[str, Any] | None = None,
) -> str:
    rendered = text
    for key, value in (iri_params or {}).items():
        iri = str(to_iri(value))
        for token in {key, key.upper(), key.lower()}:
            placeholder = "{{" + token + "}}"
            rendered = rendered.replace(f"<{placeholder}>", f"<{iri}>")
            rendered = rendered.replace(placeholder, f"<{iri}>")
    for key, value in (raw_params or {}).items():
        for token in {key, key.upper(), key.lower()}:
            rendered = rendered.replace("{{" + token + "}}", str(value))
    return rendered


def render_named_query(
    name: str,
    iri_params: dict[str, Any] | None = None,
    raw_params: dict[str, Any] | None = None,
) -> str:
    return render_query(load_query(name), iri_params=iri_params, raw_params=raw_params)


COMPETENCY_QUESTIONS = [
    {
        "id": "cq1",
        "title": "Tropi condivisi",
        "question": "Quali film condividono almeno due tropi con Avengers: Endgame?",
        "query": "10_cq_shared_two_tropes.rq",
        "iri_params": {"seed": "TMDB299534"},
        "note": "Usa GROUP BY, HAVING e COUNT per classificare i film in base alla sovrapposizione di tropi.",
    },
    {
        "id": "cq2",
        "title": "Regista e tropo",
        "question": "Quali film sono diretti da registi che hanno lavorato su opere con lo stesso tropo di Avengers: Endgame?",
        "query": "11_cq_director_trope.rq",
        "iri_params": {"seed": "TMDB299534"},
        "note": "Combina directedBy con hasTrope e verifica la coerenza del percorso semantico.",
    },
    {
        "id": "cq3",
        "title": "Dettagli condivisi",
        "question": "Quali proprietà condividono Inception e Il cavaliere oscuro?",
        "query": "13_shared_details.rq",
        "iri_params": {"seed": "TMDB27205", "rec": "TMDB155"},
        "note": "Confronta tropi, regista, attori e generi condivisi, indicando anche il named graph della fonte.",
    },
    {
        "id": "cq4",
        "title": "Provenienza",
        "question": "Da quale fonte proviene l'asserzione 'Inception usa dreams'?",
        "query": "05_provenance_assertion.rq",
        "iri_params": {"film": "TMDB27205", "trope": "dreams"},
        "note": "Interroga direttamente i named graph con GRAPH ?source, senza reificazione.",
    },
    {
        "id": "cq5",
        "title": "Raccomandazioni spiegabili",
        "question": "Quali film condividono tropi, regista, attori o generi con un film scelto?",
        "query": "03_recommendations.rq",
        "iri_params": {"seed": "TMDB27205"},
        "raw_params": {
            "limit": 5,
            "trope_weight": 3,
            "director_weight": 2,
            "actor_weight": 2,
            "genre_weight": 5,
        },
        "note": "È la query usata dalla demo: punteggio combinato e cinque risultati ordinati.",
    },
    {
        "id": "cq6",
        "title": "Collaboratori frequenti (SWRL)",
        "question": "Quali coppie regista-attore sono collegate da hasFrequentCollaborator?",
        "query": "07_frequent_collaborators.rq",
        "note": "Inferita dalla regola SWRL FrequentCollaboratorRule (ciclo a diamante a 4 nodi con DifferentIndividuals, impossibile in puro OWL 2 DL).",
    },
    {
        "id": "cq7",
        "title": "Gerarchia dei generi",
        "question": "Quali generi sono sottogeneri di altri generi?",
        "query": "09_genre_hierarchy.rq",
        "note": "Mostra la gerarchia dei generi modellati come individui tramite subGenreOf (proprietà transitiva).",
    },
    {
        "id": "cq8",
        "title": "Fonti",
        "question": "Quante triple asserisce ciascun named graph?",
        "query": "08_source_stats.rq",
        "note": "Rende verificabile il contributo di Ontology, TMDB, Wikidata, DBpedia e delle inferenze HermiT.",
    },
    {
        "id": "cq9",
        "title": "Co-star ricorrenti (CONSTRUCT + SymmetricProperty)",
        "question": "Quali coppie di attori hanno recitato insieme in almeno due film distinti?",
        "query": "12_cq_co_stars.rq",
        "note": "Derivata in una direzione con SPARQL CONSTRUCT (L8); HermiT inferisce la direzione inversa tramite owl:SymmetricProperty (L11).",
    },
    {
        "id": "cq10",
        "title": "Classe definita (intersezione)",
        "question": "Quali film sono sia acclamati sia blockbuster secondo HermiT (classe AcclaimedBlockbuster)?",
        "query": "14_cq_defined_class.rq",
        "note": "AcclaimedBlockbuster è definita come intersezione di AcclaimedFilm e Blockbuster e classificata automaticamente da HermiT.",
    },
    {
        "id": "cq11",
        "title": "Genere antenato (property chain)",
        "question": "Quali film sono di narrativa speculativa senza dichiararlo esplicitamente?",
        "query": "15_cq_ancestor_genre.rq",
        "note": "Interroga i film appartenenti a sottogeneri di Narrativa speculativa tramite subGenreOf / property chain hasAncestorGenre.",
    },
    {
        "id": "cq12",
        "title": "Stesso regista (property chain)",
        "question": "Quali coppie di film condividono il regista?",
        "query": "16_cq_same_director.rq",
        "note": "sameDirectorAs = directedBy ∘ directorOf è materializzata da HermiT, senza join manuali.",
    },
    {
        "id": "cq13",
        "title": "Registi auteur (someValuesFrom su classe definita)",
        "question": "Quali registi sono classificati come Auteur da HermiT?",
        "query": "17_cq_auteur.rq",
        "note": "Auteur ≡ Regista ⊓ (directorOf some AcclaimedFilm): restrizione esistenziale su classe definita + proprietà inversa, classificata da HermiT.",
    },
    {
        "id": "cq14",
        "title": "Film multigenere (cardinalità qualificata)",
        "question": "Quali film appartengono ad almeno tre generi distinti (classe MultiGenreFilm)?",
        "query": "18_cq_multi_genre.rq",
        "note": "Cardinalità qualificata minima (hasGenre min 3 Genere): classificata nativamente da HermiT con owl:AllDifferent sui generi.",
    },
    {
        "id": "cq15",
        "title": "Film acclamati e blockbuster",
        "question": "Quali film hanno voto alto o incassi elevati?",
        "query": "19_cq_acclaimed_blockbuster.rq",
        "note": "Datatype restriction OWL 2 (xsd:minInclusive) su voteAverage ≥ 7.5 e revenue ≥ 500M USD, classificata da HermiT.",
    },
]
