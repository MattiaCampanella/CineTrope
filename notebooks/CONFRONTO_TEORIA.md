# Confronto Accademico: CineTrope vs. Teoria e Pratica del Corso di Semantic Web

> Mappatura sistematica tra l'ontologia **CineTrope v3.1** (`notebooks/build_ontology.ipynb`, `data/ontology/core.ttl`, `data/ontology/core.owl`) e gli argomenti del corso di *Semantic Web* (Prof.ssa Marianna Nicolosi Asmundo, Università di Catania, A.A. 2025/26 — directory `teoria/`).

---

## 1. Copertura delle Lezioni Teoriche (Lezioni 1–12 + Syllabus Parte II–III)

| Lezione | Argomenti teorici | Implementazione concreta in CineTrope |
|---|---|---|
| **L1 — Fondamenti SW & Syllabus** | AAA Slogan, Network Effect, **Open World Assumption (OWA)**, **Non-Unique Naming (No UNA)**, OWL 2 DL ↔ $\mathcal{SROIQ}(\mathcal{D})$, profili OWL 2 (RL), HermiT. | OWA dimostrata empiricamente su `StandardLengthFilm` (`Film ⊓ ¬EpicFilm` lascia non classificato *Insecta*, privo di `runtime`) e su `MultiGenreFilm` (`owl:AllDifferent` sui 17 generi). No UNA gestita con `owl:sameAs` (47 ponti LOD). Reasoning completo HermiT con fallback OWL 2 RL (`cinetrope/reasoning.py`). |
| **L2 — Modello RDF & Ontologie** | Definizione Studer/Benjamins/Fensel, concettualizzazione $(D, R)$, architettura SW end-to-end, **trade-off espressività/complessità**, Explainability & Trust. | Pipeline completa: sorgenti eterogenee (TMDB, Wikidata, DBpedia) → ETL `rdflib` → `store.trig` → FastAPI + grafo di spiegazione vis.js (`04_explanation_construct.rq`). **Trade-off $\mathcal{SROIQ}(\mathcal{D})$ misurato empiricamente**: la rimozione dei costruttori nominali (`owl:oneOf`/`owl:hasKey`) e la riduzione di `AllDifferent` da 100 a 13 film condivisi ha ridotto HermiT da **607s a ~140s** (~85s in Protégé, **4.2× speedup**)! |
| **L3 — Grafo RDF, URI, CURIE & `owl:sameAs`** | Merging via URI condivisi, CURIE/QName, `rdf:type`/`rdf:Property`, **`owl:sameAs`** per unificare identità tra sorgenti (slide 7). | Prefissi puliti (`ct:`, `schema:`, `dbo:`, `dbr:`, `wd:`, `wdt:`, `foaf:`, `skos:`, `dcterms:`). Ponti `owl:sameAs` verso **DBpedia** (`dbr:` per i registi), **Wikidata** (`wd:` per i film Oscar e `ct:OscarBestPicture owl:sameAs wd:Q102427`) e alias locale (`ct:SciFi owl:sameAs ct:ScienceFiction`). |
| **L4 — Letterali, Reificazione, BNode, Named Graph** | Letterali RDF 1.1 tipizzati e con tag lingua, reificazione n-aria vs `rdf:Statement`, Blank Node esistenziali, **Named Graph & Quads**. | Provenienza modellata con **Named Graph** (`:Ontology`, `:TMDB`, `:Wikidata`, `:DBpedia`, `:Inferred`) in `data/generated/store.trig` (alternativa moderna a `rdf:Statement`). BNode nelle restrizioni OWL e atomi SWRL. Rispetto della **OWL 2 Datatype Map** di HermiT (`xsd:integer`, `xsd:decimal`, `xsd:string` al posto di `xsd:date`/`xsd:gYear`). |
| **L5–L6 — Serializzazioni, Collection & DBpedia** | Turtle, RDF/XML, N3/TriG; **RDF Collections (`rdf:List`)** chiuse vs Container aperti; DBpedia. | Esportazione in **Turtle** (`core.ttl`), **RDF/XML** (`core.owl`, nativo Protégé), **N3** (`core.swrl.n3`) e **TriG** (`store.trig`). `rdf:List` usate in tutti gli assiomi OWL 2 e in `swrl:AtomList`. Arricchimento reale da DBpedia (`dbo:birthDate`). |
| **L7 — Linguaggio SPARQL** | 4 forme (`SELECT`, `CONSTRUCT`, `ASK`, `DESCRIBE`), `DISTINCT`, `ORDER BY`, `FILTER`, `OPTIONAL`, `FILTER NOT EXISTS`, **query di metadati/schema**. | Tutte e 4 le forme SPARQL e le query di schema/metadati sono eseguite e verificate in **Cella 10** di `build_ontology.ipynb` e nelle 15 Competency Questions (`data/queries/`). |
| **L8 — SPARQL `CONSTRUCT` & `SERVICE`** | `CONSTRUCT` come traduzione di vocabolari (`VCards`) e regole (`Parenti`), `UNION`, `SERVICE` federato. | `04_explanation_construct.rq` (`CONSTRUCT` + `UNION` + `GRAPH ?source`), `enrich_birthdates_service.rq` (`SERVICE <https://dbpedia.org/sparql>`), più `CONSTRUCT` di proiezione `ct:` → `schema:`/`dbo:` in Cella 10. |
| **L9 — RDFS: Gerarchie & Limiti Espressivi** | `subClassOf`, `subPropertyOf+`, intersezione di `domain`/`range`, limiti di RDFS su intersezione ($C \subseteq A \cap B$) e unione ($A \cup B \subseteq C$). | Gerarchia ricca di proprietà (`hasContributor` ⊒ `directedBy`, `starring`; `contributedTo` ⊒ `directorOf`, `actedIn`; `relatedFilm`; `directSequelOf` ⊑ `sequelOf`). Superamento dei limiti RDFS tramite `owl:equivalentClass` con `owl:intersectionOf` (`RegistaAttore`, `AcclaimedBlockbuster`) e `owl:unionOf` (`NotableFilm`). |
| **L10 — Pattern RDFS & Trappole di Modellazione** | `subPropertyOf rdfs:label` (`ActorsFilms`), `domain`/`range` come inferenza non validazione (`Navi`), **trappola della contaminazione di dominio** (`Navi6`→`NaviFinal`). | Pattern **`NaviFinal`** applicato a `ct:isoCode` (senza dominio) con sottoproprietà `ct:countryIsoCode` (domain `Paese`) e `ct:languageIsoCode` (domain `Lingua`) — zero contaminazione tra classi disgiunte. Pattern **`ActorsFilms`** adattato a OWL 2 DL con `ct:displayTitle a owl:AnnotationProperty ; rdfs:subPropertyOf rdfs:label`. |
| **L11 — `OntoComedySources` & RDFS-Plus** | Riuso ontologie fondazionali (Dublin Core, FOAF, SKOS), `owl:inverseOf`, `owl:SymmetricProperty`. | Metadati `dcterms:*`, allineamenti `foaf:Person`, `skos:prefLabel`/`skos:altLabel`, 5 coppie `owl:inverseOf`, proprietà `owl:SymmetricProperty` e superproprietà inverse (`hasContributor` ↔ `contributedTo`, stile `Library`). |
| **L12 — Verso OWL & Protégé (`Frutta.owl`)** | `owl:equivalentClass`, `owl:equivalentProperty`, export Protégé (`owl:NamedIndividual`). | `ct:Movie owl:equivalentClass ct:Film` + 12 allineamenti esterni `equivalentClass` e 13 `equivalentProperty`. Tutti gli individui tipizzati `owl:NamedIndividual` + export `core.owl` nativo Protégé. |
| **Syllabus Parte II–III — OWL 2 DL ($\mathcal{SROIQ}(\mathcal{D})$) & SWRL** | Costruttori DL, ruoli semplici vs non semplici, consistenza, classificazione, regole SWRL DL-safe. | **16 classi definite** ($\sqcap, \sqcup, \neg, \exists, \forall, \ge n, \text{hasValue}, \text{disjointUnionOf}$, datatype facets), ruoli semplici (`directSequelOf`) vs non semplici (`sequelOf` transitiva), **2 property chain**, **6 regole SWRL non riducibili a OWL 2 DL** + **1 regola `CONSTRUCT` L8** (`coStarsWith` simmetrica). |

---

## 2. Confronto con gli Esercizi Pratici (`teoria/pratica/`)

| Esercizio del corso | Tecnica insegnata | Come CineTrope la riprende e la estende |
|---|---|---|
| `EserciziLezione3/` (`Shakespeare`) | Grafi RDF/RDFS modulari e merging | 5 named graph di provenienza fusi in `store.trig` con `Dataset(default_union=True)`. |
| `EsLlezione4/` (`Reification`, `BNodes`) | BNode esistenziali e reificazione | BNode anonimi nelle espressioni OWL 2; Named Graph al posto di `rdf:Statement` per scalabilità. |
| `EsLezione7/` (`Collection`, `Dataset`, `JamesDean`) | `rdf:List`, `Dataset` TriG, Linked Data cinematografico su DBpedia | `rdflib.collection.Collection` per assiomi OWL/SWRL; dataset TriG; filmografia arricchita con DBpedia + Wikidata. |
| `Esercizilezione8/` (`VCards`, `Parenti`, `Service`) | `CONSTRUCT` mapping/regole, `GRAPH`, `SERVICE` | `04_explanation_construct.rq` + `enrich_birthdates_service.rq` + Cella 10 `CONSTRUCT` verso `schema.org`. |
| `EsempiLezione9/` (`Firm`, `Hospital`, `AllStar`, `Karen`) | `subPropertyOf+`, approssimazioni RDFS, `domain`+`subClassOf` | Gerarchie `hasContributor`/`relatedFilm`/`directSequelOf` + passaggio dalle approssimazioni RDFS ai veri `owl:intersectionOf`/`owl:unionOf`. |
| `EsempiLezione10/` (`ActorsFilms`, `NaviFinal`) | `subPropertyOf rdfs:label`, refactoring anti-contaminazione di dominio | `ct:displayTitle ⊑ rdfs:label` (`AnnotationProperty`) e `countryIsoCode`/`languageIsoCode ⊑ isoCode` (neutra). |
| `EserciziLezione11-12/` (`Library`, `Researcher`, `Frutta.owl`) | Integrazione multi-schema con `inverseOf`/`Symmetric`/`equivalentClass` e Protégé | Integrazione TMDB + Wikidata + DBpedia; `core.ttl` + `core.owl` con `owl:NamedIndividual` e HermiT completo al posto dei `CONSTRUCT` manuali. |

---

## 3. Confine Teorico: Perché servono le 6 Regole SWRL (OWL 2 DL vs. Horn Rules)

OWL 2 DL corrisponde alla logica descrittiva $\mathcal{SROIQ}(\mathcal{D})$, che gode della **tree-model property** (ogni concetto soddisfacibile ammette un modello ad albero): per garantire la decidibilità (`N2ExpTime`-complete), OWL 2 DL **non** permette congiunzioni arbitrarie di ruoli né cicli (triangoli o diamanti) tra variabili distinte.

1. **`RegistaAttore` (OWL 2 DL) vs. `AutoreInterprete` (SWRL `SelfDirectedRoleRule`)**:
   - `RegistaAttore ≡ Regista ⊓ Attore` classifica chi ha diretto *un* film e recitato in *un altro* film (anche diversi).
   - `SelfDirectedRoleRule`: `Film(?f) ∧ directedBy(?f, ?p) ∧ starring(?f, ?p) → AutoreInterprete(?p)` impone che i due archi connettano gli **stessi** `?f` e `?p` (congiunzione di ruoli, non esprimibile in $\mathcal{SROIQ}$).
2. **`FrequentCollaboratorRule`** (ciclo a **diamante a 4 nodi** con `swrl:DifferentIndividualsAtom`): rileva le 28 coppie regista-attore su ≥ 2 film distinti — viola la tree-model property di OWL 2 DL. *(Per `coStarsWith` tra attori usiamo invece una query **SPARQL `CONSTRUCT` L8** unidirezionale e lasciamo a HermiT l'inferenza della direzione inversa tramite **`owl:SymmetricProperty` L11**, evitando un join 4-way su 970 archi `starring`!)*
3. **`SequelDirectorRule`** (**triangolo a 3 nodi** sulla proprietà transitiva `sequelOf`): `sequelOf(?f2, ?f1) ∧ directedBy(?f1, ?d) ∧ directedBy(?f2, ?d) → SequelDirector(?d)` — non esprimibile in OWL 2 DL.
4. **`VersatileAuteurRule`** (join multi-hop su 2 film distinti e 2 generi distinti + chaining su `AcclaimedFilm`).
5. **`SharedCollectionRule`** (con `DifferentIndividualsAtom(?f1, ?f2)`): a differenza di una `propertyChainAxiom` (`partOfCollection ∘ hasPart`), evita i self-loop riflessivi `sameCollectionAs(?f, ?f)` direttamente nel reasoner.
6. **`EnsembleAwardRule`**: dimostra il **chaining** tra 3 classi definite OWL 2 DL (`EnsembleFilm`, `AcclaimedFilm`, `ProfitableFilm`) e una classe target SWRL (`PremioFilm`).

> **Note di ingegneria HermiT (Trade-off Espressività vs. Efficienza — Lezione 2 Slide 22)**:
> - **Niente `swrlb:` dentro `core.ttl`**: HermiT implementa SWRL DL-safe senza *built-in* aritmetici (`swrlb:*`), e solleva `IllegalArgumentException` se ne incontra uno. Per questo `roi` e `birthYear` sono gestiti con **OWL 2 Datatype Restrictions** (`ProfitableFilm`, `BoxOfficeFlop`, `VeteranDirector`).
> - **Scelta nominal-free (`owl:oneOf` / `owl:hasKey` esclusi da `core.ttl`)**: i benchmark di ablazione hanno mostrato che anche un singolo assioma nominale (`owl:oneOf` o `owl:hasKey`) disattiva l'algoritmo *nominal-free* di HermiT (Motik et al., JAIR 2009), facendo salire il reasoning da ~140s (85s in Protégé) a **607s** (**4.2×** più lento). Questa misura empirica è un caso studio perfetto per la discussione orale sul trade-off di $\mathcal{SROIQ}(\mathcal{D})$!

---

## 4. Guida Rapida all'Ispezione in Protégé 5.6+

1. **Apertura**: `File → Open...` → selezionare `data/ontology/core.ttl` (oppure `data/ontology/core.owl`).
2. **Avvio Reasoner**: `Reasoner → HermiT` → `Reasoner → Start reasoner`.
   - Verificare assenza di errori e **0 classi rosse** sotto `owl:Nothing`.
3. **Entities → Classes (vista *Inferred*)**:
   - Osservare la tassonomia inferita: `AcclaimedBlockbuster ⊑ AcclaimedFilm ⊓ Blockbuster`, `PremioFilm`, `StandardLengthFilm` (83 film, escluso *Insecta* per OWA!), `ProfitableFilm` (disgiunta da `BoxOfficeFlop`), `NotableFilm` (`owl:unionOf`), `RegistaAttore` vs `AutoreInterprete`, `VeteranAuteur` (TMDB + DBpedia).
4. **Entities → Object Properties**:
   - Osservare `hasContributor` ↔ `contributedTo`, `directSequelOf ⊑ sequelOf` (selezionare `TMDB1003596` *Avengers: Doomsday* negli Individuals: tra le proprietà inferite compare `sequelOf TMDB299536` *Infinity War* per transitività!), `sameDirectorAs`, `hasFrequentCollaborator` (`ChristopherNolan` ↔ `MichaelCaine`, `CillianMurphy`, `AnneHathaway`), `coStarsWith` (simmetria inferita).
5. **Entities → Data Properties**:
   - Osservare `countryIsoCode` e `languageIsoCode` sotto `isoCode` (pattern `NaviFinal`: nessuna contaminazione di dominio tra `Paese` e `Lingua`).
6. **Window → Tabs → SWRLTab**:
   - Verificare le **6 regole SWRL** abilitate (`swrla:isRuleEnabled = true`) con nome e commento descrittivo.
7. **DL Query Tab** (con HermiT attivo, spuntare *Instances*):
   - `Film and (hasGenre min 3 Genere)` → 61 film (`MultiGenreFilm`)
   - `Film and (not EpicFilm)` → 83 film (`StandardLengthFilm`, prova OWA!)
   - `Regista and (directorOf some AcclaimedBlockbuster)` → registi di blockbuster acclamati
   - `Persona and (hasFrequentCollaborator some Attore)` → registi con collaboratori ricorrenti
