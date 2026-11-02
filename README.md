# CineTrope

Recommender semantico per film. Dato un film, CineTrope propone cinque titoli e
mostra il percorso che li collega: tropi condivisi, regia, cast, generi e named
graph di provenienza.

Il progetto usa **RDF/RDFS, OWL 2, SPARQL, SWRL, `rdflib` e `owlrl`**, con una
demo web basata su **FastAPI, Jinja2 e vis.js**. Il dataset è materializzato
localmente: la demo non dipende da endpoint pubblici.

## Funzionalità

- Catalogo locale di film e serie TV, con keyword TMDB usate come tropi condivisibili
  (nell'importazione corrente: 224 film, 1 serie e 1886 keyword/tropi).
- Raccomandazioni ordinate da un punteggio combinato:
- Raccomandazioni con preset selezionabili: bilanciata, priorità cast, priorità
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
- Nove competency questions eseguibili dalla UI, dall'API e dalla CLI.
- Validazione esplicita di cardinalità e incoerenze che OWL RL non copre.

## Avvio rapido

Requisiti: Python 3.11 o superiore.

```powershell
python -m pip install -r requirements.txt
python scripts/build_store.py
uvicorn cinetrope.web:app --reload
```

Apri <http://127.0.0.1:8000>.

Il primo avvio della web app costruisce automaticamente lo store se
`data/generated/store.trig` non esiste. Per forzare la ricostruzione:

```powershell
python scripts/build_store.py
```

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
python -m pytest -q
```

I test coprono catalogo, regole SWRL, raccomandazioni, grafo di spiegazione,
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
    -> query SPARQL / FastAPI / Jinja2 / vis.js
```

Componenti principali:

| File | Ruolo |
| --- | --- |
| `cinetrope/etl.py` | Costruisce il dataset RDF e i named graph |
| `cinetrope/reasoning.py` | OWL RL, inferenze e validazione |
| `cinetrope/swrl.py` | Parser ed esecuzione delle regole SWRL |
| `cinetrope/queries.py` | Caricamento, rendering e competency questions |
| `cinetrope/store.py` | API applicativa su catalogo, raccomandazioni e spiegazioni |
| `cinetrope/web.py` | Rotte FastAPI e template |
| `cinetrope/cli.py` | Interfaccia da terminale |
| `cinetrope/tmdb.py` | Client TMDB e importazione delle keyword/cast |
| `scripts/import_tmdb.py` | Importazione e aggiornamento del catalogo TMDB |
| `scripts/enrich_birthdates.py` | Arricchimento federato delle date di nascita da DBpedia |

## Ontologia

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

- **Punning OWL 2 sui generi**: un genere è sia `owl:Class` (per classificare i
  film) sia individuo di `:Genere` (per `hasGenre` e per la gerarchia).
- `ScienceFiction owl:equivalentClass SciFi`.
- `Film owl:disjointWith SerieTV`.
- `Film` ha almeno un regista e al massimo un anno di uscita. Le restrizioni
  OWL sono affiancate da controlli SPARQL espliciti, perché OWL RL non implementa
  tutte le cardinalità qualificate.
- Le fonti non usano reificazione: la provenienza ordinaria è nel named graph.

## Named graph e provenienza

| Named graph | Contenuto |
| --- | --- |
| `:Ontology` | Schema RDFS/OWL e vocabolario |
| `:Wikidata` | Titoli, anni, regia, cast, generi |
| `:DBpedia` | Metadati biografici delle persone |
| `:TMDB` | Metadati e keyword importati automaticamente |
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
preset scelto nella pagina. La query
`04_explanation_construct.rq` genera il grafo della spiegazione:

- `:recommends` collega il film scelto alla raccomandazione;
- `:sharesTropeWith`, `:sharesDirectorWith`, `:sharesActorWith`,
  `:sharesGenreWith` indicano la dimensione condivisa;
- `:recommendedBecause` collega il film ai tropi che motivano il consiglio;
- `:assertedIn` collega fatti e proprietà al named graph che li asserisce.

Il grafo viene restituito dall'API e disegnato con vis.js.

La pagina `/recommendations/{film}` permette di rigenerare la Top 5 con i
preset `balanced`, `cast`, `director`, `tropes` e `genres`, ad esempio:

```text
/recommendations/TMDB27205?priority=cast
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
| `enrich_birthdates_service.rq` | Arricchimento DBpedia con `SERVICE` durante l'ETL |

Le competency questions sono definite in `cinetrope/queries.py` e visibili su
`/queries`. Le query `derive_*.rq` e `detect_frequent_collaboration.rq` sono usate
dall'ETL, non dalla UI.

## Rotte web

| Rotta | Descrizione |
| --- | --- |
| `/` | Catalogo e selezione del film |
| `/recommendations/{film}` | Cinque raccomandazioni motivate con preset di priorità |
| `/explanation/{seed}/{rec}` | Grafo interattivo della spiegazione |
| `/queries` | Competency questions e risultati |
| `/sources` | Statistiche e ruolo dei named graph |
| `/health` | Stato sintetico del servizio |
| `/api/films` | Catalogo in JSON |
| `/api/recommendations/{seed}` | JSON delle raccomandazioni |
| `/api/explanation/{seed}/{rec}` | JSON del grafo di spiegazione |
| `/api/provenance/{film}/{trope}` | JSON della provenienza |
| `/api/competency-questions` | JSON di tutte le CQ |
| `/api/stats` | Statistiche del knowledge graph |
| `/docs` | Documentazione OpenAPI |

Esempi:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/recommendations/TMDB27205
Invoke-RestMethod http://127.0.0.1:8000/api/explanation/TMDB27205/TMDB49026
```

## Struttura del progetto

```text
CineTrope/
├── cinetrope/
│   ├── config.py
│   ├── etl.py
│   ├── queries.py
│   ├── reasoning.py
│   ├── store.py
│   ├── swrl.py
│   ├── web.py
│   └── cli.py
├── data/
│   ├── ontology/
│   │   ├── cinetrope.ttl
│   │   ├── cinetrope-swrl.n3
│   │   └── cinetrope-rules.swrl
│   ├── queries/
│   ├── raw/
│   └── generated/          # creato dal build, ignorato da git
├── scripts/
│   ├── build_dataset.py
│   ├── build_store.py
│   ├── enrich_birthdates.py
│   └── import_tmdb.py
├── static/
│   ├── style.css
│   ├── app.js
│   ├── graph.js
│   ├── favicon.svg
│   └── vendor/vis-network.min.js
├── templates/
├── tests/
├── requirements.txt
├── .env.example
└── README.md
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
python scripts/import_tmdb.py --discover-pages 10
python scripts/build_store.py
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
python scripts/enrich_birthdates.py
python scripts/build_store.py
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
