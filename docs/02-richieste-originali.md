# 02 - Richieste originali (specifica di partenza)

Questo documento fissa **cosa era stato chiesto** al progetto, prima di qualsiasi
valutazione dello stato attuale. Deriva da due fonti scritte dal docente
referente e dagli studenti (vedi `docs/sources/README.md`):

- **[F1]** "Attivita' pomeridiana di Orientamento": la scheda di progetto.
- **[F2]** "Documentazione del prof" (appunti di brainstorming con gli studenti,
  pagina 3/3 di un documento piu' lungo).

Ogni richiesta ha un **ID** (`R-xx`) usato negli altri documenti
(`03-stato-attuale.md`, `04-roadmap-mvp.md`) per la tracciabilita'.
La distinzione tra requisito **vincolante** e **esempio** e' quella dichiarata
dalle fonti: l'esempio della talpa e' un esempio, non una specifica.

## 1. Contesto

- Attivita' pomeridiana di **orientamento** (PNRR, anno scolastico 2025/26),
  con ore svolte da un docente tutor orientatore.
- Il docente ha proposto di sviluppare in autonomia un **videogioco il cui
  controller e' un sensore EEG** (segnale elettrico cerebrale).
- Partecipanti: studenti di una classe quarta dell'a.s. 2025/26 (oggi quinta),
  su base volontaria, organizzati in team con ruoli.
- Calendario: **martedi', 15:00-16:30**, a scuola. Se l'incontro salta per
  impegni curricolari, il gruppo puo' trovarsi comunque.
- Origine dei file: la cartella `Bleppo2` (gioco GameMaker) e il documento
  "progetto gioco mente" sono opera degli studenti; il resto e' del docente.

## 2. Il gioco richiesto

| ID | Richiesta | Natura | Fonte |
|----|-----------|--------|-------|
| R-01 | Videogioco **a due giocatori cooperativi**: obiettivo comune, **fare piu' punti possibile in 10 minuti**. | Vincolante | F1 |
| R-02 | **Giocatore A** usa un controller tradizionale; **Giocatore B** usa un controller **BioAmp EXG Pill + Arduino** (EEG). | Vincolante | F1 |
| R-03 | A dispone di due "controller": **controller 1** per decidere le strategie di punteggio; **controller 2** per supportare B nell'eseguire al meglio i suoi compiti. | Vincolante | F1 |
| R-04 | B, in base agli **input sonori** di A, capisce come **cambiare il proprio stato mentale** (**concentrato / rilassato**). | Vincolante | F1 |
| R-05 | Il canale di comunicazione A->B e' la **musica**: A fa variare la musica per aiutare B a restare nello stato mentale opportuno. | Vincolante (conseguenza di R-04) | F1 |
| R-06 | Esempio di ambientazione ("la talpa"): la talpa scava il piu' a fondo possibile; incontra a caso **terreno soffice o compatto** e **ostacoli casuali (rocce)**. A guida la talpa e le fa evitare gli ostacoli. | Esempio | F1 |
| R-07 | Nell'esempio, B e' efficace sul terreno **compatto se concentrato**, sul terreno **soffice se rilassato**; **piu' lo stato mentale di B e' coerente con il terreno, piu' la talpa va in profondita'**. | Esempio della meccanica centrale | F1 |

**Lettura della meccanica centrale.** Al di la' dell'ambientazione (talpa, auto, ...),
il nucleo e' questo: *esiste una condizione del gioco che cambia nel tempo; il
punteggio cresce quando lo stato mentale di B e' coerente con quella condizione;
A, tramite la musica, aiuta B a raggiungere lo stato giusto, mentre gioca il
proprio ruolo con un controller tradizionale.* Il brainstorming (sezione 4) ha poi
ridotto l'ambientazione a un'auto, mantenendo come obiettivo il gioco cooperativo.

## 3. Elaborazione del segnale e metodo

| ID | Richiesta | Natura | Fonte |
|----|-----------|--------|-------|
| R-08 | Il segnale EEG viene scomposto in bande (**delta, theta, alfa, beta, gamma**) tramite **FFT**; la **variazione di "volume" tra le bande** corrisponde alla variazione di stato mentale. Frequenze di riferimento nella scheda: delta 1-3,9 Hz; theta 4-7,5 Hz; alfa 8-13,9 Hz; beta 14-30 Hz; gamma 30-42 Hz. | Vincolante (base tecnica) | F1 |
| R-09 | **Metodo MVP incrementale**: partire da qualcosa di piccolissimo ma funzionante, ampliarlo ogni settimana con piccoli aggiornamenti, **mantenendo il progetto sempre funzionante**. "Darvi obiettivi chiari e soprattutto piccoli e' la chiave per andare avanti spediti." | Vincolante (metodo) | F1 |
| R-10 | Scala di aggiornamenti indicata come esempio: (1) gioco singolo con numeri casuali da contro-bilanciare con le frecce dx/sx; (2) i numeri diventano una nota che cambia a caso; (3) i numeri casuali sono generati dal controller Arduino; (4) risultati delle partite **salvati online e consultabili da tutti, con statistiche**; (5) audio piu' complesso; (6) grafica della pagina online piu' complessa; (7) i giocatori diventano effettivamente due; (8) gioco online; "e cosi' via". | Esempio di percorso | F1 |

## 4. Brainstorm con gli studenti ([F2])

Dopo aver illustrato l'idea (videogioco con controller EEG in tempo reale), gli
studenti hanno proposto: un **livello unico che si complica nel tempo**, **pixel
art 2D**, e l'idea di **un'auto che accelera e frena**.

Il documento definisce tre livelli di ambizione, dal piu' al meno semplice
(i nomi sono quelli usati nel testo):

1. **"Progetto piu' stupido"** - un cubo che va avanti con la freccetta in avanti;
   senza grafica e audio, "cubo che va e si blocca".
2. **"Progetto stupido"** - l'**auto**.
3. Il gioco completo descritto in F1 (R-01...R-07).

Piano di lavoro sull'analisi (nel testo: "Da mps a ps ->"):

- analizzare la **concentrazione**;
- scegliere le **onde** da usare;
- fare **test sulla concentrazione** con il software Chords (nel testo "swchords")
  su **5 persone**, un solo punto della testa per volta; per ogni test annotare
  il **punto di massimo per ciascuna onda**. Stimoli proposti: matematica,
  memory, partita a scacchi, leggere un testo il piu' velocemente possibile,
  trattenere il respiro, riflessi (gioco "strega comanda colore"), una partita a
  un videogioco mobile, rilassarsi a occhi chiusi con la musica (1 minuto per
  ciascuna traccia). Tempo previsto: circa **3 minuti a persona**, suddivisi tra
  gli stimoli;
- capire, su **una** persona, la **posizione ottimale dell'elettrodo giallo** per
  i vari stimoli (circa mezz'ora per persona);
- **migliorare l'impatto visivo**.

## 5. Organizzazione del team e finalita'

| ID | Richiesta | Fonte |
|----|-----------|-------|
| R-11 | Quattro mansioni, ciascuna con un **responsabile della documentazione** (obiettivo: imparare a "approcciare qualsiasi codice, anche molto complesso"). | F1 |
| R-12 | Finalita' educative dichiarate: promuovere la **capacita' di scelta critica**; **imparare a gestire un progetto non giocattolo e lavorare insieme** ("la cosa piu' difficile e spendibile"). | F1 |
| R-13 | Possibile **finanziamento** per estendere il progetto dalla rete **Contemplative Education Network** ("presentiamo una parte, il resto lo implementiamo se il progetto piace"). | F1 |

Mansioni e attitudini indicate in F1 (i nomi degli studenti sono volutamente
omessi da questo repository):

| Mansione | Attitudini richieste |
|----------|----------------------|
| **Hardware** | matematica, propensione alla meditazione, passione per il funzionamento del pensiero e del cervello, praticita' |
| **Audio design** | passione per il mondo audio e la musica, matematica, capacita' di comunicare con altre persone |
| **Deployment** | voglia di capire come si crea una web app, voglia di creare cose belle da vedere, chiare e intuitive |
| **Game design** | passione per il gaming, capacita' di approssimazione |

## 6. Link utili citati nelle fonti

- Chords (software e firmware del produttore del sensore): <https://chords.upsidedownlabs.tech/>
- Firmware Arduino open source: <https://github.com/upsidedownlabs/Chords-Arduino-Firmware>
- Tutorial "Controlling Video Game Using Brainwaves (EEG)": <https://www.instructables.com/Controlling-Video-Game-Using-Brainwaves-EEG/>
- Rete Contemplative Education Network: <https://contemplative-education.com/>

## 7. Ambiguita' presenti nelle fonti (da non risolvere in silenzio)

- **"Controller 1" e "controller 2" di A** (R-03): le fonti non dicono se siano
  due dispositivi fisici o due funzioni sullo stesso controller.
- **Cosa significhi "concentrato" e "rilassato" in termini di bande** (R-04,
  R-07): non e' specificato; va derivato dai dati dei test (vedi `04-roadmap-mvp.md`,
  decisione D2).
- **Punteggio** (R-01): non e' definito come si calcola, oltre al fatto che nel
  caso della talpa dipende dalla profondita' e dalla coerenza stato mentale/terreno.
- **Scarto tra brainstorm e scheda**: la scheda F1 descrive il gioco a due
  giocatori; il brainstorm F2 ripiega su un'auto a singolo giocatore come
  versione "stupida" per partire. Le due non sono in contraddizione se lette come
  "punto di partenza" e "obiettivo", ed e' cosi' che questo repository le tratta.
- Una frase del testo F2 ("Da mps a ps") e' riportata cosi' com'e': il significato
  esatto non e' stato confermato.

## Variazioni richieste dal docente dopo la stesura originale

Le richieste R-01...R-10 sopra restano come furono scritte. Le variazioni successive sono tracciate in `web/01-decisioni-e-vincoli.md`:

- **10/10/2026 (WD-5)** - R-01: la durata della partita passa da **10 a 5 minuti** (anche la calibrazione e' dimezzata). R-06: i terreni diventano **cinque livelli** con stati intermedi di B, con piu' tipi di ostacolo e gemme. R-04/R-05: la musica ha **al massimo tre cursori** (ritmo, quante note, morbidezza del timbro) e **nessuna percussione nel rilassamento**. Si aggiunge la raccolta di dati per una possibile **ricerca** (scheda anonima del partecipante, consenso).
