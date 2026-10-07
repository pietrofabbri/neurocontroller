# 03 - Stato attuale rispetto alle richieste originali

Data dell'analisi: **6 ottobre 2026**. Base: contenuto del repository (progetto
GameMaker `game/BLeppo2`) + diario degli studenti (`07-diario-studenti.md`).
Legenda: **Fatto** = verificato nel repository; **Parziale**; **Assente** = non c'e'
nel repository (potrebbe esistere altrove); **Non verificabile** = dipende da
materiale non ancora recuperato.

## 1. Tracciabilita' requisiti -> evidenza

| ID | Richiesta (sintesi) | Stato | Evidenza / nota |
|----|---------------------|-------|-----------------|
| R-01 | Due giocatori cooperativi, punti in 10 minuti | **Assente** | Nel codice non c'e' timer, punteggio, fine partita, ne' un secondo giocatore definito. |
| R-02 | A con controller tradizionale, B con EEG | **Parziale** | B (EEG, via UDP) e' implementato in `obj_player`. Per A esiste solo la tastiera che fa scorrere la strada (`obj_road`, `obj_game`), senza un ruolo dichiarato. |
| R-03 | A: controller 1 (strategia) + controller 2 (supporto a B) | **Assente** | Nessuna distinzione di funzioni. |
| R-04 | B cambia stato mentale in base agli input sonori di A | **Assente** | Il progetto non contiene **nessuna risorsa audio** (zero risorse `GMSound` in `BLeppo2.yyp`). |
| R-05 | La musica e' il canale A->B | **Assente** | Come sopra. |
| R-06 | Terreni soffice/compatto casuali, ostacoli casuali | **Assente** | Esistono `obj_muro` e `Obj_albero` ma **non sono piazzati** in `Room1` e nessun codice li genera. La strada e' un'unica superficie. |
| R-07 | Efficacia di B legata alla coerenza stato mentale/terreno | **Assente** | Nel **gioco** il segnale EEG e' ancora solo un passo di movimento: manca la meccanica terreno/punteggio (tappa M3). Lo "stato" esiste ora **fuori dal gioco** (`neurocontroller/`, vedi R-08). |
| R-08 | EEG -> FFT -> bande -> stati mentali | **Parziale: implementato, non validato su EEG vero** | `neurocontroller/` calcola le bande con la FFT e ricava lo stato rilassato/concentrato **tarato su ogni persona** con compiti cognitivi (`docs/08-calibrazione.md`). Provato solo con segnale **simulato** (circolare: non prova nulla sul cervello). Il `bridge.py` degli studenti e il firmware non sono nel repository. |
| R-09 | MVP incrementale, sempre funzionante | **Fatto (come processo)** | Il diario mostra la sequenza: player -> test EEG -> input -> firmware -> guida -> bridge -> 3 uscite. Il passaggio da `swchords` a `bridge.py` e' un esempio di pivot. |
| R-10 | Risultati online + statistiche; scala di aggiornamenti | **Non verificabile** | Il diario cita una "static web app" (28/04); non e' nel repository. Nel gioco non c'e' alcun salvataggio. |
| R-11 | Responsabile documentazione per ruolo | **Parziale** | Esistono diario e una "GUIDA" (21/04), non recuperata. Il repository ora centralizza la documentazione. |
| R-12 | Scelta critica; gestione di un progetto vero | **Fatto (come processo)** | Vedi diario. In questo repository e' reso esplicito in `05-sicurezza-privacy-etica.md` (limiti scientifici). |
| R-13 | Possibile finanziamento CEN | **Non verificabile** | Dipende da una candidatura esterna; nessun materiale nel repository. |

## 2. Cosa funziona oggi (verificato leggendo il codice)

- Un'auto (`obj_player`) che si sposta di 5 pixel per ogni comando `a` (sinistra),
  `b` (destra) o `g` (su) ricevuto via UDP sulla porta 6510.
- Bordi "Pac-Man", collisione con muri (non presenti in stanza), camera con shake
  predisposto ma mai attivato.
- Strada che scorre quando si tiene premuto il tasto freccia su (`obj_game` +
  `obj_road`).
- **Non e' stato possibile eseguire il gioco in questo ambiente**: tutto cio' che
  precede e' dedotto dalla lettura del codice.

## 3. Che cosa il progetto e' realmente, oggi

Un **prototipo di pipeline** (sensore -> firmware -> bridge -> rete -> gioco) con un
gioco volutamente minimo ("progetto stupido": l'auto) che dimostra l'ultimo anello.
La parte piu' difficile e piu' di valore (portare il segnale EEG da un sensore reale
al gioco) e' **documentata nel diario come risolta**, ma i file che la
dimostrano non sono ancora nel repository.

La meccanica che rende il progetto *il gioco richiesto* (R-01...R-07: stato
mentale -> coerenza con una condizione -> punteggio, con A che aiuta via musica)
**non e' ancora implementata**.

## 4. Divari principali, in ordine di impatto sulla chiusura

1. **Recuperare** bridge, firmware, guida, web app e dati dei test (senza di essi
   la pipeline non e' riproducibile ne' presentabile).
2. **Trasformare il segnale in uno stato** (concentrato/rilassato) e non solo in
   un movimento (R-07, prerequisito di tutto il resto).
3. **Introdurre la meccanica di gioco**: condizione che cambia + punteggio +
   timer da 10 minuti (R-01, R-06, R-07).
4. **Dare un ruolo reale ad A** e alla musica (R-02...R-05).
5. **Salvare i risultati** (R-10), prima in locale, poi eventualmente online.

## 5. Incoerenze e punti che meritano attenzione

- Il documento F1 dice che B si adatta alla musica di A; nel codice **non esiste
  alcun canale** da A verso B. Oggi il sistema e' interamente a senso unico
  (cervello -> gioco).
- `Draw_0.gml` di `obj_player` imposta `image_blend` *dopo* `draw_self()`: l'effetto
  si vede al frame successivo; e' innocuo ma probabilmente non voluto.
- La logica dei bordi e' duplicata (script `ball_walls` e dentro l'evento di rete).
- Il diario si interrompe il 5/05/2026 con una riga "giorno" senza contenuto: gli
  ultimi mesi del lavoro non sono documentati.

## Aggiornamento 07/10/2026 - prova senza sensore con GameMaker

- **Verificato dal docente**: `tools/udp_sim.py send b --count 40` muove l'auto nel gioco aperto in GameMaker (catena Python -> UDP 6510 -> gioco funzionante).
- **Difetto trovato e corretto**: la `demo` con sorgente simulata inviava tutti i comandi in pochi decimi di secondo (il segnale simulato non e' in tempo reale), quindi l'auto riceveva centinaia di pacchetti insieme e non si vedeva nulla. Ora con `--udp` il modo live procede a tempo reale (1 s di segnale = 1 s vero; `LiveRunner(pace=True)`), coperto da test.
- **Richiesta aperta**: movimento dolce (tappa M3b in `docs/04-roadmap-mvp.md`).

## Aggiornamento 08/10/2026 - versione web (solo progettazione)

- **Decisione del docente referente**: la versione web e' un **secondo binario**; il gioco GameMaker non viene toccato (se gli studenti vogliono proseguirlo e' libero); chi cura la documentazione abbandona l'ipotesi di sviluppare ulteriormente GameMaker. Per ora **solo documentazione** in `web/`, nessun codice.
- **Richiesta aggiunta**: una "bella pulizia" del segnale (palpebre, mascella, rete, contatto), perche' il segnale vero e' molto piu' sporco di quello simulato e non e' mai stato provato con il sensore. Progettata in `web/03-pulizia-del-segnale.md` (rilevatori proposti, protocollo di validazione, criteri di accettazione, limiti); **non implementata**.
- Nessun requisito `R-xx` cambia stato: la versione web e' tracciata verso i requisiti in `web/01-decisioni-e-vincoli.md`, sezione 3.
