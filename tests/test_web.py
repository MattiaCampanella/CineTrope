from __future__ import annotations

from fastapi.testclient import TestClient

from cinetrope.web import app, get_store


def test_home() -> None:
    get_store.cache_clear()
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "CineTrope" in response.text
    assert "Inception" in response.text


def test_recommendations_page() -> None:
    with TestClient(app) as client:
        response = client.get("/recommendations/TMDB27205")
    assert response.status_code == 200
    assert "Il cavaliere oscuro" in response.text
    assert "Esplora il grafo" in response.text
    assert "Tropi condivisi" in response.text


def test_priority_rebuilds_recommendation_ranking() -> None:
    with TestClient(app) as client:
        balanced = client.get("/recommendations/TMDB27205?priority=balanced")
        cast = client.get("/recommendations/TMDB27205?priority=cast")
    assert balanced.status_code == 200
    assert cast.status_code == 200
    assert "Bilanciata" in balanced.text
    assert "Priorità cast" in cast.text
    assert balanced.text != cast.text


def test_home_form_redirects_without_javascript() -> None:
    with TestClient(app) as client:
        response = client.get("/?film=Inception", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/recommendations/Inception"


def test_explanation_page() -> None:
    with TestClient(app) as client:
        response = client.get("/explanation/TMDB27205/TMDB49026")
    assert response.status_code == 200
    assert "CINETROPE_GRAPH" in response.text
    assert "vis-network" in response.text
    assert "sharesGenreWith" in response.text


def test_queries_page() -> None:
    with TestClient(app) as client:
        response = client.get("/queries")
    assert response.status_code == 200
    assert "Competency" in response.text or "competency" in response.text
    assert "CQ1" in response.text


def test_sources_page() -> None:
    with TestClient(app) as client:
        response = client.get("/sources")
    assert response.status_code == 200
    assert "TMDB" in response.text
    assert "Named graph" in response.text or "named graph" in response.text


def test_api_recommendations() -> None:
    with TestClient(app) as client:
        response = client.get("/api/recommendations/TMDB27205?limit=3")
    assert response.status_code == 200
    payload = response.json()
    assert payload["seed"]["title"] == "Inception"
    assert len(payload["recommendations"]) == 3


def test_api_explanation() -> None:
    with TestClient(app) as client:
        response = client.get("/api/explanation/TMDB27205/TMDB49026")
    assert response.status_code == 200
    payload = response.json()
    assert payload["seed"] == "TMDB27205"
    assert payload["recommendation"] == "TMDB49026"
    assert payload["nodes"]


def test_404() -> None:
    with TestClient(app) as client:
        response = client.get("/recommendations/NonEsiste")
    assert response.status_code == 404
    assert "Nessun film" in response.text


def test_api_404_is_json() -> None:
    with TestClient(app) as client:
        missing_film = client.get("/api/recommendations/NonEsiste")
        missing_route = client.get("/api/route-inesistente")
    assert missing_film.status_code == 404
    assert missing_film.headers["content-type"].startswith("application/json")
    assert missing_film.json()["detail"]
    assert missing_route.status_code == 404
    assert missing_route.headers["content-type"].startswith("application/json")


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
