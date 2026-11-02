from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import SOURCE_LABELS, STATIC_DIR, TEMPLATE_DIR
from .store import CineTropeStore

app = FastAPI(
    title="CineTrope",
    description="Recommender semantico spiegabile basato su tropi narrativi, OWL, SWRL e named graph.",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


def _source_label(value: str | None) -> str:
    if not value:
        return ""
    return SOURCE_LABELS.get(value, value)


def _number(value: Any) -> str:
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(value or 0)


templates.env.filters["source_label"] = _source_label
templates.env.filters["number"] = _number


@lru_cache(maxsize=1)
def get_store() -> CineTropeStore:
    return CineTropeStore.load_or_build()


def render(request: Request, name: str, context: dict, status_code: int = 200) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name=name,
        context={"request": request, **context},
        status_code=status_code,
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request, film: str | None = None) -> Response:
    if film:
        return RedirectResponse(url=f"/recommendations/{film}", status_code=303)
    store = get_store()
    films = store.films()
    stats = store.stats()
    featured_titles = {"Inception", "The Matrix", "Parasite", "Spirited Away", "The Shining", "Pulp Fiction"}
    featured = [film for film in films if film["title"] in featured_titles][:6]
    return render(
        request,
        "index.html",
        {
            "active": "home",
            "films": films,
            "featured": featured,
            "stats": stats,
            "source_count": len(store.source_stats()),
        },
    )


@app.get("/recommendations/{film_id}", response_class=HTMLResponse)
def recommendations_page(
    request: Request,
    film_id: str,
    priority: str = "balanced",
) -> HTMLResponse:
    store = get_store()
    film = store.film(film_id)
    if film is None:
        return not_found(request, f"Film non trovato: {film_id}")
    priorities = {
        "balanced": "Bilanciata",
        "cast": "Priorità cast",
        "director": "Priorità regia",
        "tropes": "Priorità tropi",
        "genres": "Priorità generi",
    }
    priority_weights = {
        "balanced": {"tropes": 3, "director": 2, "actors": 2, "genres": 5},
        "cast": {"tropes": 3, "director": 2, "actors": 6, "genres": 3},
        "director": {"tropes": 3, "director": 6, "actors": 2, "genres": 3},
        "tropes": {"tropes": 6, "director": 2, "actors": 2, "genres": 3},
        "genres": {"tropes": 3, "director": 2, "actors": 2, "genres": 8},
    }
    if priority not in priorities:
        priority = "balanced"
    recommendations = store.recommendations(film_id, limit=5, priority=priority)
    return render(
        request,
        "recommendations.html",
        {
            "active": "home",
            "film": film,
            "recommendations": recommendations,
            "all_films": store.films(),
            "priority": priority,
            "priorities": priorities,
            "priority_weights": priority_weights[priority],
        },
    )


@app.get("/explanation/{seed_id}/{rec_id}", response_class=HTMLResponse)
def explanation_page(request: Request, seed_id: str, rec_id: str) -> HTMLResponse:
    store = get_store()
    seed = store.film(seed_id)
    rec = store.film(rec_id)
    if seed is None or rec is None:
        return not_found(request, "Film non trovato nel catalogo.")
    explanation = store.explanation(seed_id, rec_id)
    details = store.shared_details(seed_id, rec_id)
    return render(
        request,
        "explanation.html",
        {
            "active": "home",
            "seed": seed,
            "recommendation": rec,
            "explanation": explanation,
            "details": details,
            "graph_json": explanation,
        },
    )


@app.get("/queries", response_class=HTMLResponse)
def queries_page(request: Request) -> HTMLResponse:
    store = get_store()
    return render(
        request,
        "queries.html",
        {
            "active": "queries",
            "questions": store.competency_questions(),
        },
    )


@app.get("/sources", response_class=HTMLResponse)
def sources_page(request: Request) -> HTMLResponse:
    store = get_store()
    stats = store.stats()
    return render(
        request,
        "sources.html",
        {
            "active": "sources",
            "sources": store.source_stats(),
            "stats": stats,
            "source_labels": SOURCE_LABELS,
        },
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
    return JSONResponse({"seed": film, "recommendations": store.recommendations(seed_id, limit)})


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


def not_found(request: Request, message: str) -> HTMLResponse:
    return render(request, "404.html", {"message": message}, status_code=404)


@app.exception_handler(404)
def custom_404(request: Request, exc: HTTPException):
    message = getattr(exc, "detail", "Pagina non trovata.")
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": message}, status_code=404)
    return not_found(request, message)
