from __future__ import annotations

from pathlib import Path

from rdflib import Namespace

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
TMDB_PATH = RAW_DIR / "tmdb.json"
IMAGES_PATH = RAW_DIR / "images.json"
FILMS_PATH = RAW_DIR / "films.json"
ONTOLOGY_DIR = DATA_DIR / "ontology"
SCHEMA_DIR = ONTOLOGY_DIR / "schema"
QUERY_DIR = DATA_DIR / "queries"
RULES_DIR = QUERY_DIR / "rules"
GENERATED_DIR = DATA_DIR / "generated"

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

# Le immagini non vengono scaricate: il browser le carica dal CDN TMDB.
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/"
