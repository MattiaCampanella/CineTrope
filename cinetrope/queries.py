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
    if text.startswith("http://") or text.startswith("https://") or text.startswith("urn:"):
        return URIRef(text)
    return CT[text]


def render_query(text: str, iri_params: dict[str, Any] | None = None, raw_params: dict[str, Any] | None = None) -> str:
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


def render_named_query(name: str, iri_params: dict[str, Any] | None = None, raw_params: dict[str, Any] | None = None) -> str:
    return render_query(load_query(name), iri_params=iri_params, raw_params=raw_params)


COMPETENCY_QUESTIONS = [
    {
        "id": "cq1",
        "title": "Tropi condivisi",
        "question": "Quali film condividono almeno due tropi con Inception?",
        "query": "10_cq_shared_two_tropes.rq",
        "iri_params": {"seed": "TMDB27205"},
        "note": "Usa GROUP BY, HAVING e COUNT per classificare i film in base alla sovrapposizione di tropi.",
    },
    {
        "id": "cq2",
        "title": "Regista e tropo",
        "question": "Quali film sono diretti da persone che hanno lavorato su opere con lo stesso tropo?",
        "query": "11_cq_director_trope.rq",
        "iri_params": {"seed": "TMDB27205"},
        "note": "Combina directedBy con hasTrope e verifica la coerenza del percorso semantico.",
    },
    {
        "id": "cq3",
        "title": "MindBender inferiti",
        "question": "Quali film sono classificati come MindBender dalle regole SWRL?",
        "query": "06_mindbender.rq",
        "note": "La classe non è asserita nei dati: viene prodotta dalla regola SWRL UnreliableNarrator + TwistEnding.",
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
        "title": "Collaboratori frequenti",
        "question": "Quali persone sono collegate da hasFrequentCollaborator?",
        "query": "07_frequent_collaborators.rq",
        "note": "Il conteggio è materializzato dall'ETL; la regola SWRL crea il collegamento tra individui.",
    },
    {
        "id": "cq7",
        "title": "Gerarchia dei generi",
        "question": "Quali generi sono sottogeneri di altri generi?",
        "query": "09_genre_hierarchy.rq",
        "note": "Mostra la gerarchia dei generi modellati come individui tramite subGenreOf.",
    },
    {
        "id": "cq8",
        "title": "Fonti",
        "question": "Quante triple asserisce ciascun named graph?",
        "query": "08_source_stats.rq",
        "note": "Rende verificabile il contributo di Wikidata, DBpedia, TV Tropes, analisi locale, dati derivati e inferenze.",
    },
    {
        "id": "cq9",
        "title": "Co-star",
        "question": "Quali attori hanno recitato insieme?",
        "query": "12_cq_co_stars.rq",
        "note": "coStarsWith è dichiarata simmetrica in OWL; la relazione inversa viene inferita.",
    },
]
