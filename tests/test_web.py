from __future__ import annotations

from fastapi.testclient import TestClient

from cinetrope.web import app, get_store


def _client() -> TestClient:
    get_store.cache_clear()
    return TestClient(app)


def test_home_payload() -> None:
    with _client() as client:
        response = client.get("/api/home")
    assert response.status_code == 200
    payload = response.json()
    assert payload["hero"]["title"]
    assert payload["stats"]["films"] >= 80
    assert payload["rows"] and all(row["items"] for row in payload["rows"])
    card = payload["rows"][0]["items"][0]
    assert {"id", "title", "year", "genres", "poster", "classes"} <= set(card)


def test_film_page_payload() -> None:
    with TestClient(app) as client:
        response = client.get("/api/film/TMDB27205")
    assert response.status_code == 200
    payload = response.json()
    assert payload["film"]["title"] == "Inception"
    assert len(payload["recommendations"]) == 5
    assert any(
        "Il cavaliere oscuro" in rec["title"] for rec in payload["recommendations"]
    )
    assert {"poster", "genres", "score"} <= set(payload["recommendations"][0])


def test_priority_changes_ranking() -> None:
    with TestClient(app) as client:
        balanced = client.get("/api/film/TMDB27205?priority=balanced").json()
        cast = client.get("/api/film/TMDB27205?priority=cast").json()
    assert balanced["recommendations"] != cast["recommendations"]


def test_api_recommendations() -> None:
    with TestClient(app) as client:
        response = client.get("/api/recommendations/TMDB27205?limit=3")
    assert response.status_code == 200
    payload = response.json()
    assert payload["seed"]["title"] == "Inception"
    assert len(payload["recommendations"]) == 3


def test_api_explanation_and_relation() -> None:
    with TestClient(app) as client:
        explanation = client.get("/api/explanation/TMDB27205/TMDB49026")
        relation = client.get("/api/relation/TMDB27205/TMDB49026")
    assert explanation.status_code == 200
    payload = explanation.json()
    assert payload["seed"] == "TMDB27205" and payload["recommendation"] == "TMDB49026"
    assert payload["nodes"]
    assert relation.status_code == 200
    assert relation.json()["derived"]


def test_search_and_suggest() -> None:
    with TestClient(app) as client:
        search = client.get("/api/search?title=incep").json()
        suggest = client.get("/api/suggest?q=incep").json()
        bad = client.get("/api/search?cls=NotAClass")
    assert any(card["id"] == "TMDB27205" for card in search["results"])
    assert "poster" in search["results"][0]
    assert suggest and suggest[0]["label"].lower().startswith("incep")
    assert bad.status_code == 400


def test_queries_are_lazy_and_individual() -> None:
    with TestClient(app) as client:
        meta = client.get("/api/queries").json()
        one = client.get("/api/queries/cq5").json()
        missing = client.get("/api/queries/cq999")
    assert len(meta) == 15 and "query" not in meta[0]
    assert one["error"] is None and len(one["rows"]) == 5
    assert missing.status_code == 404


def test_sources_counts_named_graphs() -> None:
    with TestClient(app) as client:
        payload = client.get("/api/sources").json()
    ids = {row["source"].split("#")[-1] for row in payload["sources"]}
    assert {"TMDB", "Derived", "Inferred"} <= ids
    assert all(row["triples"] > 0 for row in payload["sources"])


def test_card_and_404s_are_json() -> None:
    with TestClient(app) as client:
        card = client.get("/api/card/TMDB27205")
        missing_card = client.get("/api/card/NonEsiste")
        missing_film = client.get("/api/film/NonEsiste")
        missing_route = client.get("/api/route-inesistente")
    assert card.status_code == 200 and card.json()["title"] == "Inception"
    for response in (missing_card, missing_film, missing_route):
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/json")
        assert response.json()["detail"]


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
