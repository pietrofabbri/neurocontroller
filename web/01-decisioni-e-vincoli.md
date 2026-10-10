# 01 - Decisioni e vincoli

## 1. Decisioni gia' prese (docente referente, 7 ottobre 2026)

| ID | Decisione | Conseguenza |
|----|-----------|-------------|
| **WD-1** | La versione web e' un **secondo binario**. Il gioco GameMaker resta com'e'; se gli studenti vogliono proseguirlo, e' libero ed e' supportato dalla documentazione esistente. Chi cura questa documentazione **abbandona l'ipotesi** di sviluppare ulteriormente GameMaker. | Nessuna modifica a `game/BLeppo2/`. Il protocollo UDP e il pacchetto `neurocontroller/` restano il ponte verso GameMaker. |
| **WD-2** | Per ora **solo documentazione** nella cartella `web/`. | **Superata il 9 ottobre 2026 da WD-4**: le tappe sono state avviate. |
| **WD-3** | La **pulizia del segnale** (disturbi di palpebre, mascella, rete, contatto) e' un requisito di prima classe, non un'aggiunta finale. | Documento `03-pulizia-del-segnale.md`; la tappa W1 non si chiude senza la validazione descritta li'. |
| **WD-4** | (9 ottobre 2026) Si realizza la web app **con la talpa**, seguendo le richieste originali, con **database** che salva i dati di gioco di ognuno; il controller vero arriva dopo. | Piccolo **server locale** + SQLite sul computer; V-04 vale ancora (nessun dato esce); dettagli in `05-talpa-w0.md`. |
| **WD-5** | (10 ottobre 2026, dopo la prima partita con il sensore vero) Partita e calibrazione **dimezzate** (5 minuti; blocchi da 30 s); **terreni a 5 livelli** (soffice, morbido, medio, duro, compatto) con stati intermedi di B; piu' ostacoli (roccia, masso, mobile, muro con varco) e **gemme**; musica di A con **al massimo 3 cursori** (ritmo, quante note, morbidezza del timbro), **senza percussioni nel rilassamento**, con **deriva** dei cursori per rendere piu' impegnativo il compito di A; **database orientato alla ricerca** (scheda anonima del partecipante, consenso, metadati del sensore, motivo dei disturbi). | Modifica R-01 (10 → 5 minuti) per richiesta esplicita del docente. Schema v2, app W0.2. Dettagli in `05-talpa-w0.md` e `06-dati-ricerca.md`. Il consenso e' obbligatorio per giocare con il sensore (V-07 resta). Il secondo parametro mentale e' **solo proposto** (`07`). |

## 2. Vincoli (V-xx)

I vincoli valgono per **qualunque** implementazione della versione web, anche scritta da altri.

### 2.1 Fedelta' alle richieste originali

- **V-01 - Tracciabilita'.** Ogni funzione della versione web deve poter essere ricondotta a un
  requisito `R-xx` di `docs/02-richieste-originali.md` (vedi tabella in sezione 3). Cio' che
  non lo e' va dichiarato come estensione.
- **V-02 - Sempre funzionante (R-09).** Ogni tappa lascia l'applicazione utilizzabile e ha un
  criterio di accettazione verificabile. Niente tappe "a meta'".
- **V-03 - Il nucleo del gioco e' la meccanica R-07**: esiste una condizione che cambia nel tempo;
  il punteggio cresce quando lo stato mentale di B e' **coerente** con la condizione; A, con la
  musica, aiuta B. L'ambientazione (auto, talpa, astratta) e' sostituibile (decisione `WD-C`).

### 2.2 Dati, privacy, sicurezza

- **V-04 - Tutto in locale.** Nessun segnale EEG, profilo o risultato lascia il computer: **nessuna
  statistica inviata, nessun servizio esterno di analisi**. (Precisazione WD-4: e' ammesso un server
  **locale** su `127.0.0.1` con un database SQLite sullo stesso computer.) L'elaborazione avviene
  nel browser. (R-10, "risultati online", e' un'estensione futura, vedi `04`, tappa W4, e richiede
  una decisione esplicita sulla protezione dei dati.)
- **V-05 - Nessun dato fisiologico versionato o salvato di nascosto.** Il segnale grezzo e i profili
  esistono in memoria durante la sessione; vengono scritti su disco **solo** con un'azione esplicita
  dell'utente (scaricare un file). Nessun salvataggio automatico nel browser dei dati grezzi.
  Coerente con `docs/05-sicurezza-privacy-etica.md`, sezione 3.
- **V-06 - Nessun nome di persona.** Le persone sono codici `P01`, `P02`... (stesso schema di
  `neurocontroller/profile.py`, `ID_PATTERN`). L'interfaccia rifiuta nomi.
- **V-07 - Minori.** Prima di una sessione con il sensore l'applicazione mostra che serve il
  consenso di chi esercita la responsabilita' genitoriale e che si puo' interrompere in qualsiasi
  momento (`docs/05`, sezioni 2 e 3).
- **V-08 - Sicurezza elettrica visibile.** Prima del collegamento del sensore l'applicazione mostra
  l'avviso di `docs/05`, sezione 2 (computer **a batteria**, scollegato dal caricatore; istruzioni del
  produttore; elettrodi solo su pelle integra). *Il punto va confermato sul manuale del produttore.*

### 2.3 Onesta' scientifica

- **V-09 - Etichetta sempre visibile.** Lo stato di B e' una **stima**; l'interfaccia lo dice
  (formula consigliata in `docs/05`: *"E' un esperimento per capire cosa possiamo e cosa non
  possiamo misurare con un sensore economico"*). Non e' un dispositivo medico.
- **V-10 - Il simulato non si spaccia per vero.** Quando la sorgente e' simulata, la schermata lo
  indica in modo **permanente e ben visibile** (non solo nelle impostazioni). Un risultato ottenuto con
  segnale simulato non e' mai presentato come misura.
- **V-11 - Nessun punto per segnale scadente.** Se la qualita' del segnale e' insufficiente
  (`03`, sezione 5), la partita **non assegna punti basati su quel segnale** e lo dice. In
  particolare un disturbo (mascella serrata) **non deve poter far salire il punteggio** (test
  anti-trucco, `03`, sezione 6).
- **V-12 - Profilo non affidabile = niente partita con il sensore.** Come fa `neurocontroller live`
  (si rifiuta di partire con un profilo non affidabile): in questo caso restano disponibili le
  modalita' simulata e dimostrativa.
- **V-13 - Ricalibrare a ogni sessione.** La stabilita' nel tempo non e' dimostrata
  (`docs/08-calibrazione.md`, sezione 7); l'applicazione non riusa profili di un'altra sessione
  senza dirlo.

### 2.4 Tecnica

- **V-14 - Nessuno strumento di compilazione obbligatorio.** Il nucleo e' fatto di **file statici**
  (HTML, JavaScript, CSS) apribili e pubblicabili cosi' come sono. Chi sviluppa puo' usare strumenti
  suoi, ma il risultato **non li richiede** per essere eseguito.
- **V-15 - Funziona offline.** Il nucleo non carica risorse esterne (font, script, immagini da
  altri siti): a scuola la rete puo' non esserci o essere filtrata. (Eventuali font o librerie sono
  copiati nel repository con la loro licenza, `third_party/`.)
- **V-16 - Sensore: solo dove il browser lo permette.** La lettura via USB richiede un browser
  basato su Chromium su computer, in un indirizzo sicuro (https o `localhost`); vedi `02`, sezione 5.
  Negli altri browser l'applicazione **deve comunque funzionare** in modalita' simulata e da tastiera.
- **V-17 - Il calcolo non deve perdere campioni.** L'elaborazione del segnale non gira nello stesso
  filo dell'interfaccia e dell'audio (`02`, sezione 3): lo scatto del gioco non puo' far perdere
  dati al sensore.
- **V-18 - Parita' con il codice Python.** Il nucleo di elaborazione (FFT, bande, indice, soglie) deve
  dare **gli stessi numeri** del codice Python di riferimento (`neurocontroller/dsp.py`,
  `profile.py`) sugli stessi segnali di prova, entro una tolleranza dichiarata. Si verifica con
  **vettori di riferimento** (segnale in ingresso, numeri attesi) generati dal Python e usati
  dai test della versione web.
- **V-19 - Sorgenti intercambiabili.** Il nucleo conosce solo l'interfaccia `Sorgente` (`02`,
  sezione 2). Aggiungere una cuffia diversa significa scrivere **un adattatore**, non modificare il
  nucleo. Questo e' il vincolo che rende possibili gli sviluppi futuri.
- **V-20 - Lingua e accessibilita'.** Interfaccia in italiano; nessuna informazione affidata al solo
  colore; testi leggibili da una persona di seconda media senza termini tecnici non spiegati.

## 3. Tracciabilita' R-xx -> versione web

| Requisito | Come lo copre la versione web | Tappa |
|-----------|-------------------------------|-------|
| R-01 due giocatori cooperativi, 10 minuti | Partita a due sullo stesso computer, timer, punteggio condiviso | W3 |
| R-02 A tradizionale, B EEG | A: tastiera/gamepad (Gamepad API). B: sensore via USB oppure persona simulata | W0, W1 |
| R-03 A ha due controller | Due gruppi di comandi distinti: strategia di punteggio e supporto a B (musica). *Due dispositivi o due funzioni?* e' `WD-G` | W3 |
| R-04 B capisce come cambiare stato dai suoni di A | Musica generata nel browser, con parametri comandati da A | W2 |
| R-05 la musica e' il canale A->B | Stesso motore audio | W2 |
| R-06 ambientazione (esempio: talpa) | Sostituibile (`WD-C`) | W0 |
| R-07 efficacia legata alla coerenza stato-condizione | Meccanica centrale del gioco (`V-03`) | W0 |
| R-08 EEG -> FFT -> bande -> stati | Porting del codice Python (`V-18`) | W1 |
| R-09 MVP incrementale | `V-02` e piano a tappe | tutte |
| R-10 risultati online e statistiche | Estensione futura, subordinata a `V-04` | W4 |
| R-11 documentazione per ruolo | Questa cartella; nessun nome di studente (`V-06`) | - |
| R-12 scelta critica | Etichette di `V-09`, `V-10`; sezione 6 di `03` | - |

## 4. Cio' che NON e' un vincolo (liberta' lasciate a chi implementa)

Linguaggio di programmazione oltre al JavaScript del browser, uso di librerie di grafica, aspetto
dell'interfaccia, ambientazione, struttura interna dei moduli (purche' valga `V-19`).
