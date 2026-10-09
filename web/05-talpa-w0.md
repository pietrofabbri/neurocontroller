# 05 - La talpa (tappa W0): cosa esiste, come si usa, cosa manca

*Stato al 9 ottobre 2026 (sera). **Implementato:** gioco a due con B simulato, musica di A, elaborazione
del segnale con parita' verificata, database locale, **flusso del sensore via Web Serial (collegamento,
controllo, calibrazione, gioco, vista dal vivo, scarico della registrazione)**. Il flusso del sensore e'
provato **solo con una porta seriale finta** (`tools/prova_web_sensore.py`): **nessun EEG vero e' ancora
passato da qui.** Non implementato: gamepad, rilevatori di pulizia (`03`, sez. 4.2-4.4).*

## 1. Come si avvia

```
python3 -m neurocontroller serve          # poi apri in Chrome o Edge: http://localhost:8765/
```

- Nessuna installazione oltre a Python (solo libreria standard) e a un browser moderno.
- Il server ascolta **solo su 127.0.0.1**, accetta solo richieste con host `localhost`/`127.0.0.1` e
  scrive in `data/web/giochi.sqlite3` (cartella ignorata da git, `tests/test_repo_hygiene.py`).
  `--data-dir`, `--port`, `--host` cambiano i valori.
- `localhost` e' un contesto sicuro: e' quello che servira' alla Web Serial per il sensore (`02`, sez. 5).

## 2. Decisione WD-4 (9 ottobre 2026)

Richiesta del docente referente: *"facciamolo con la talpa, segui le indicazioni originali... web app
con db che salva i dati di gioco di ognuno"*. Questo **supera WD-2** (solo documentazione) e precisa
V-04: la pagina e' servita da un **piccolo server locale** che tiene un **database SQLite sul computer
stesso**. Cio' che V-04 vieta resta vietato: **nessun dato esce dal computer**, nessun servizio
esterno. Il database contiene solo dati di gioco e codici `Pxx` (V-06); **non** il segnale grezzo
(V-05). Chi gioca puo' essere cancellato con tutte le sue partite (pulsante in "Gestione dei giocatori").

## 2b. Pubblicazione su GitHub Pages (WD-A, 9 ottobre 2026)

`.github/workflows/pages.yml` pubblica **solo `web/app`** (senza `test/`) su GitHub Pages a ogni modifica
di `web/app`, `neurocontroller/`, `tests/`, **dopo** che unittest (Python + Node) e `check_repo` passano.
Indirizzo atteso: `https://pietrofabbri.github.io/neurocontroller/`. **Una tantum, a mano:** Settings -> Pages -> Source = "GitHub Actions" (il token del workflow non puo' attivare Pages). Su https la Web Serial e' utilizzabile (`02`, sez. 5).

Sul sito **non c'e' il server**: la pagina se ne accorge (`/api/health`) e usa un **archivio nel browser**
(`js/archivio_locale.mjs`, `localStorage`), con le stesse regole di validazione del server. Conseguenze:
le partite restano **nel browser di chi gioca**, non sono condivise tra computer, si perdono se si
cancellano i dati del sito (il CSV scaricabile e' la copia); la classifica e' quindi **personale**. Per
una classifica comune a piu' persone serve il server locale su un solo computer. La pagina dice sempre
in quale modo sta lavorando. Prova automatica di entrambi i modi: `tools/prova_web_e2e.py [--statico]`.

## 2c. Il sensore (W1b, prima versione)

Si sceglie "Sensore EEG (USB)" (solo Chrome/Edge su computer, da `localhost` o https). Passi, in `sensore.mjs`:

1. **Avviso** (V-07, V-08): batteria (il browser dice se il computer e' in carica: in tal caso blocca),
   consenso, istruzioni del produttore. Si spunta per procedere.
2. **Collega**: `SerialSource` (Web Serial, 115200 baud) legge **una riga ASCII per campione** (`parseLine`,
   stessa regola di `sources.parse_line`, verificata sugli stessi esempi). Mostra righe valide/scartate e,
   se non arriva nulla, l'ultima riga ricevuta (per capire il formato vero del firmware).
3. **Controllo (6 s, fermo)**: frequenza **misurata** dai tempi di arrivo (avvisa se si discosta del 10% da
   250), segnale piatto, fondo scala, rete a 50 Hz (`quality.mjs`, parita' con `dsp.signal_quality`).
4. **Calibrazione** (protocollo `v1`, 4 blocchi da 60 s: rilassamento, sottrazioni, rilassamento,
   moltiplicazioni; 5 s di assestamento scartati) -> profilo e verdetto come nel Python (d', accuratezza
   bilanciata, soglie `Q_USABLE_*`). **Solo con profilo affidabile si puo' giocare** (V-12).
5. **Vista dal vivo** (anche con profilo debole): stato stimato, punteggio, segnale e bande; **nessun
   punto, nulla salvato nel database**.
6. **Scarica la registrazione**: un valore per riga (compatibile con il replay del Python); i dati grezzi
   restano solo in memoria finche' non si preme il pulsante (V-05). **Non vanno nel repository.**

Limiti: il blocco "movimenti volontari" non c'e' ancora; i rilevatori di battito, salto e raffica non
esistono (`03`); formato del firmware e 250 Hz non sono verificati; la musica esce dagli altoparlanti del
computer (cavi vicini agli elettrodi possono disturbare). `?calib=12` accorcia i blocchi **solo per le prove**.

## 3. Il gioco (R-01 ... R-07)

- Due giocatori, 10 minuti (anche 2 minuti o 20 secondi per prova). **A** guida la talpa con le frecce
  (↓ o spazio = scavo veloce: piu' profondita', ma piu' stordimento se urta) ed evita le rocce.
- Il terreno cambia a caso tra **soffice** (serve B rilassato) e **compatto** (serve B concentrato).
  Piu' lo stato di B e' coerente, piu' la talpa scende (`web/app/js/core.js`: `coerenza`, `velocita`).
  Zona neutra = poca velocita'. **Segnale non pulito o dubbio = nessun punto** (V-11): la prova del
  "mascella" (tasto J) lo verifica.
- **Musica di A -> B** (R-04, R-05): ritmo, suono chiaro/scuro, quante note, registro. Tasti Q/A, W/S,
  E/D, R/F; preset 1 2 3; oppure cursori. E' il solo canale da A a B.
- Con la persona simulata, la mente di B segue la musica (modello giocattolo, **non scientifico**);
  con "Tastiera" B gioca con Z (rilassa) e X (concentra). La scritta **SEGNALE SIMULATO** e' sempre
  visibile (V-10).
- "Sotto il cofano": segnale, bande, indice `E`, rumore, muscoli (valore didattico, `03` sez. 5).

## 4. Catena del segnale (R-08)

`SimulatedSource` (250 Hz, tempo reale) -> Web Worker -> finestra 512, passo 125 -> detrend, Hann, FFT ->
bande -> `E = ln(beta/(alfa+theta))` -> profilo (soglie di disturbo e soglia di stato) ->
classificatore (media di 3, margine 0,25) -> `{stato, punteggio, qualita'}` -> gioco.

- **Parita' con il Python (V-18):** `tools/genera_vettori_web.py` produce `web/app/test/vettori.json`
  (segnali sintetici); `web/app/test/parita.test.mjs` verifica che FFT, bande, rms, rapporto ad alta
  frequenza, `E`, soglie del profilo e sequenza del classificatore coincidano (tolleranza 1e-9).
  `tests/test_web_js.py` controlla anche che il file dei vettori non sia invecchiato.
- **Calibrazione simulata:** due blocchi di circa 60 s (mente a 0 e a 1) producono il profilo; il livello
  (affidabile / debole / non affidabile) segue `d'` come nel Python. La persona "che non reagisce"
  risulta **non affidabile**: il gioco parte comunque (e' simulato) e lo dice.
- **Qualita' `dubbia`** (proposta, da tarare): oltre l'80% del tratto tra valore tipico e soglia di scarto.

## 5. Dati salvati (database)

Tabelle `players`, `games`, `game_series` (schema in `neurocontroller/server.py`). Per ogni partita:
giocatori A e B (codici), sorgente (`simulata` / `sensore`), seme, durata, profondita', rocce urtate,
secondi coerenti / neutri / non coerenti / senza segnale valido, percentuale di segnale valido, punti;
e **una riga al secondo** con profondita', terreno, stato di B, punteggio, qualita' e i **parametri
musicali** attivi (per studiare, dopo, l'effetto della musica: ipotesi, non risultati). API e CSV
(`/api/export.csv`) sono locali.

## 6. File

| Percorso | Ruolo |
|----------|-------|
| `neurocontroller/server.py`, `cli.py serve` | server locale + SQLite |
| `web/app/index.html`, `style.css` | pagina |
| `web/app/js/core.js` | regole del gioco (senza DOM, provate con Node) |
| `web/app/js/dsp.mjs`, `classifier.mjs`, `pipeline.mjs`, `simulata.mjs`, `worker.mjs` | segnale |
| `web/app/js/music.mjs` | musica di A (Web Audio) |
| `web/app/js/serial.mjs`, `quality.mjs`, `sensore.mjs` | sensore: Web Serial, controllo del segnale, flusso di calibrazione |
| `tools/prova_web_sensore.py` | prova del flusso del sensore con porta seriale finta (facoltativa) |
| `web/app/js/main.mjs`, `view.mjs`, `api.mjs`, `archivio_locale.mjs` | schermate, disegno, archivio (server o browser) |
| `web/app/test/` | prove Node (`node --test web/app/test/*.test.*js`) |
| `tools/prova_web_e2e.py` | partita lampo nel browser (richiede Playwright, facoltativo) |

## 7. Cosa manca (in ordine)

1. **Prima sessione con il sensore vero (W1b):** provare il flusso di 2c, annotare formato delle righe,
   frequenza misurata, esito del controllo e della calibrazione; scaricare la registrazione per analizzarla.
2. **Validazione della pulizia (W1c):** rilevatori di battiti, salti, raffiche (`03`, sez. 4) e
   protocollo a blocchi (sez. 6). **Senza questa, con il sensore vero il gioco non e' affidabile.**
3. **Controller di A (gamepad)** e, se serve, i "due gruppi di comandi" di R-03 (`WD-G`).
4. Gemme/bonus (il campo `gems` esiste ma vale 0), audio di eventi (urto, cambio terreno).
5. Giudizio di sessione (`03`, sez. 3, L3): sospendere i punti se il segnale pulito scende sotto il 60%.
