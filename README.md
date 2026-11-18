# CineTrope

Recommender semantico per film. Dato un film, CineTrope propone cinque titoli e
mostra il percorso che li collega: tropi condivisi, regia, cast, generi e named
graph di provenienza.

Il progetto usa **RDF/RDFS, OWL 2, SPARQL, SWRL, `rdflib` e `owlrl`**, con una
demo web basata su **FastAPI (API) e Next.js/React (sito) con vis-network**. Il dataset è materializzato
localmente: la demo non dipende da endpoint pubblici.

## Funzionalità

- Catalogo locale di film e serie TV, con keyword TMDB usate come tropi condivisibili
  (nel catalogo incluso in `data/raw/`: 500 film, 4028 persone e 3331 keyword/tropi).
- Raccomandazioni ordinate da un punteggio combinato, con preset selezionabili: bilanciata, priorità cast, priorità
  regia, priorità tropi e priorità generi.
- Punteggio predefinito:
  - tropo condiviso: **3 punti**;
  - regista condiviso: **2 punti**;
  - attore condiviso: **2 punti**;
  - genere condiviso: **5 punti**.
- Spiegazione visuale come grafo RDF generato con una query `CONSTRUCT`.
- Provenienza su named graph separati: Wikidata, DBpedia, TMDB, dati derivati
  e inferenze.
- Inferenza OWL RL con `owlrl` e regole SWRL con forward chaining.
- Quindici competency questions eseguibili dalla UI, dall'API e dalla CLI.
- Ricerca per titolo, regista, attore, genere, tropo, voto e durata, con autosuggest.
- Classi definite OWL (`AcclaimedFilm`, `Blockbuster`, `EpicFilm`, `ItalianFilm`, ...) calcolate da OWL RL e da regole SPARQL.
- Poster e foto TMDB caricati dal browser (hotlink), con segnaposto se mancano.
- Validazione esplicita di cardinalità e incoerenze che OWL RL non copre.

## Avvio rapido

Requisiti: Python 3.11+ (testato con 3.12), [uv](https://docs.astral.sh/uv/), [Bun](https://bun.sh) e,
solo per scaricare dati e immagini, una chiave [TMDB](https://www.themoviedb.org/settings/api).

### 1. Installazione (una volta sola)

```powershell
uv venv --python 3.12 .venv                  # ambiente Python in .venv
uv pip install -r requirements.txt           # rdflib, owlrl, fastapi, uvicorn, pytest, httpx, tqdm
cd web; bun install; cd ..                   # next, react, react-dom, typescript
Copy-Item .env.example .env                  # poi inserisci TMDB_API_KEY (serve solo per i fetch)
```

### 2. Fetch dei dati (opzionale: `data/raw/` contiene già catalogo, immagini e date di nascita)

```powershell
uv run python scripts/pipeline.py fetch                  # tmdb + images + birthdates, salta quello che c'è già
uv run python scripts/pipeline.py tmdb --discover-pages 25 --target 500   # solo catalogo, keyword, cast e campi extra
uv run python scripts/pipeline.py images                 # solo poster, sfondi e foto -> data/raw/images.json
uv run python scripts/pipeline.py birthdates             # solo date di nascita da DBpedia (senza chiave)
```

`tmdb` e `images` richiedono `TMDB_API_KEY`. Ogni passo salta il lavoro se i dati ci sono già (`--force` per rifarlo);
`images` riprende da dove si era fermato. Dopo un nuovo import va ricostruito lo store, le sole immagini invece si
leggono a runtime, senza rebuild. Se DBpedia non risponde il passo `birthdates` esce con un avviso e l'ETL usa `people.json`. Dettagli in [docs/PROSSIMI_PASSI.md](docs/PROSSIMI_PASSI.md).

### 3. Build dello store RDF (~3 minuti)

```powershell
uv run python scripts/pipeline.py store         # scrive data/generated/store.trig e build_report.json
uv run python scripts/pipeline.py all           # in alternativa: fetch + validate + store in un colpo solo
```

Il passo `store` viene saltato se `store.trig` è più recente di dati, ontologia, query e codice. I log vanno anche in `data/generated/pipeline.log`.

Se manca, `store.trig` viene costruito automaticamente al primo avvio del backend.

### 4. Avvio

```powershell
.\run.ps1                # backend :8000 + sito Next.js :3000, apre il browser
.\run.ps1 -Dev           # Next.js in sviluppo (hot reload)
.\run.ps1 -Rebuild       # ricostruisce lo store RDF prima di avviare
.\run.ps1 -Images        # scarica poster e foto da TMDB prima di avviare
```

Lo script usa `.venv` (o `python` se manca), esegue `bun install` e `bun run build` quando i sorgenti sono cambiati,
costruisce lo store se manca e ferma il backend alla chiusura del sito. Apri <http://127.0.0.1:3000>.

Manuale, senza lo script (due terminali):

```powershell
uv run uvicorn cinetrope.web:app --port 8000      # API JSON (documentazione su /docs)
cd web; bun run build; bun run start               # sito su :3000 (o: bun run dev)
```

Il sito è in `web/` (Next.js 15, React 19, TypeScript, tema OLED in stile Netflix). Parla solo con il backend semantico
FastAPI tramite il rewrite `/api/*` di `web/next.config.mjs` (`CINETROPE_API` cambia l'URL del backend); il backend
resta in Python perché lo stack RDF/OWL/SPARQL lo è.

### CLI

```powershell
python -m cinetrope list
python -m cinetrope recommend TMDB27205
python -m cinetrope explain TMDB27205 TMDB49026
python -m cinetrope cq
python -m cinetrope cq cq3
python -m cinetrope stats
python -m cinetrope --rebuild stats
```

### Test

```powershell
python -m pytest tests -q
```

La suite (29 test in `tests/`) carica lo store reale, quindi richiede alcuni minuti. I test coprono catalogo, regole SWRL, raccomandazioni, grafo di spiegazione,
provenienza, validazione, competency questions, arricchimento DBpedia e rotte web.

## Architettura

```text
data/raw/*.json
    -> ETL (rdflib)
    -> importazione TMDB (data/raw/tmdb.json)
    -> arricchimento DBpedia via SERVICE (materializzato in data/raw/)
    -> named graph delle fonti
    -> relazioni derivate con SPARQL
    -> OWL RL (owlrl)
    -> regole SWRL (motore custom)
    -> data/generated/store.trig
    -> query SPARQL / FastAPI (JSON) / Next.js + React (web/)
```

Componenti principali:

| File | Ruolo |
| --- | --- |
| `cinetrope/etl.py` | Costruisce il dataset RDF e i named graph |
| `cinetrope/reasoning.py` | OWL RL, inferenze e validazione |
| `cinetrope/swrl.py` | Parser ed esecuzione delle regole SWRL |
| `cinetrope/queries.py` | Caricamento, rendering e competency questions |
| `cinetrope/store.py` | API applicativa su catalogo, raccomandazioni e spiegazioni (indici in memoria per le rotte veloci) |
| `cinetrope/search.py` | Query builder con filtri in whitelist e autosuggest |
| `cinetrope/web.py` | API JSON FastAPI |
| `web/` | Sito Next.js + React (OLED, poster, grafo vis-network) |
| `cinetrope/cli.py` | Interfaccia da terminale |
| `cinetrope/tmdb.py` | Client TMDB e importazione delle keyword/cast |
| `scripts/pipeline.py` | Entry point unico: `tmdb`, `images`, `birthdates`, `validate` (TBox), `dataset`, `store`, `fetch`, `all` |
| `run.ps1` | Avvio di backend e sito, con installazione e build al bisogno |

## Ontologia

L'ontologia è modulare: `data/ontology/cinetrope.ttl` è la radice (`owl:imports`) e i
moduli sono in `data/ontology/schema/` (classi, proprietà oggetto/dati, classi
definite, allineamenti a schema.org/DBpedia/Wikidata, assiomi DL-only). Tabelle
complete, property chain e classi definite sono in [docs/ontology.md](docs/ontology.md).
`python scripts/pipeline.py validate` controlla label IT/EN, domain/range, inversi e cicli.
Per i nuovi campi TMDB vedi [docs/PROSSIMI_PASSI.md](docs/PROSSIMI_PASSI.md).

Namespace: `http://example.org/cinetrope#` (`:`).

Classi principali: `OperaAudiovisiva`, `Film`, `SerieTV`, `Persona`, `Regista`,
`Attore`, `Genere`, `Tropo`, `ElementoDescrittivo`, `Fonte`, `MindBender`.

Proprietà principali:

- `hasGenre`, `subGenreOf`;
- `directedBy` / `directorOf`;
- `starring` / `actedIn`;
- `coStarsWith` (simmetrica);
- `hasTrope` / `tropeUsedIn`;
- `hasElement` / `elementUsedIn`;
- `collaboratedWith` (simmetrica), `frequentCollaboration`,
  `hasFrequentCollaborator`;
- proprietà applicative per il grafo di spiegazione: `recommends`,
  `recommendedBecause`, `sharesTropeWith`, `sharesDirectorWith`,
  `sharesActorWith`, `sharesGenreWith`, `assertedIn`.

Scelte di modellazione:

- `SciFi` viene normalizzato in `ScienceFiction` durante l'ETL.
- I generi sono individui di `Genere`, collegati da `subGenreOf`; non viene usato
  punning OWL 2.
- `Film owl:disjointWith SerieTV`.
- `Film` ha almeno un regista e al massimo un anno di uscita. Le restrizioni
  OWL sono affiancate da controlli SPARQL espliciti, perché OWL RL non implementa
  tutte le cardinalità qualificate.
- Le fonti non usano reificazione: la provenienza ordinaria è nel named graph.

## Named graph e provenienza

| Named graph | Contenuto |
| --- | --- |
| `:Ontology` | Schema RDFS/OWL e vocabolario |
| `:Wikidata` | Metadati strutturati delle persone, per esempio date di nascita |
| `:DBpedia` | Metadati biografici delle persone |
| `:TMDB` | Titoli, anni, regia, cast, generi e keyword importati automaticamente |
| `:Derived` | Co-star, collaborazioni e collaborazioni frequenti |
| `:Inferred` | Chiusura OWL RL e conseguenze SWRL |

Esempio di provenienza:

```sparql
SELECT ?source WHERE {
  GRAPH ?source {
    :TMDB27205 :hasTrope :dreams
  }
}
```

## Inferenza e regole

Le regole SWRL sono in `data/ontology/cinetrope-swrl.n3` (N3 perché il parser
Turtle di `rdflib` non supporta variabili) e in
`data/ontology/cinetrope-rules.swrl` per la lettura.

```text
Film(?f) ^ hasTrope(?f, :UnreliableNarrator)
^ hasTrope(?f, :TwistEnding) -> :MindBender(?f)

Persona(?p1) ^ Persona(?p2) ^ collaboratedWith(?p1, ?p2)
^ frequentCollaboration(?p1, ?p2)
-> hasFrequentCollaborator(?p1, ?p2)
```

Poiché SWRL standard non supporta aggregazioni, la collaborazione frequente
(più di tre opere in comune) viene calcolata dall'ETL con
`GROUP BY`/`HAVING`. La regola SWRL crea poi il collegamento tra individui.

Il numero di inferenze e collaborazioni dipende dal catalogo TMDB importato e
viene riportato in `data/generated/build_report.json`.

## Raccomandazioni e spiegazione

La query `03_recommendations.rq` calcola quattro sottoquery indipendenti e le
unisce sul film, evitando prodotti cartesiani. I pesi vengono passati dal
preset scelto nella pagina. A runtime `store.recommendations()` usa però indici in
memoria (stessi punteggi e stesso ordine, circa 7 ms invece di circa 1 s); i file SPARQL
restano per le competency question. La query
`04_explanation_construct.rq` genera il grafo della spiegazione:

- `:recommends` collega il film scelto alla raccomandazione;
- `:sharesTropeWith`, `:sharesDirectorWith`, `:sharesActorWith`,
  `:sharesGenreWith` indicano la dimensione condivisa;
- `:recommendedBecause` collega il film ai tropi che motivano il consiglio;
- `:assertedIn` collega fatti e proprietà al named graph che li asserisce.

Il grafo viene restituito dall'API e disegnato con vis.js.

La pagina `/film/{id}` permette di rigenerare la Top 5 con i
preset `balanced`, `cast`, `director`, `tropes` e `genres`, ad esempio:

```text
/film/TMDB27205?priority=cast
```

## Query e competency questions

Le query commentate sono in `data/queries/`.

| Query | Uso |
| --- | --- |
| `01_films.rq` | Catalogo film |
| `02_shared_tropes.rq` | Film ordinati per tropi condivisi |
| `03_recommendations.rq` | Cinque raccomandazioni con punteggio |
| `04_explanation_construct.rq` | Grafo di spiegazione con `CONSTRUCT` |
| `05_provenance_assertion.rq` | Provenienza di un'asserzione |
| `06_mindbender.rq` | Film inferiti come `MindBender` |
| `07_frequent_collaborators.rq` | Collaboratori frequenti inferiti |
| `08_source_stats.rq` | Triple per named graph |
| `09_genre_hierarchy.rq` | Gerarchia dei generi |
| `10_cq_shared_two_tropes.rq` | Film con almeno due tropi in comune |
| `11_cq_director_trope.rq` | Regista e tropo condivisi |
| `12_cq_co_stars.rq` | Attori che hanno recitato insieme |
| `13_shared_details.rq` | Dettagli condivisi con fonte |
| `14_cq_defined_class.rq` | Individui di una classe definita |
| `15_cq_ancestor_genre.rq` | Generi antenati (property chain) |
| `16_cq_same_director.rq` | Film dello stesso regista (property chain) |
| `17_cq_auteur.rq` | Film d'autore (restrizione annidata) |
| `18_cq_multi_genre.rq` | Film multigenere |
| `19_cq_acclaimed_blockbuster.rq` | Film acclamati e blockbuster |
| `rules/*.rq` | Regole `CONSTRUCT` per le classi definite che OWL RL non calcola |
| `enrich_birthdates_service.rq` | Arricchimento DBpedia con `SERVICE` durante l'ETL |

Le competency questions (cq1-cq15) sono definite in `cinetrope/queries.py` e visibili su
`/queries`; il backend le esegue una per volta su richiesta (`/api/queries/{cq}`). Le query `derive_*.rq` e `detect_frequent_collaboration.rq` sono usate
dall'ETL, non dalla UI.

## Pagine e API

Pagine del sito (Next.js): `/` (home con billboard e rail), `/film/{id}` (raccomandazioni con preset di priorità),
`/explain/{seed}/{rec}` (mappa delle connessioni con provenienza e legami derivati, più il grafo RDF completo con layout che si ferma da solo), `/search` (filtri e autosuggest), `/queries`, `/sources`.

API del backend (`http://127.0.0.1:8000`, documentazione OpenAPI su `/docs`):

| Rotta | Descrizione |
| --- | --- |
| `/api/home` | Hero, rail tematici e statistiche |
| `/api/film/{id}?priority=` | Scheda film e Top 5 con i preset `balanced`, `cast`, `director`, `tropes`, `genres` |
| `/api/card/{id}` | Scheda leggera di un film |
| `/api/search`, `/api/suggest` | Query builder (filtri whitelist) e autosuggest |
| `/api/relation/{a}/{b}` | Legami derivati (property chain, SWRL) |
| `/api/explanation/{a}/{b}` | Grafo di spiegazione (`CONSTRUCT`) |
| `/api/queries`, `/api/queries/{cq}` | Competency questions: elenco e esecuzione singola |
| `/api/sources`, `/api/stats` | Named graph e statistiche |
| `/api/films`, `/api/recommendations/{id}`, `/api/provenance/{film}/{trope}`, `/api/competency-questions` | API originali |
| `/health` | Stato del servizio |

## Struttura del progetto

```text
CineTrope/
├── cinetrope/              # backend Python: ETL, reasoning, store, API
│   ├── config.py  etl.py  queries.py  reasoning.py  swrl.py
│   └── store.py  search.py  tmdb.py  web.py  cli.py
├── data/
│   ├── ontology/           # cinetrope.ttl, schema/*.ttl, regole SWRL
│   ├── queries/            # query SPARQL, rules/ per le classi definite
│   ├── raw/                # films, people, genres, images, dbpedia_birthdates (JSON)
│   └── generated/          # creato dal build, ignorato da git
├── scripts/pipeline.py     # fetch, validazione TBox, ETL, reasoning e store
├── web/                    # sito Next.js (src/app, src/components, src/lib)
├── docs/                   # ontology.md, PROSSIMI_PASSI.md
├── relazione/              # relazione LaTeX
├── tests/
├── run.ps1
├── requirements.txt
└── .env.example
```

## Dati e fonti

Il dataset è materializzato localmente per la demo didattica. I metadati e le
keyword provengono automaticamente da TMDB: non vengono più usate scene
annotate manualmente. Tutte le keyword sono trattate come tropi condivisibili
per aumentare la copertura del recommender; la classe `ElementoDescrittivo`
resta disponibile nell'ontologia per distinguere in futuro ambientazioni,
personaggi, oggetti e contesti non narrativi.

Non viene eseguito scraping a runtime e non vengono chiamati endpoint pubblici
durante la demo. Per riproducibilità, i dati grezzi restano in `data/raw/`.

### Importazione automatica TMDB

Configura la chiave copiando `.env.example` in `.env` e sostituendo il valore:

```powershell
Copy-Item .env.example .env
# Modifica .env e inserisci la tua chiave TMDB_API_KEY
python scripts/pipeline.py tmdb --discover-pages 25 --target 500 --skip-existing
python scripts/pipeline.py store
```

Il file `.env` è escluso da Git. In alternativa è possibile impostare
`TMDB_API_KEY` come variabile d'ambiente.

Il comando reimporta anche i titoli già presenti, scrive `data/raw/tmdb.json`
e rende TMDB la sorgente canonica dei film. Gli ID sono stabilizzati come
`TMDB<id>` per evitare duplicati tra importazioni. I campi legacy `tropes` e
`scenes` vengono rimossi da `data/raw/films.json`.

Ogni keyword TMDB diventa un individuo `:Tropo`, così può contribuire alle
relazioni condivise senza classificazione manuale. Il cast importa i primi 10
attori accreditati per film; registi e generi vengono importati dagli endpoint
TMDB. La chiave viene letta da `.env`, escluso da Git, o dalla variabile
d'ambiente `TMDB_API_KEY`.

### Arricchimento federato con SERVICE

La query `data/queries/enrich_birthdates_service.rq` interroga DBpedia tramite
`SERVICE <https://dbpedia.org/sparql>` per recuperare le date di nascita dei
registi. Lo script ETL materializza il risultato in
`data/raw/dbpedia_birthdates.json`:

```powershell
python scripts/pipeline.py birthdates
python scripts/pipeline.py store
```

Il file materializzato viene caricato nel named graph `:DBpedia`; la demo usa
solo il risultato locale. Se il file non è presente, l'ETL continua a usare le
date già incluse in `data/raw/people.json`.

## Limiti e scelte consapevoli

- La qualità delle raccomandazioni dipende dalla copertura di keyword, cast,
  regia e generi disponibili su TMDB.
- Il punteggio è una euristica trasparente, non un modello appreso.
- Le regole SWRL sono eseguite da un motore custom limitato a `ClassAtom` e
  `IndividualPropertyAtom`; non è un supporto SWRL completo.
- OWL RL non copre tutte le cardinalità OWL 2 DL: la validazione esplicita
  compensa questo limite.
- La demo è ottimizzata per l'uso locale, non per carichi concorrenti.

## Licenza e uso didattico

Progetto realizzato per un corso universitario. I dati sono un sottoinsieme
dimostrativo; prima di riutilizzare o distribuire i dati esterni verificare le
licenze delle fonti originali.
