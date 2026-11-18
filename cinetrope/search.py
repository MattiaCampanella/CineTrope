"""Query builder senza LLM e autosuggest: SPARQL generato da una whitelist di campi."""

from __future__ import annotations

import re
import unicodedata

from rdflib import RDF, RDFS, Dataset

from .config import CT
from .reasoning import DEFINED_CLASSES

# Campo -> (proprietà, classe attesa del valore) per i filtri a entità.
ENTITY_FIELDS = {
    "genre": ("hasGenre", "Genere"),
    "director": ("directedBy", "Regista"),
    "actor": ("starring", "Attore"),
    "trope": ("hasTrope", "Tropo"),
}
NUMBER_FIELDS = {"min_rating": ("voteAverage", ">="), "min_runtime": ("runtime", ">=")}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return text.casefold()


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _ident(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", value or ""):
        raise ValueError(f"Identificatore non valido: {value!r}")
    return value


def build_query(filters: dict, limit: int = 50) -> str:
    """Costruisce la SELECT. Ogni valore passa da whitelist/escaping."""
    clauses = ["?film a :Film ; rdfs:label ?title ."]
    if filters.get("title"):
        clauses.append(
            f'FILTER CONTAINS(LCASE(STR(?title)), "{_escape(filters["title"].lower())}")'
        )
    if filters.get("year_from") or filters.get("year_to"):
        clauses.append("?film :releaseYear ?year .")
        if filters.get("year_from"):
            clauses.append(
                f"FILTER (xsd:integer(STR(?year)) >= {int(filters['year_from'])})"
            )
        if filters.get("year_to"):
            clauses.append(
                f"FILTER (xsd:integer(STR(?year)) <= {int(filters['year_to'])})"
            )
    for field, (prop, _) in ENTITY_FIELDS.items():
        if filters.get(field):
            clauses.append(f"?film :{prop} :{_ident(filters[field])} .")
    for field, (prop, op) in NUMBER_FIELDS.items():
        if filters.get(field):
            clauses.append(
                f"?film :{prop} ?{prop} . FILTER (?{prop} {op} {float(filters[field])})"
            )
    if filters.get("class"):
        cls = filters["class"]
        if cls not in DEFINED_CLASSES:
            raise ValueError(f"Classe non ammessa: {cls!r}")
        clauses.append(f"?film a :{cls} .")
    body = "\n  ".join(clauses)
    return (
        "PREFIX : <http://example.org/cinetrope#>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"
        f"SELECT DISTINCT ?film ?title WHERE {{\n  {body}\n}} ORDER BY ?title LIMIT {int(limit)}"
    )


def search(dataset: Dataset, filters: dict, limit: int = 50) -> dict:
    query = build_query(filters, limit)
    rows = [
        {"id": str(row.film).split("#")[-1], "title": str(row.title)}
        for row in dataset.query(query)
    ]
    return {"query": query, "count": len(rows), "results": rows}


class SuggestIndex:
    """Indice di etichette: prefisso > prefisso di parola > sottostringa."""

    TYPES = {
        "Film": "film",
        "Persona": "persona",
        "Genere": "genere",
        "Tropo": "tropo",
    }

    def __init__(self, dataset: Dataset):
        self.items: list[tuple[str, str, str, str]] = []
        for cls, kind in self.TYPES.items():
            for node in set(dataset.subjects(RDF.type, CT[cls])):
                labels = list(dataset.objects(node, RDFS.label))
                if labels:
                    label = str(labels[0])
                    self.items.append(
                        (_fold(label), label, kind, str(node).split("#")[-1])
                    )
        self.items.sort()

    def suggest(self, query: str, limit: int = 8) -> list[dict]:
        needle = _fold(query.strip())
        if not needle:
            return []
        ranked = []
        for folded, label, kind, ident in self.items:
            if folded.startswith(needle):
                rank = 0
            elif any(word.startswith(needle) for word in folded.split()):
                rank = 1
            elif needle in folded:
                rank = 2
            else:
                continue
            ranked.append((rank, folded, label, kind, ident))
        ranked.sort()
        return [
            {"label": label, "kind": kind, "id": ident}
            for _, _, label, kind, ident in ranked[:limit]
        ]
