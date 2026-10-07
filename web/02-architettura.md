# 02 - Architettura proposta

*Stato: **proposta**. Nessuna parte e' implementata. Cio' che viene "ereditato" dal Python e' verificato
nel codice del repository; il resto e' progettazione.*

## 1. Flusso dei dati

```
 sensore (EEG)            +  persona simulata        +  file registrato (replay)
       |                         |                            |
   SerialSource            SimulatedSource               ReplaySource      (adattatori: V-19)
       \________________________|____________________________/
                                v
                    interfaccia  Sorgente   -->  blocchi di campioni + tempo di arrivo
                                v
                  [Web Worker: elaborazione]   (V-17)
                     pulizia  -->  finestre di ~2 s  -->  FFT  -->  bande  -->  indice E
                                v                                   |
                     qualita' (pulita / dubbia / scartata)          |
                                v                                   v
                      profilo + classificatore  -->  Stato { rilassato | concentrato | neutro | artefatto,
                                                              punteggio [-1,+1], qualita' }
                                v
   Giocatore A  --tastiera/gamepad-->  [Gioco su canvas]  <--Stato--  (B)
        |                                   |
        +--comandi musica-->  [Motore audio (Web Audio)] --suono--> altoparlanti/cuffie di B
```

Il canale A->B e' la **musica** (R-05): A agisce sul motore audio, B la ascolta e cerca di cambiare
stato; il sistema misura B e passa lo stato al gioco, che assegna i punti (R-07).

## 2. Interfaccia `Sorgente` (il punto di estensione, V-19)

Contratto minimo che ogni adattatore deve rispettare:

| Elemento | Descrizione |
|----------|-------------|
| `avvia()` / `ferma()` | Apre e chiude la sorgente. L'apertura di un sensore reale richiede un gesto dell'utente (selezione della porta). |
| evento `campioni` | Consegna un blocco di valori numerici **nell'ordine di arrivo**, con l'istante di arrivo del blocco (orologio monotono del browser). Il nucleo **non assume** una frequenza esatta. |
| `descrizione` | `{ etichetta, simulata (si/no), frequenzaNominale, bitADC }`. `simulata` alimenta `V-10`. |
| evento `errore` / `chiusa` | Sensore scollegato, porta occupata, formato non riconosciuto. Mai silenzio: l'utente vede cosa e' successo. |

Adattatori previsti:

| Adattatore | Tappa | Nota |
|------------|-------|------|
| `SimulatedSource` | W0 | Porting del simulatore Python (`neurocontroller/sources.py`): persone `tipica`, `debole`, `nulla`. **Va a tempo reale** (il simulatore Python ha richiesto un'accortezza di ritmo: vedi `neurocontroller/live.py`, opzione `pace`): un segnale simulato che arriva "tutto insieme" non si comporta come un sensore. |
| `ReplaySource` | W1 | Riproduce un file registrato dall'utente (CSV locale). Serve ai test, al confronto con il Python e per ripetere una sessione senza la persona. |
| `SerialSource` | W1 | Web Serial: legge le righe dall'Arduino. Vedi sezione 5 e le assunzioni in sezione 4. |
| altri (Bluetooth, WebSocket verso un programma locale) | W4 | Solo per cuffie future; **non progettati ora**, ma l'interfaccia li ammette. |

## 3. Moduli e filo di esecuzione

| Modulo | Compito | Dove gira | Riferimento nel Python |
|--------|---------|-----------|------------------------|
| `sorgenti/` | adattatori di cui sopra | filo principale (I/O) | `sources.py` |
| `dsp/` | detrend, finestra di Hann, FFT radix-2, spettro, potenza per banda | **Web Worker** | `dsp.py` |
| `qualita/` | rilevatori di disturbo, indice di qualita' (vedi `03`) | Web Worker | `dsp.signal_quality`, `profile.is_artifact` |
| `profilo/` | calibrazione per persona, soglia, classificatore con media mobile | Web Worker | `profile.py`, `calibration.py`, `protocol.py` |
| `gioco/` | stato della partita, condizione che cambia, punteggio, ruoli A/B | filo principale (canvas) | - (nuovo) |
| `audio/` | motore musicale controllabile da A | filo principale (Web Audio) | - (nuovo) |
| `ingressi/` | tastiera, gamepad | filo principale | - (nuovo) |
| `ui/` | schermate: avviso sicurezza, collegamento, controllo segnale, calibrazione, partita, risultato | filo principale | `cli.py` (flusso) |
| `esporta/` | scarica CSV/JSON su richiesta (V-05) | filo principale | `calibration.save_session` (colonne) |

Perche' un Web Worker (V-17): la FFT di 512 campioni e' leggera, ma il filo principale e' occupato
da disegno e audio; se un fotogramma tarda, i campioni in arrivo non devono andare persi ne'
arrivare in ritardo di secondi. Il Worker riceve i blocchi e restituisce **stati**, non campioni.

## 4. Cio' che si eredita dal Python (verificato nel codice) e cio' che resta da verificare

Parametri e metodi da riprodurre uguali (V-18), con il file di origine:

| Elemento | Valore | Origine |
|----------|--------|---------|
| Bande (Hz) | delta 1-4, theta 4-8, alfa 8-14, beta 14-30, gamma 30-42 | `dsp.py`, `BANDS` |
| Intervallo "totale" | 1-42 Hz | `dsp.py`, `TOTAL_RANGE` |
| Rete elettrica | 48-52 Hz | `dsp.py`, `MAINS_RANGE` |
| Finestra | ~2 s (512 campioni a 250 Hz), sovrapposta | `dsp.window_size`, `docs/08` sez. 3 |
| Indice di stato | `E = ln( beta / (alfa + theta) )`, rapporto tra bande (indipendente dalla scala) | `docs/08` sez. 3 |
| Punteggio | da -1 (tipico del riposo di *quella persona*) a +1 (tipico del calcolo), media delle ultime 3 finestre pulite; **neutro** entro +-0,25 dalla soglia | `profile.py`, `StateClassifier` |
| Stati | `rilassato`, `concentrato`, `neutro`, `artefatto` | `profile.py` |
| Soglie di qualita' per persona | `RMS_FACTORS`, `HF_FACTORS`, falsi allarmi ammessi 5% | `profile.py` |
| Protocollo di calibrazione | compiti cognitivi `v1`: controllo sensore, rilassamento, concentrazione, movimenti volontari | `protocol.py`, `docs/08` sez. 2 |

**Non verificato (assunzioni ereditate, `docs/08` sezione 6):** formato dei dati dal firmware (una riga
ASCII per campione), 250 campioni al secondo, ADC a 10 bit. Il firmware modificato dagli studenti non e'
nel repository. La versione web deve **misurare** la frequenza reale dall'orologio del browser sui
tempi di arrivo (come fa `neurocontroller check` nel Python) e avvisare se si discosta di oltre il 10%.

**Soglie di qualita' e indice `E`**: euristiche, mai provate su EEG vero. La versione web non le
presenta come risultati.

## 5. Piattaforma browser (da riverificare al momento dell'uso)

| Funzione | Serve a | Supporto (conoscenza al giugno 2026, **da verificare**) |
|----------|---------|----------------------------------------------------------|
| Web Serial API | leggere l'Arduino via USB | Chrome, Edge, Opera su **computer**; non Safari, non Firefox. Solo in **https** o `localhost`. Serve un gesto dell'utente per scegliere la porta. |
| Web Audio API | musica di A, suoni del gioco | tutti i browser moderni; l'audio parte solo dopo un gesto dell'utente |
| Gamepad API | controller di A | tutti i browser moderni; il pad compare dopo il primo tasto premuto |
| Web Worker | elaborazione fuori dal filo principale | tutti |
| Web Bluetooth | cuffie future (W4) | Chrome, Edge, Opera; non Safari, non Firefox |
| File locale (`file://`) | uso senza pubblicare | la lettura via USB **puo' non funzionare**: privilegiare `localhost` o https |

Conseguenza: la pubblicazione su un indirizzo https (per esempio GitHub Pages) e' il modo piu'
semplice per far funzionare il sensore a scuola. Dove pubblicare e' `WD-A`.

## 6. Musica (A -> B): parametri comandabili

Proposta di insieme minimo di parametri che A puo' variare, da tarare con prove: **tempo**, **densita'
di note**, **registro (grave/acuto)**, **luminosita' del timbro**, **presenza di un pulso regolare**.
Le **ipotesi sull'effetto** di questi parametri sullo stato di B vanno trattate come **ipotesi da mettere
alla prova** (`docs/05`, sezione 1: l'osservazione sui suoni acuti riguarda 5 persone senza gruppo di
controllo). L'applicazione dovrebbe poter **registrare** (in locale) quali parametri musicali erano
attivi in ogni finestra, per studiarlo dopo. Attenzione pratica da provare: **cuffie o altoparlanti con
cavi vicini agli elettrodi possono aggiungere disturbo**; la validazione di `03` va fatta **con la
musica accesa**.

## 7. Meccanica di gioco (richiamo di R-07, forma astratta)

- La **condizione** `C(t)` assume a caso i valori *compatto* (richiede B concentrato) e *soffice*
  (richiede B rilassato), con durate casuali.
- Punti per unita' di tempo: crescono quando lo stato di B e' **coerente** con `C(t)`, sono nulli quando
  e' neutro, e **sono sospesi quando lo stato e' `artefatto` o la qualita' e' insufficiente** (`V-11`).
- A evita gli ostacoli e comanda la musica.
- Come si calcola esattamente il punteggio e' la decisione `D4` della roadmap, riproposta come `WD-D`.
