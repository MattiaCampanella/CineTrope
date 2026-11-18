from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .config import SOURCE_LABELS
from .store import CineTropeStore

_store: CineTropeStore | None = None
_store_lock = threading.Lock()


def get_store() -> CineTropeStore:
    """Carica lo store una sola volta. Il lock evita che /health e il warm-up lo carichino
    insieme (due parse in parallelo mandavano rdflib in KeyError)."""
    global _store
    with _store_lock:
        if _store is None:
            _store = CineTropeStore.load_or_build()
        return _store


def _reset_store() -> None:
    global _store
    with _store_lock:
        _store = None


get_store.cache_clear = _reset_store  # compatibilità con i test


def _warm_up() -> None:
    # Le query SPARQL su rdflib sono lente (secondi): le eseguo una volta sola all'avvio.
    store = get_store()
    # Le competency question (15 query pesanti) NON si scaldano: si eseguono una per
    # volta quando la pagina le chiede, altrimenti rallentano ogni altra richiesta.
    for call in (store.cards, store.home, store.stats, store.source_stats):
        call()


@asynccontextmanager
async def lifespan(_: FastAPI):
    threading.Thread(target=_warm_up, daemon=True).start()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="CineTrope",
    description="Backend semantico di CineTrope (JSON). Il sito è in web/ (Next.js).",
    version="2.0.0",
)


@app.get("/api/search")
def api_search(
    title: str = "",
    genre: str = "",
    director: str = "",
    actor: str = "",
    trope: str = "",
    year_from: int | None = None,
    year_to: int | None = None,
    min_rating: float | None = None,
    min_runtime: int | None = None,
    cls: str = "",
    limit: int = 50,
) -> JSONResponse:
    filters = {
        "title": title,
        "genre": genre,
        "director": director,
        "actor": actor,
        "trope": trope,
        "year_from": year_from,
        "year_to": year_to,
        "min_rating": min_rating,
        "min_runtime": min_runtime,
        "class": cls,
    }
    try:
        return JSONResponse(get_store().search(filters, min(max(limit, 1), 200)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/suggest")
def api_suggest(q: str = "") -> JSONResponse:
    return JSONResponse(get_store().suggest(q))


@app.get("/api/relation/{a_id}/{b_id}")
def api_relation(a_id: str, b_id: str) -> JSONResponse:
    relation = get_store().relation(a_id, b_id)
    if not relation:
        raise HTTPException(status_code=404, detail="Film non trovato")
    return JSONResponse(relation)


@app.get("/api/home")
def api_home() -> JSONResponse:
    store = get_store()
    stats = store.stats()
    keys = (
        "films",
        "people",
        "tropes",
        "genres",
        "triples",
        "named_graphs",
        "inferred_triples",
    )
    return JSONResponse({**store.home(), "stats": {k: stats[k] for k in keys}})


@app.get("/api/film/{film_id}")
def api_film(film_id: str, priority: str = "balanced") -> JSONResponse:
    page = get_store().film_page(film_id, priority)
    if page is None:
        raise HTTPException(status_code=404, detail=f"Film non trovato: {film_id}")
    return JSONResponse({**page, "priority": priority})


@app.get("/api/card/{film_id}")
def api_card(film_id: str) -> JSONResponse:
    card = get_store().cards().get(film_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"Film non trovato: {film_id}")
    return JSONResponse(card)


@app.get("/api/queries")
def api_queries() -> JSONResponse:
    from .queries import COMPETENCY_QUESTIONS

    meta = ("id", "title", "question", "note")
    return JSONResponse([{k: cq[k] for k in meta} for cq in COMPETENCY_QUESTIONS])


@app.get("/api/queries/{cq_id}")
def api_query(cq_id: str) -> JSONResponse:
    result = get_store().competency_question_by_id(cq_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Competency question inesistente")
    return JSONResponse(result)


@app.get("/api/sources")
def api_sources() -> JSONResponse:
    store = get_store()
    return JSONResponse(
        {
            "sources": store.source_stats(),
            "labels": SOURCE_LABELS,
            "stats": store.stats(),
        }
    )


@app.get("/api/films")
def api_films() -> JSONResponse:
    return JSONResponse(get_store().films())


@app.get("/api/recommendations/{seed_id}")
def api_recommendations(seed_id: str, limit: int = 5) -> JSONResponse:
    store = get_store()
    film = store.film(seed_id)
    if film is None:
        raise HTTPException(status_code=404, detail=f"Film non trovato: {seed_id}")
    limit = max(1, min(limit, 10))
    return JSONResponse(
        {"seed": film, "recommendations": store.recommendations(seed_id, limit)}
    )


@app.get("/api/explanation/{seed_id}/{rec_id}")
def api_explanation(seed_id: str, rec_id: str) -> JSONResponse:
    store = get_store()
    if store.film(seed_id) is None or store.film(rec_id) is None:
        raise HTTPException(status_code=404, detail="Film non trovato nel catalogo.")
    return JSONResponse(store.explanation(seed_id, rec_id))


@app.get("/api/provenance/{film_id}/{trope_id}")
def api_provenance(film_id: str, trope_id: str) -> JSONResponse:
    return JSONResponse(get_store().provenance(film_id, trope_id))


@app.get("/api/competency-questions")
def api_competency_questions() -> JSONResponse:
    return JSONResponse(get_store().competency_questions())


@app.get("/api/stats")
def api_stats() -> JSONResponse:
    return JSONResponse(get_store().stats())


@app.get("/health")
def health() -> dict:
    stats = get_store().stats()
    return {"status": "ok", "films": stats["films"], "triples": stats["triples"]}


@app.exception_handler(404)
def json_404(request: Request, exc: HTTPException):
    return JSONResponse(
        {"detail": getattr(exc, "detail", "Risorsa non trovata.")}, status_code=404
    )
