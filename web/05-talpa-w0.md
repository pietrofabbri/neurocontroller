# 05 - La talpa (tappa W0): cosa esiste, come si usa, cosa manca

*Stato al 10 ottobre 2026 (app W0.2, schema database v2). **Implementato:** gioco a due (5 minuti, terreni a
5 livelli, 5 tipi di ostacolo/premio), musica di A a 3 cursori con deriva, elaborazione del segnale con
parita' verificata, database locale con scheda del partecipante e consenso (dizionario in `06`), **flusso del
sensore via Web Serial con riconoscimento automatico di formato e baud**. Il 9-10/10/2026 la prima partita con
il sensore **vero** e' stata giocata (vedi sez. 8): il flusso funziona, ma il **segnale e' risultato molto
disturbato** (qualita' 45%). Il flusso e' provato in automatico **solo con una porta seriale finta**
(`tools/prova_web_sensore.py`). Non implementato: gamepad, rilevatori di pulizia (`03`, sez. 4.2-4.4).*

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
2. **Collega**: `SerialSource` (Web Serial) **prova 9600 e 115200 baud** e riconosce da sola il formato
   (pacchetti binari oppure righe di testo con un valore, vedi la fine di questa sezione). Il formato
   binario e' il **protocollo del firmware** (`chords.mjs`), letto dallo sketch `provaBCI.ino` (Upside Down Labs "Chords", scheda UNO-CLONE, 6 canali):
   dopo l'apertura della porta attende 2,2 s (l'Arduino si riavvia), invia `WHORU` (risposta = nome
   scheda), poi `START`; riceve **pacchetti binari** a 250 Hz: `C7 7C`, contatore, 6 x (alto, basso) a 10 bit,
   `01` (16 byte). Il lettore si risincronizza se arrivano byte estranei, conta i pacchetti **persi** dal
   contatore e invia `STOP` alla chiusura. **Verificato sul codice del firmware, non su dati reali.** Si sceglie il
   canale (di solito A0); il controllo mostra la variazione di tutti e sei per aiutare a trovare quello giusto.
   La scheda di Pietro, invece, esegue uno sketch di testo (una riga per campione a 9600 baud): vedi sotto.
3. **Controllo (6 s, fermo)**: frequenza **misurata** dai tempi di arrivo (avvisa se si discosta del 10% da
   250), segnale piatto, fondo scala, rete a 50 Hz (`quality.mjs`, parita' con `dsp.signal_quality`).
4. **Calibrazione** (protocollo `v1` **dimezzato** il 10/10/2026, `web-v1-30s`: 4 blocchi da 30 s: rilassamento,
   sottrazioni, rilassamento, moltiplicazioni; 4 s di assestamento scartati; circa 3 minuti con le pause. Il
   Python usa ancora 60 s per blocco: con meno finestre d' e accuratezza sono meno stabili) -> profilo e verdetto come nel Python (d', accuratezza
   bilanciata, soglie `Q_USABLE_*`). **Solo con profilo affidabile si puo' giocare** (V-12).
5. **Vista dal vivo** (anche con profilo debole): stato stimato, punteggio, segnale e bande; **nessun
   punto, nulla salvato nel database**.
6. **Scarica la registrazione**: un valore per riga (compatibile con il replay del Python); i dati grezzi
   restano solo in memoria finche' non si preme il pulsante (V-05). **Non vanno nel repository.**

Limiti: il Python (`sources.py`) legge ora **sia** le righe ASCII **sia** i pacchetti Chords e riconosce da solo il formato (`--format auto`); il blocco "movimenti volontari" non c'e' ancora; i rilevatori di battito, salto e raffica non
esistono (`03`); formato del firmware e 250 Hz non sono verificati; la musica esce dagli altoparlanti del
computer (cavi vicini agli elettrodi possono disturbare). `?calib=12` accorcia i blocchi **solo per le prove**.

## 3. Il gioco (R-01 ... R-07), come e' dal 10/10/2026

Modifiche richieste dal docente il 10/10/2026 dopo la prima prova con il sensore: durata e calibrazione
**dimezzate**, piu' ostacoli, **terreni intermedi**, musica rifatta, piu' impegno per A. (R-01 originale: 10
minuti; ora la partita e' di **5 minuti**, con prove da 1 minuto e da 20 secondi.)

- **A** guida la talpa con le frecce (↓ o spazio = scavo veloce: piu' profondita', ma piu' stordimento se urta)
  ed evita gli ostacoli; **B** e' la mente che scava.
- **Cinque terreni**, dal piu' soffice al piu' compatto: `soffice` (B rilassato), `morbido` (un po' rilassato),
  `medio` (a meta': lo stato **neutro** e' quello giusto), `duro` (un po' concentrato), `compatto`
  (concentrato). Ogni terreno ha un **bersaglio** sul punteggio di B (−0,9 / −0,45 / 0 / +0,45 / +0,9); la
  coerenza e' `1 − |s − bersaglio| / 0,6`, limitata a 0..1 (`core.js`: `coerenza`, `bersaglioTerreno`). Gli strati
  durano 7-16 m e cambiano sempre (passi di 1 livello spesso, di 2-4 qualche volta). **Segnale non pulito o
  dubbio = nessun punto** (V-11).
- **Ostacoli e premi** (`Mondo.genera`): `roccia` (piccola), `masso` (largo, stordisce di piu'), `mobile`
  (oscilla da una parte all'altra: colpisce dove si trova in quel momento), `muro` con un **varco** di circa due
  talpe, e `gemma` (80 punti, nessuno stordimento). Gli ostacoli sono pochi in superficie e si infittiscono con la
  profondita'.
- **Musica di A -> B** (R-04, R-05), **massimo tre cursori**: **ritmo** (bpm), **quante note** (quantita' e
  lunghezza: poche e lunghe <-> tante e brevi), **suono morbido** (timbro: taglio del filtro, attacco, forma
  d'onda e miscela secco/riverbero insieme). **Nessun preset.** Tasti Q/A, W/S, E/D, o cursori. **Percussioni
  assenti per il rilassamento**: entrano solo se l'indice di focus (`0,45·ritmo + 0,35·densita' + 0,20·secchezza`)
  supera 0,5 (cassa), poi 0,68 (piatto); sotto c'e' un tappeto sonoro (pad) che sparisce verso il focus
  (`music.mjs`: `indiceFocus`, `livelloPercussioni`, `timbro`, `noteDa`). E' il solo canale da A a B.
  **Gli effetti sullo stato di B sono ipotesi, non risultati.**
- **Deriva dei cursori** (`core.js`: `Deriva`, `CFG.derivaMusica`): i tre cursori scivolano da soli, a caso
  (riproducibile dal seme); A deve tenerli dove serve a B mentre guida e schiva. E' la leva per "piu'
  stressogeno per A". `derivaMusica = 0` la spegne. Questa e' una **condizione sperimentale fissa**: va
  registrata come tale nelle analisi.
- Con la persona simulata, la mente di B segue la musica (modello giocattolo, **non scientifico**; timbro
  morbido = rilassante, secco = concentrante); con "Tastiera" B gioca con Z (rilassa) e X (concentra). La scritta
  **SEGNALE SIMULATO** e' sempre visibile (V-10).
- **Disturbi**: quando il segnale non e' pulito la pagina dice **perche'** (ampiezza = movimento/ciglia/contatto;
  alte frequenze = muscoli) e a fine partita mostra quanti secondi per ciascun motivo.
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

Schema **v2** (10/10/2026), con migrazione automatica da v1 (copia di sicurezza `giochi.sqlite3.v1.bak`; le
vecchie partite restano, il timbro `softness` = 1 − vecchia luminosita', i vecchi giocatori risultano senza
consenso). Tre tabelle: `players` (scheda anonima: eta', genere, mano, videogiochi, musica, contesto,
**consenso**), `games` (una riga per partita: risultato, coerenza, disturbi per motivo, musica media, metadati del
sensore e del profilo, condizioni di B: sonno, caffe', stanchezza) e `game_series` (una riga al secondo).
**Con il sensore vero servono il consenso registrato di A e di B** (409 dal server, blocco nella pagina);
il segnale grezzo **non** si archivia. **Dizionario completo, definizioni, limiti ed etica: `06-dati-ricerca.md`**
(un test controlla che ogni colonna sia descritta). API: `GET/POST /api/players`, `PUT /api/players/<codice>`
(scheda e consenso), `/api/games`, `/api/leaderboard`, `/api/export.csv` (partite + schede di A e B),
`/api/export-series.csv`. Tutto locale.

## 6. File

| Percorso | Ruolo |
|----------|-------|
| `neurocontroller/server.py`, `cli.py serve` | server locale + SQLite |
| `web/app/index.html`, `style.css` | pagina |
| `web/app/js/core.js` | regole del gioco (senza DOM, provate con Node) |
| `web/app/js/dsp.mjs`, `classifier.mjs`, `pipeline.mjs`, `simulata.mjs`, `worker.mjs` | segnale |
| `web/app/js/music.mjs` | musica di A (Web Audio): 3 cursori, pad, percussioni oltre soglia, riverbero |
| `web/06-dati-ricerca.md` | dizionario dei dati, etica, limiti, analisi |
| `web/07-secondo-parametro-mentale.md` | proposta del secondo parametro controllabile con la mente |
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
4. Audio di eventi (urto, gemma, cambio terreno).
5. Giudizio di sessione (`03`, sez. 3, L3): sospendere i punti se il segnale pulito scende sotto il 60%.


## 8. Il sensore vero: cosa e' successo il 9-10/10/2026

**Formato.** La scheda di Pietro non esegue `provaBCI.ino`: invia **righe ASCII a 9600 baud** (misurati
~193 campioni/s, non 250; media 537, deviazione standard 24,8 a riposo; a 115200 la porta restituisce solo
zeri). La pagina e `python3 -m neurocontroller serve` provano 9600 e 115200 e riconoscono da sole pacchetti
`C7 7C` o righe di testo; con 9600 baud la frequenza e' quella misurata e **gli intervalli non sono regolari**.
Per i 250 Hz esatti: caricare `provaBCI.ino` (115200 baud). Il Python legge sia ASCII sia Chords (`--format auto`).

**Prima partita con il sensore (9/10/2026, ~23:17).** Qualita' del segnale **45%** (327 s su 600 scartati).
Serie al secondo (media su 30 s): qualita' 0,88 e 0,82 nei primi 60 s, poi tra 0,07 e 0,87 per il resto
della partita (minimo 0,07 tra 210 e 240 s); B riferisce di essersi impegnato per circa 4 minuti e di aver poi
lasciato scadere il tempo facendo altro, con il segnale sempre disturbato. **La causa non e' accertata** e i dati
salvati non bastano a stabilirla (la v1 non registrava il motivo dello scarto e il segnale grezzo non e' stato
salvato). Ipotesi, **nessuna dimostrata**: tensione muscolare di fronte o mascella o movimento durante lo sforzo
(le soglie di scarto vengono da una calibrazione a riposo e da calcoli pacati); contatto degli elettrodi che
cambia; rete a 50 Hz; cavo mosso; irregolarita' del collegamento a 9600 baud. **Da v2 il motivo di ogni scarto e' registrato** (`reason`, `artifact_amp_s`, `artifact_hf_s`): alla prossima partita
si vedra' se prevale l'ampiezza (movimento, ciglia, contatto) o l'alta frequenza (muscoli). In piu' la pagina
offre, a fine partita, **"Scarica il segnale grezzo"** per un'analisi tecnica.

**Che cosa provare** (in quest'ordine, annotando il risultato): (1) computer a batteria, lontano da cavi e
alimentatori; (2) elettrodi: pelle pulita, contatto fermo, cavi fissati, elettrodo di riferimento dietro
l'orecchio su osso (se e' il montaggio previsto dal produttore); (3) durante il calcolo, mascella **lenta**,
fronte distesa, sguardo fermo; (4) ripetere la calibrazione dopo 5 minuti di assestamento; (5) caricare
`provaBCI.ino` per avere 250 Hz regolari; (6) leggere i secondi `artifact_amp_s` contro `artifact_hf_s`.
