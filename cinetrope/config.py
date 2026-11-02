from __future__ import annotations

from pathlib import Path
from rdflib import Namespace

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
TMDB_PATH = RAW_DIR / "tmdb.json"
FILMS_PATH = RAW_DIR / "films.json"
ONTOLOGY_DIR = DATA_DIR / "ontology"
QUERY_DIR = DATA_DIR / "queries"
GENERATED_DIR = DATA_DIR / "generated"
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

STORE_PATH = GENERATED_DIR / "store.trig"
CATALOG_PATH = GENERATED_DIR / "catalog.trig"
REPORT_PATH = GENERATED_DIR / "build_report.json"

CT = Namespace("http://example.org/cinetrope#")
SWRL = Namespace("http://www.w3.org/2003/11/swrl#")

SOURCE_GRAPHS = {
    "Wikidata": CT.Wikidata,
    "DBpedia": CT.DBpedia,
    "TMDB": CT.TMDB,
    "TvTropes": CT.TvTropes,
    "LocalAnalysis": CT.LocalAnalysis,
    "Derived": CT.Derived,
    "Inferred": CT.Inferred,
}

SOURCE_LABELS = {
    "Wikidata": "Wikidata",
    "DBpedia": "DBpedia",
    "TMDB": "TMDB",
    "TvTropes": "TV Tropes",
    "LocalAnalysis": "Analisi locale",
    "Derived": "Dati derivati",
    "Inferred": "Inferenze",
}

REQUIRED_SOURCES = ("Wikidata", "DBpedia", "TMDB", "Derived", "Inferred")
