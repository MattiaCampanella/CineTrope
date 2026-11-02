"""Importazione e classificazione automatica delle keyword TMDB."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from .config import BASE_DIR
from .etl import slugify

TMDB_API = "https://api.themoviedb.org/3"

def classify_keyword(keyword: dict) -> dict:
    name = str(keyword["name"]).strip()
    try:
        keyword_id = slugify(name)
    except ValueError:
        keyword_id = f"TMDBKeyword{keyword['id']}"
    return {
        "id": keyword_id,
        "label": name,
        "category": "trope",
    }


def _request(path: str, api_key: str, **params) -> dict:
    query = urllib.parse.urlencode({"api_key": api_key, **params})
    request = urllib.request.Request(f"{TMDB_API}{path}?{query}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _film_record(details: dict, credits: dict, keywords: dict) -> dict:
    directors = [
        person["name"]
        for person in credits.get("crew", [])
        if person.get("job") == "Director"
    ]
    cast = [person["name"] for person in credits.get("cast", [])[:10]]
    year = (details.get("release_date") or "0")[:4]
    try:
        record_id = slugify(details["title"])
    except ValueError:
        record_id = f"TMDB{details['id']}"
    return {
        "id": record_id,
        "tmdb_id": details["id"],
        "title": details["title"],
        "year": int(year) if year.isdigit() else None,
        "type": "Film",
        "directors": directors,
        "cast": cast,
        "genres": [slugify(genre["name"]) for genre in details.get("genres", [])],
        "keywords": [classify_keyword(item) for item in keywords.get("keywords", [])],
    }


def fetch_movie(title: str, api_key: str, language: str = "it-IT") -> dict:
    results = _request("/search/movie", api_key, query=title, language=language)["results"]
    if not results:
        raise ValueError(f"TMDB non ha trovato il film {title!r}")
    movie_id = results[0]["id"]
    details = _request(f"/movie/{movie_id}", api_key, language="en-US")
    credits = _request(f"/movie/{movie_id}/credits", api_key, language="en-US")
    keywords = _request(f"/movie/{movie_id}/keywords", api_key)
    record = _film_record(details, credits, keywords)
    record["title"] = results[0].get("title") or record["title"]
    return record


def fetch_discover(
    api_key: str,
    pages: int = 1,
    language: str = "it-IT",
    start_page: int = 1,
) -> list[dict]:
    records = []
    for page in range(start_page, start_page + pages):
        results = _request(
            "/discover/movie",
            api_key,
            language=language,
            sort_by="popularity.desc",
            page=page,
        )["results"]
        for movie in results:
            records.append(fetch_movie(movie["title"], api_key, language))
    return records


def write_records(path: Path, records: list[dict]) -> None:
    path.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def require_api_key() -> str:
    api_key = os.environ.get("TMDB_API_KEY")
    if not api_key:
        env_path = BASE_DIR / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                key, separator, value = line.partition("=")
                if separator and key.strip() == "TMDB_API_KEY":
                    api_key = value.strip().strip("\"'")
                    break
    if not api_key:
        raise RuntimeError("Configura TMDB_API_KEY nel file .env o come variabile d'ambiente.")
    return api_key
