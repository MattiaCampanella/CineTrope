# Copilot instructions for CineTrope

## Build, run, and test

### Python environment

The documented Python workflow uses `uv` and Python 3.11+ (3.12 is the tested
version):

```powershell
uv venv --python 3.12 .venv
uv pip install -r requirements.txt
```

The repository also works with the active `python` interpreter when its
dependencies are installed.

### Data and RDF store

The checked-in JSON files under `data/raw/` are the local source data. Build
the materialized RDF/TriG store with:

```powershell
uv run python scripts/pipeline.py store
```

Use `--force` to rebuild even when the generated store appears current. The
single pipeline entry point also supports:

```powershell
uv run python scripts/pipeline.py validate  # validate the ontology/TBox
uv run python scripts/pipeline.py dataset   # ETL only
uv run python scripts/pipeline.py tmdb --discover-pages 25 --target 500
uv run python scripts/pipeline.py images
uv run python scripts/pipeline.py birthdates
uv run python scripts/pipeline.py fetch
uv run python scripts/pipeline.py all
```

The TMDB and image steps require `TMDB_API_KEY` in a local `.env` file or the
environment. Network fetches are optional for normal development; the demo
uses the local materialized data. `store` writes
`data/generated/store.trig`, `build_report.json`, and pipeline logs.

### Backend and frontend

Run the complete local application from the repository root:

```powershell
.\run.ps1
.\run.ps1 -Dev       # Next.js hot reload
.\run.ps1 -Rebuild   # rebuild the RDF store first
.\run.ps1 -Images    # refresh TMDB poster/profile metadata first
```

The script starts FastAPI on port 8000 and Next.js on port 3000. For manual
startup:

```powershell
uv run uvicorn cinetrope.web:app --port 8000
cd web
bun install
bun run build
bun run start
```

Use `bun run dev` instead of `bun run build`/`bun run start` during frontend
development. `web/package.json` currently defines `dev`, `build`, and `start`;
there is no separate frontend lint or test script. `bun run build` is the
frontend validation command and includes the TypeScript/Next build checks.

### Tests

The Python suite loads the real RDF store and can take several minutes:

```powershell
uv run python -m pytest tests -q
```

Run one file or one test node with:

```powershell
uv run python -m pytest tests/test_semantics.py -q
uv run python -m pytest tests/test_web.py::test_film_page_payload -q
```

`pytest.ini` configures the RDFLib deprecation-warning filters. The tests
expect the catalog data and generated store to be available; if the store is
missing, `CineTropeStore.load_or_build()` builds it.

## Architecture

CineTrope is a local semantic movie recommender. Its source data is JSON, but
the application-facing model is an `rdflib.Dataset` serialized as TriG.

1. `scripts/pipeline.py` orchestrates fetching, ontology validation, ETL, and
   store creation.
2. `cinetrope/etl.py` loads the ontology and raw catalog data into named
   graphs, then materializes co-star/collaboration relations with SPARQL.
3. `cinetrope/reasoning.py` merges the non-inferred graphs for two OWL RL
   passes, applies the custom SWRL engine from `cinetrope/swrl.py`, applies
   SPARQL classification rules from `data/queries/rules/`, and stores new
   in-namespace triples in `:Inferred`.
4. `cinetrope/queries.py` loads `.rq` files and supplies the competency
   question registry. `cinetrope/store.py` is the application service layer:
   it loads/builds the store, exposes catalog/recommendation/explanation/
   provenance operations, and maintains in-memory indexes for fast runtime
   recommendation paths.
5. `cinetrope/web.py` exposes the store through FastAPI JSON routes. It loads
   the store once, warms selected expensive queries in the lifespan, and
   serializes the semantic results for the UI.
6. `web/` is a Next.js 15/React 19 frontend. It talks to FastAPI through the
   `/api/*` rewrite in `web/next.config.mjs`; `CINETROPE_API` changes the
   backend URL. The explanation pages render the API's RDF-derived graph with
   the vendored vis-network browser script.

The important named graphs are `:Ontology`, `:LocalAnalysis`, `:TMDB`,
`:DBpedia`, `:Wikidata`, `:Derived`, and `:Inferred`. Ordinary queries use the
dataset's union default graph, while reasoning explicitly merges all graphs
except `:Inferred`. Provenance is represented by the graph containing a
triple, not by RDF reification.

## Repository-specific conventions

- Treat `data/ontology/cinetrope.ttl` as the ontology root. Schema modules
  live under `data/ontology/schema/`; query files under `data/queries/` are
  loaded by name rather than duplicated in Python.
- Keep source facts, derived relations, and inferred consequences in their
  appropriate named graphs. Do not write inferred triples back into source
  graphs or use `:Inferred` as reasoning input.
- OWL RL does not cover every qualified-cardinality or datatype classification
  used here. When a defined class needs aggregation/cardinality or a datatype
  threshold, add/update a SPARQL `CONSTRUCT` rule under
  `data/queries/rules/` and keep the result in the reasoning flow.
- SWRL support is intentionally limited to the custom forward-chaining engine's
  `ClassAtom` and `IndividualPropertyAtom` forms. Aggregations such as frequent
  collaboration counts belong in SPARQL/ETL, with SWRL consuming the
  materialized relation.
- `Dataset(default_union=True)` is intentional. Use explicit `GRAPH` clauses
  when a query must distinguish source/provenance, and use the existing query
  rendering helpers rather than assembling ad-hoc SPARQL in API routes.
- Search filters are a whitelist in `cinetrope/search.py`. New filter fields
  must be added to the appropriate whitelist and escaped/validated there; do
  not interpolate untrusted request values directly into SPARQL.
- Local identifiers are stable `TMDB<id>` values for imported works and
  slugified local names for people and ontology individuals. Preserve this
  convention when adding data or API links. `SciFi` is normalized to
  `ScienceFiction` during ETL.
- Recommendation scoring has four independent dimensions (tropes, director,
  actors, genres). Keep the SPARQL recommendation query, the runtime indexes
  in `store.py`, and the frontend priority presets behaviorally consistent.
- Runtime images are an overlay from `data/raw/images.json` and are hotlinked
  from TMDB's CDN; image refreshes do not require an RDF store rebuild.
- RDFLib SPARQL parsing and store initialization are guarded for concurrency:
  preserve the query lock in `CineTropeStore` and the singleton/initialization
  lock in `cinetrope.web`.
- API errors are JSON responses with HTTP status codes. New routes should
  follow the existing `get_store()` pattern and return the frontend's
  established payload shapes.
- Keep generated outputs in `data/generated/`; change source JSON, ontology,
  query, or Python code instead of hand-editing generated TriG/report files.
