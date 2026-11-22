# Pipeline di costruzione dell'ontologia CineTrope (v3.1)

> Questo documento descrive la pipeline implementata nel notebook [`build_ontology.ipynb`](build_ontology.ipynb). Per il confronto sistematico con le lezioni teoriche ed esercizi pratici del corso, vedi [`CONFRONTO_TEORIA.md`](CONFRONTO_TEORIA.md).

## Panoramica

L'ontologia OWL 2 DL ($\mathcal{SROIQ}(\mathcal{D})$) di CineTrope è costruita **interamente in Python** con `rdflib` — nessun file Turtle scritto a mano. La pipeline si compone di 12 passi eseguiti nel notebook, che producono cinque artefatti:

| File | Formato | Contenuto |
|---|---|---|
| `data/ontology/core.ttl` | Turtle | Sorgente di verità: TBox completa + ABox + 6 regole SWRL |
| `data/ontology/core.owl` | RDF/XML | Formato nativo OWL API / Protégé |
| `data/ontology/core.swrl.n3` | N3 | Le 6 regole SWRL DL-safe isolate |
| `data/generated/inferred.ttl` | Turtle | Triple inferite da HermiT (classi, proprietà, SWRL) |
| `data/generated/store.trig` | TriG | Dataset named-graph per il backend FastAPI |

---

## Passi della pipeline

### Passo 0 — Dipendenze, path e namespace
Importa `rdflib`, `owlready2`, `SPARQLWrapper`, `tqdm`. Configura i prefissi standard (`ct:`, `owl:`, `rdf:`, `rdfs:`, `xsd:`, `schema:`, `dbo:`, `dbr:`, `wd:`, `wdt:`, `foaf:`, `skos:`, `dcterms:`, `swrl:`, `swrla:`) con `override=True` per evitare collisioni di prefissi (es. `schema1:`).

### Passo 1 — Selezione corpus (top-100 TMDB)
Legge `data/raw/films.json` (500 film) e seleziona i **100 film con popolarità TMDB più alta**.

### Passo 2 — Costruzione TBox OWL 2 DL con `rdflib`
Le funzioni helper (`add_class`, `owl_restriction`, `owl_intersection`, `owl_union`, `owl_complement`, `owl_one_of`, `owl_datatype_restriction`, `add_min_qualified_cardinality`, `add_disjoint_union`, `add_has_key`) costruiscono programmaticamente l'intera TBox:

- **Classi primitive**: `OperaAudiovisiva` (`owl:disjointUnionOf (Film SerieTV)`), `Film`, `SerieTV`, `Persona`, `Regista`, `Attore`, `Genere`, `Tropo`, `Premio`, `Paese`, `Lingua`, `Studio`, `Collezione`, `Fonte`, più `AllDisjointClasses` sulle 10 radici e l'alias `Movie ≡ Film`.
- **Restrizioni universali (`owl:allValuesFrom`)**: condizioni necessarie su `Film` (`directedBy only Regista`, `hasGenre only Genere`, `originCountry only Paese`).
- **Annotazioni**: `ct:displayTitle a owl:AnnotationProperty ; rdfs:subPropertyOf rdfs:label` (pattern L10 `ActorsFilms` conforme a OWL 2 DL).
- **16 Classi Definite (`owl:equivalentClass`)** classificate da HermiT:

| Classe | Costruttore OWL 2 DL | Condizione |
|---|---|---|
| `AcclaimedFilm` | Datatype restriction (`xsd:minInclusive`) | `voteAverage ≥ 7.5` |
| `Blockbuster` | Datatype restriction (`xsd:minInclusive`) | `revenue ≥ 500 000 000 USD` |
| `EpicFilm` | Datatype restriction (`xsd:minInclusive`) | `runtime ≥ 150 minuti` |
| `StandardLengthFilm` | **`owl:complementOf` + `FunctionalProperty`** | `Film ⊓ ¬EpicFilm` *(prova OWA: esclude film senza runtime)* |
| `EnsembleFilm` | Datatype restriction (`xsd:minInclusive`) | `castSize ≥ 7` |
| `ProfitableFilm` | Datatype restriction (`xsd:minInclusive`) | `roi ≥ 2.0` *(disgiunta da `BoxOfficeFlop`)* |
| `BoxOfficeFlop` | Doppia datatype restriction (`minExclusive`/`maxExclusive`) | `budget ≥ 20M ∧ 0 < roi < 1.0` |
| `CollectionFilm` | `owl:someValuesFrom` su classe nominata | `partOfCollection some Collezione` |
| `Auteur` | `owl:someValuesFrom` su classe definita + inversa | `Regista ⊓ (directorOf some AcclaimedFilm)` |
| `VeteranDirector` | Datatype restriction su dati **DBpedia** (`xsd:maxInclusive`) | `Regista ⊓ (birthYear ≤ 1975)` |
| `VeteranAuteur` | Intersezione cross-source (TMDB + DBpedia) | `Auteur ⊓ VeteranDirector` |
| `MultiGenreFilm` | `owl:minQualifiedCardinality` (+ `owl:AllDifferent` sui 17 generi) | `hasGenre min 3 Genere` |
| `AwardedFilm` | `owl:hasValue` (dati **Wikidata**) | `awardCode value "OSCAR_BEST_PICTURE"` |
| `AcclaimedBlockbuster` | `owl:intersectionOf` di classi definite | `AcclaimedFilm ⊓ Blockbuster` |
| `RegistaAttore` | `owl:intersectionOf` di ruoli | `Regista ⊓ Attore` |
| `NotableFilm` | `owl:unionOf` di classi definite | `AcclaimedFilm ⊔ AwardedFilm ⊔ Blockbuster` |

- **Object Properties**:
  - Gerarchie inverse (`hasContributor` ↔ `contributedTo`, `directedBy` ↔ `directorOf`, `starring` ↔ `actedIn`, `partOfCollection` ↔ `hasPart`)
  - Ruoli semplici vs non semplici: `directSequelOf` (`Asymmetric`, `Irreflexive`, `Functional`) ⊑ `sequelOf` (`Transitive`) ↔ `hasSequel` (`Transitive`)
  - Property chain: `sameDirectorAs` (`directedBy ∘ directorOf`), `hasAncestorGenre` (`hasGenre ∘ subGenreOf`)
  - Proprietà simmetriche (`relatedFilm`, `collaboratedWith`, `hasFrequentCollaborator`, `coStarsWith`, `sameCollectionAs`)
- **Data Properties**: funzionali + pattern L10 `NaviFinal` (`countryIsoCode` e `languageIsoCode` sottoproprietà della superproprietà neutra `isoCode` senza dominio).
- **Allineamenti**: tipizzati OWL 2 DL verso `schema.org`, `dbo:`, `wd:`, `wdt:`, `foaf:`.

### Passi 3 e 4 — Fetch Wikidata e DBpedia (+ cache locale)
- **Wikidata**: recupera i vincitori dell'Oscar al Miglior Film (`wdt:P166 wd:Q102427`) e i loro IRI `wd:Q...` (salvati in `data/generated/wikidata_oscar_cache.json`).
- **DBpedia**: recupera `dbo:birthDate` e IRI `dbr:` dei registi del corpus (salvati in `data/generated/dbpedia_directors_cache.json`).

### Passo 5 — Popolamento ABox
Popola 100 film, ~1.019 persone, 17 generi (+ alias `ct:SciFi owl:sameAs ct:ScienceFiction`), tropi, paesi, lingue (`originalLanguage`), studi, collezioni, catene di sequel (`directSequelOf`), tutti tipizzati **`owl:NamedIndividual`**. Dichiara `owl:AllDifferent` in modo mirato sui 17 generi canonici e sui 13 film che condividono regista o franchise. Materializza le 54 coppie di co-star ricorrenti (`coStarsWith`) in una sola direzione via **SPARQL `CONSTRUCT`** (L8), lasciando a HermiT l'inferenza della simmetria (`owl:SymmetricProperty`, L11).

### Passo 6 — 6 Regole SWRL DL-safe (compatibili HermiT + Protégé SWRLTab)
Tutte annotate con `swrla:isRuleEnabled true`, `rdfs:label` e `rdfs:comment`:
1. **`SelfDirectedRoleRule`**: `Film(?f) ∧ directedBy(?f, ?p) ∧ starring(?f, ?p) → AutoreInterprete(?p)` *(congiunzione di ruoli)*
2. **`FrequentCollaboratorRule`**: `Film(?f1) ∧ Film(?f2) ∧ differentFrom(?f1,?f2) ∧ directedBy(?f1,?d) ∧ directedBy(?f2,?d) ∧ starring(?f1,?a) ∧ starring(?f2,?a) → hasFrequentCollaborator(?d, ?a)` *(diamante a 4 nodi)*
3. **`SequelDirectorRule`**: `Film(?f1) ∧ Film(?f2) ∧ sequelOf(?f2,?f1) ∧ directedBy(?f1,?d) ∧ directedBy(?f2,?d) → SequelDirector(?d)` *(triangolo su proprietà transitiva)*
4. **`VersatileAuteurRule`**: `Regista(?d) ∧ directorOf(?d,?f1) ∧ AcclaimedFilm(?f1) ∧ hasGenre(?f1,?g1) ∧ directorOf(?d,?f2) ∧ hasGenre(?f2,?g2) ∧ differentFrom(?f1,?f2) ∧ differentFrom(?g1,?g2) → VersatileAuteur(?d)`
5. **`SharedCollectionRule`**: `Film(?f1) ∧ Film(?f2) ∧ differentFrom(?f1,?f2) ∧ partOfCollection(?f1,?c) ∧ partOfCollection(?f2,?c) → sameCollectionAs(?f1, ?f2)` *(zero self-loop)*
6. **`EnsembleAwardRule`**: `Film(?f) ∧ EnsembleFilm(?f) ∧ AcclaimedFilm(?f) ∧ ProfitableFilm(?f) → PremioFilm(?f)` *(chaining OWL → SWRL)*

### Passi 7–11 — Serializzazione, HermiT, Materializzazione e Verifica SPARQL
- Serializza `core.ttl`, `core.owl` e `core.swrl.n3`.
- Esegue `owlready2.sync_reasoner_hermit(world, infer_property_values=True)` verificando 0 classi inconsistenti.
- Salva tutte le inferenze in `data/generated/inferred.ttl` e ricostruisce `data/generated/store.trig` + `data/generated/build_report.json`.
- Esegue query di verifica coprendo `SELECT`, `ASK`, `CONSTRUCT` (mapping `ct:` → `schema:`/`dbo:`), `DESCRIBE`, property path (`subGenreOf+`), prova OWA e query di metadati TBox.

---

## Come rieseguire la pipeline

```powershell
# Esecuzione completa (notebook + validazione TBox + store.trig)
.\.venv\Scripts\python.exe scripts\pipeline.py all --force

# Oppure eseguendo direttamente il notebook
.\.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute --inplace notebooks\build_ontology.ipynb
```
