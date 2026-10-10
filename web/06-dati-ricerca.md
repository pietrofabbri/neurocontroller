# 06 · Dati per la ricerca: dizionario, protocollo di raccolta, limiti

Stato: 10/10/2026, schema del database **v2**, app **W0.2**. Questo documento è scritto per essere letto senza altro contesto: descrive che cosa si raccoglie, perché, con quali unità, quali sono i limiti e che cosa serve prima di pubblicare qualcosa.

Un test automatico (`tests/test_server.py`, classe `DataDictionaryTests`) controlla che **ogni colonna** del database e **ogni valore ammesso** compaiano in questo file tra apici inversi. Se aggiungi una colonna e non la descrivi qui, il test fallisce.

## 1. Che cosa è questo insieme di dati

Il gioco "La talpa" ha due giocatori. **A** guida la talpa con una tastiera o un controller e controlla la musica con tre cursori: è l'unico canale da A verso B. **B** ascolta la musica e prova a portarsi in uno stato rilassato o concentrato, secondo il terreno sotto la talpa. Lo stato di B è stimato da **un solo canale EEG** di un sensore economico (BioAmp EXG Pill con Arduino). Più lo stato di B è coerente con il terreno, più la talpa scende.

Ogni partita produce: una riga riassuntiva (`games`), una serie di un punto al secondo (`game_series`) e, una volta per persona, una scheda anonima (`players`). Non si salva il segnale EEG grezzo (vedi sez. 6).

Domande di ricerca che questi dati permettono di affrontare (tutte esplorative):

1. Una musica più lenta, rada e morbida precede uno stato di B stimato come più rilassato? E il contrario? (`tempo`, `density`, `softness` contro `score_b`.)
2. Quanto tempo di segnale utilizzabile si ottiene con un sensore economico, e da che cosa dipende? (`quality_pct`, `artifact_amp_s`, `artifact_hf_s`, `profile_level`.)
3. L'esperienza di gioco o di musica, l'età, il sonno o la caffeina sono associati alla coerenza o alla qualità del segnale? (`players` e `b_*` contro `coherence_mean`.)
4. C'è un effetto di apprendimento da una partita all'altra della stessa persona?
5. I cursori di A, lasciati andare alla deriva, quanto tempo restano nella zona utile per B? (tempo in cui `coherence` ≥ 0,5 contro la distanza dal terreno.)

Nessuna di queste domande è risolta: il progetto produce i dati, non conclusioni.

## 2. Come si raccolgono i dati

- Sul computer che si usa per giocare: `python3 -m neurocontroller serve` scrive un file SQLite (`data/web/giochi.sqlite3`, ignorato da Git). Il sito pubblicato senza server salva invece nel browser (stessi campi, stesse regole) e permette di scaricare il CSV.
- Esportazione: `/api/export.csv` (una riga per partita, con le schede di A e di B in colonne con prefisso `a_` e `b_`) e `/api/export-series.csv` (tutte le serie, colonna `game_id` per collegarle).
- Persone: solo codici `P01`, `P02`… Mai nomi. Il server e il browser rifiutano ogni altro formato.
- Prima di giocare con il sensore vero **devono avere il consenso registrato sia A sia B** (o chi ne ha la responsabilità, per i minorenni). Il server risponde 409 se manca; il browser blocca prima di collegare il sensore. Con il segnale simulato non serve.
- Le partite con segnale simulato sono marcate `simulata` in `source` e **non vanno mai mescolate** con quelle reali nelle analisi.

## 3. Tabella `players` (una riga per persona, scheda anonima)

Tutte le risposte sono a scelta chiusa: niente testo libero, così non entrano per sbaglio nomi o dati sanitari. Tutte facoltative tranne il consenso per il sensore. "nd" significa "preferisco non dirlo".

| Colonna | Tipo | Valori e significato |
|---|---|---|
| `code` | testo | Codice anonimo `P` + 2 o 3 cifre. Chiave. |
| `created_at` | testo UTC | Quando è stato creato il codice (ISO 8601, `Z`). |
| `age_years` | intero | Età in anni dichiarata alla compilazione della scheda, 5–99. Non si aggiorna da sola: per l'età alla partita usa `created_at` o la data della scheda con cautela. |
| `gender` | testo | `donna`, `uomo`, `altro`, `nd`. Autodichiarato. |
| `handedness` | testo | Mano usata di più: `destra`, `sinistra`, `ambidestra`, `nd`. Rilevante per i controlli di A. |
| `gaming` | testo | Ore settimanali di videogiochi: `mai`, `1-3h`, `4-10h`, `oltre10h`, `nd`. |
| `music_training` | testo | Anni di studio di uno strumento: `nessuna`, `meno2`, `2-5`, `oltre5`, `nd`. Rilevante per chi usa i cursori della musica. |
| `education` | testo | Contesto: `medie`, `superiori`, `universita`, `lavoro`, `altro`, `nd`. |
| `consent` | 0/1 | 1 = consenso registrato. Si può ritirare (torna 0 e gli altri campi del consenso si svuotano). |
| `consent_by` | testo | Chi lo ha dato: `persona` (maggiorenne) o `genitore_tutore` (minorenne). |
| `consent_at` | testo UTC | Quando è stato registrato. |
| `consent_version` | testo | Versione del testo di consenso (data), per sapere quale informativa era valida. |

Cancellare una persona (gestione dei giocatori) cancella anche le sue partite e le sue serie.

## 4. Tabella `games` (una riga per partita)

Unità: secondi (`_s`), metri (`_m`), percentuali 0–100 (`_pct`), frazioni 0–1 dove indicato. I tempi `coherent_s`, `neutral_s`, `incoherent_s`, `artifact_s` sommano la durata effettiva.

**Identificazione e risultato**

| Colonna | Significato |
|---|---|
| `id` | Numero progressivo della partita. |
| `played_at` | Fine della partita, UTC. |
| `player_a`, `player_b` | Codici di chi guida/controlla la musica (A) e di chi dà lo stato mentale (B). |
| `source` | `sensore` (EEG vero) oppure `simulata` (persona finta, tastiera). |
| `seed` | Seme del generatore del mondo: stesso seme, stessi terreni e ostacoli. Permette di rigiocare. |
| `duration_s` | Durata effettiva. |
| `duration_planned_s` | Durata prevista (300 s la partita normale dal 10/10/2026; 60 e 20 s le prove). |
| `depth_m` | Profondità raggiunta. |
| `gems` | Gemme raccolte (80 punti ciascuna). |
| `rocks_hit` | Ostacoli urtati (rocce, massi, mobili, muri). Ogni urto ferma la talpa per ~1,4 s (1,8 s per massi e muri; il doppio in turbo). |
| `score` | Punti: 10 per metro più 80 per gemma. |
| `app_version` | Versione dell'app che ha giocato (le regole cambiano tra versioni: non confrontare senza guardarla). |

**Coerenza di B** (la misura centrale)

| Colonna | Significato |
|---|---|
| `coherent_s` | Secondi con coerenza ≥ 0,5. |
| `neutral_s` | Secondi con coerenza < 0,5 e stato di B "neutro". |
| `incoherent_s` | Secondi con coerenza < 0,5 e stato opposto al terreno. |
| `artifact_s` | Secondi in cui il segnale non era valido (finestra scartata o dubbia): nessun punto. |
| `quality_pct` | Percentuale di tempo con segnale valido: 100 × (1 − `artifact_s` / durata). |
| `coherence_mean` | Coerenza media (0–1) sul tempo con segnale valido. |

**Disturbi** (nuovi nella v2: servono a capire che cosa sporca il segnale)

| Colonna | Significato |
|---|---|
| `artifact_amp_s` | Secondi scartati perché l'ampiezza (RMS) superava la soglia del profilo: tipicamente movimento, battito di ciglia, contatto che balla. |
| `artifact_hf_s` | Secondi scartati perché l'energia sopra i 42 Hz (esclusa la rete a 50 Hz) superava la soglia: tipicamente tensione muscolare di fronte, mascella, collo. Un secondo può contare in tutti e due. |
| `dubious_s` | Secondi di finestre "dubbie" (oltre l'80% della strada tra il valore tipico e la soglia di scarto): non danno punti. |

**Gioco**

| Colonna | Significato |
|---|---|
| `turbo_s` | Secondi di scavo veloce (più profondità, più rischio). |
| `terrain_changes` | Quante volte è cambiato il terreno sotto la talpa. |

**Musica di A** (media sui punti della serie)

| Colonna | Significato |
|---|---|
| `tempo_mean` | Ritmo medio, battiti al minuto (60–140). |
| `density_mean` | Densità media di note (0–1): poche note lunghe ↔ molte note brevi. |
| `softness_mean` | Morbidezza media del timbro (0–1): secco e chiaro ↔ morbido, scuro, con riverbero. |
| `percussion_pct` | Percentuale di tempo con percussioni attive. Le percussioni entrano solo quando l'indice di "focus" della musica supera 0,5 (formula in sez. 7). |

**Sensore e profilo** (vuoti con segnale simulato, tranne dove indicato)

| Colonna | Significato |
|---|---|
| `signal_fs_hz` | Frequenza di campionamento misurata, campioni/s. Con il firmware attuale a 9600 baud è circa 193, non 250: è un limite del collegamento, e le bande vengono calcolate con la frequenza misurata. Con il segnale simulato vale 250. |
| `sensor_format` | `ascii` (righe di testo, 9600 baud) oppure `chords` (pacchetti binari, 115200 baud). |
| `sensor_baud` | Baud rilevato. |
| `profile_level` | Esito della calibrazione: `affidabile`, `debole`, `non affidabile`. Con il sensore si gioca solo con `affidabile`. |
| `profile_dprime` | d′ tra rilassato e concentrato nelle finestre pulite della calibrazione (soglie: affidabile se d′ ≥ 1,5 e accuratezza ≥ 0,80). |
| `profile_accuracy` | Accuratezza bilanciata della calibrazione (0–1). Stimata sugli stessi dati che hanno costruito il profilo: **è ottimistica** (nessuna validazione incrociata). |
| `calib_protocol` | `web-v1-30s` = quattro blocchi da 30 s (rilassamento, sottrazioni, rilassamento, moltiplicazioni; 4 s di assestamento scartati per blocco); `simulata-rapida` = calibrazione sul segnale simulato. Il protocollo del Python (`neurocontroller/protocol.py`) usa 60 s per blocco: i profili non sono confrontabili senza guardare questa colonna. |

**Condizioni di B il giorno della partita** (facoltative, dichiarate da B, nessun dato sanitario)

| Colonna | Significato |
|---|---|
| `b_sleep_h` | Ore di sonno della notte precedente (0–24). |
| `b_caffeine_3h` | 1 = caffè o tè forte nelle ultime 3 ore, 0 = no. |
| `b_fatigue` | Stanchezza percepita, 1 (riposato) – 5 (molto stanco). |

## 5. Tabella `game_series` (un punto al secondo per partita)

Collegata a `games` da `game_id`. Una riga ogni secondo di gioco.

| Colonna | Significato |
|---|---|
| `t` | Secondi dall'inizio. |
| `depth_m` | Profondità in quel momento. |
| `terrain` | Terreno sotto la talpa, cinque livelli: `soffice` (serve B rilassato), `morbido` (un po' rilassato), `medio` (a metà), `duro` (un po' concentrato), `compatto` (concentrato). |
| `state` | Stato di B stimato: `rilassato`, `concentrato`, `neutro`, `artefatto` (segnale non valido). |
| `score_b` | Punteggio continuo di B in [−1, +1]: −1 tipico del riposo della propria calibrazione, +1 tipico del calcolo mentale. È relativo al profilo di quella sessione, **non confrontabile tra persone** senza normalizzare. |
| `quality` | 1 = finestra pulita, 0,5 = dubbia, 0 = scartata. |
| `coherence` | Coerenza 0–1 tra `score_b` e terreno (formula in sez. 7). |
| `tempo` | Ritmo della musica, bpm, in quel secondo. |
| `density` | Densità di note (0–1). |
| `softness` | Morbidezza del timbro (0–1). |
| `reason` | Perché la finestra non era pulita: vuoto (pulita), `ampiezza`, `alta_freq`, `entrambi`, `vicino_soglia` (dubbia). |

## 6. Che cosa NON si raccoglie, e perché

- **Nomi, contatti, classe, scuola, indirizzi**: solo il codice. Età, genere e contesto insieme, in un gruppo piccolo (una classe), possono comunque rendere riconoscibile una persona: vedi sez. 8.
- **Dati sanitari**: nessuna diagnosi, farmaco, condizione neurologica o psicologica. Sonno, caffeina e stanchezza sono abitudini del giorno, dichiarate. Non aggiungere campi sanitari senza una valutazione preliminare del DPO e un'adeguata base giuridica (sono dati di categoria particolare).
- **Segnale EEG grezzo**: non viene archiviato. La pagina lo tiene in memoria durante la sessione e lo scarica come file locale solo con un clic ("Scarica il segnale grezzo"), per analisi tecniche. Quei file **non vanno nel repository**.
- **Audio, video, tracciamento del browser**: nulla.

## 7. Definizioni delle grandezze derivate

- **Coerenza**: `max(0, 1 − |s − b| / 0,6)`, con `s` = `score_b` e `b` = bersaglio del terreno: soffice −0,9; morbido −0,45; medio 0; duro +0,45; compatto +0,9. Piena sul bersaglio, nulla a 0,6 di distanza. Sui livelli intermedi lo stato "neutro" può quindi essere quello giusto.
- **Indice di focus della musica**: `0,45 · ritmo_norm + 0,35 · densità + 0,20 · (1 − morbidezza)`, con `ritmo_norm = (bpm − 60)/80`. Le percussioni sono assenti fino a 0,5; la cassa entra sopra 0,5; il piatto sopra ≈ 0,68. Il tappeto sonoro (pad) c'è solo nella musica calma e sparisce verso 0,65.
- **Deriva dei cursori**: durante la partita i tre cursori di A si spostano da soli, in modo casuale e riproducibile dal seme (`CFG.derivaMusica` = 0,03; 0 la spegne). A deve riportarli dove serve. È una scelta di progetto per rendere il compito di A più impegnativo: va considerata come una condizione sperimentale fissa, non come rumore da ignorare.
- **Finestra EEG**: 512 campioni, passo 125 campioni (≈ 0,5 s a 250 Hz; più lungo a 193 Hz), tolta la tendenza, finestra di Hann, FFT. Bande: δ, θ, α, β, γ. Indice di impegno `E = ln(β / (α + θ))`. Stato = confronto tra `E` mediato su 3 finestre e la soglia del profilo (margine ±0,25).
- **Disturbo**: finestra scartata se RMS > soglia o energia ad alta frequenza > soglia; le soglie vengono dalla calibrazione (fattori 1,5–5 sulla mediana per RMS, 2–20 per l'alta frequenza, scelti perché si scarti non più del 2,5% delle finestre di calibrazione per ciascun criterio).

## 8. Etica, privacy e pubblicazione

Questa sezione è un promemoria operativo, **non una consulenza legale**. Le decisioni spettano al dirigente scolastico, al DPO e, per una pubblicazione, a un comitato etico o a chi ne fa le veci.

1. **Minorenni.** Se partecipano minorenni (anche solo sopra i 14 anni, dove il consenso digitale ha regole specifiche) serve il consenso di chi esercita la responsabilità genitoriale. L'app registra chi lo ha dato (`consent_by`) e quando (`consent_at`, `consent_version`), ma **non sostituisce il modulo firmato**: conserva il modulo a parte, fuori dal database, e non collegarlo ai codici nello stesso luogo.
2. **Informativa.** Prima di raccogliere dati per ricerca va redatta e approvata un'informativa (titolare, finalità, base giuridica, conservazione, diritti, contatto). La versione dell'informativa va scritta in `CONSENT_VERSION` (nel codice) quando cambia.
3. **Anonimizzazione vera.** I codici `Pxx` sono pseudonimi, non anonimi, finché esiste una tabella che li collega a persone. Per pubblicare dati aggregati o a livello di partita: rimuovere `created_at`, `played_at` (tenere solo una data approssimata o l'ordine), `seed`; portare l'età a fasce (per esempio 11–13, 14–15, 16–18, adulti); non rilasciare insieme età, genere, scuola e data in gruppi sotto una soglia (per esempio meno di 5 persone per combinazione).
4. **Conservazione e cancellazione.** I dati stanno solo sul computer che gioca. Ogni persona si cancella con le sue partite. Stabilire un tempo massimo di conservazione e farne un promemoria.
5. **Dichiarare i limiti.** Un sensore economico a canale singolo non misura "il rilassamento": stima un rapporto tra bande, sensibile ai muscoli e ai movimenti. Qualunque pubblicazione deve dire che lo stato di B è una stima non validata clinicamente, che il campione è piccolo e non rappresentativo, e che le soglie sono euristiche.

## 9. Limiti noti e rischi per l'analisi

- **Segnale reale non ancora validato.** Il 09/10/2026 la prima partita reale ha avuto qualità del 45%: i primi 60 s erano puliti (qualità ≈ 0,85), poi il segnale è stato spesso disturbato per il resto della partita. La causa non è accertata (la v1 non registrava il motivo degli scarti); la v2 registra il motivo di ogni scarto per poterla trovare (campi `artifact_amp_s`, `artifact_hf_s`, `reason`).
- **Frequenza di campionamento irregolare.** A 9600 baud le righe arrivano a intervalli non regolari e a circa 193 campioni/s: le bande sono calcolate come se fossero equispaziate. Con il firmware a 115200 baud (`provaBCI.ino`) si ottengono 250 campioni/s regolari. Confrontare partite con `sensor_format` o `signal_fs_hz` diversi richiede cautela.
- **Calibrazione breve.** Blocchi da 30 s danno meno finestre del protocollo da 60 s: d′ e accuratezza sono meno stabili. `profile_accuracy` è calcolata sugli stessi dati del profilo.
- **Misure ripetute.** Più partite della stessa persona non sono indipendenti: usare modelli a effetti misti (persona come effetto casuale) o analizzare per persona. Gli effetti di apprendimento e di stanchezza sono confusi con l'ordine delle partite: registrare l'ordine (`id`, `played_at`) e, se possibile, bilanciarlo.
- **Circolarità.** La musica di A cambia lo stato di B solo se B reagisce; ma A sceglie la musica guardando il terreno e B vede lo stesso schermo. Quindi una correlazione musica–stato può dipendere dal fatto che B **sa** che cosa deve fare (strategia volontaria), non dall'effetto della musica. Per isolare l'effetto servirebbero condizioni in cui B non vede il terreno oppure la musica è assegnata a caso.
- **Soglie non validate su più persone.** Il profilo è individuale; non c'è un confronto con uno standard.
- **Versioni.** Le regole del gioco sono cambiate (durata 600 → 300 s, terreni da 2 a 5 livelli, cursori da 4 a 3, deriva dei cursori). Le partite del 09/10/2026 sono della versione W0.1: nella migrazione il cursore di timbro è stato convertito (`softness` = 1 − luminosità) e i terreni sono i soli `soffice` e `compatto`. Filtrare per `app_version` (vuoto = W0.1).

## 10. Come analizzare (suggerimenti, non risultati)

- Partire dai soli `source = 'sensore'` con `profile_level = 'affidabile'` e `quality_pct` ≥ 60.
- Per ogni persona: correlazione tra la serie `softness`/`tempo`/`density` (ritardata di alcuni secondi) e `score_b`, tenendo conto che `score_b` è relativo al profilo.
- Controllo negativo: stessi calcoli sulle partite `simulata` con persona "nulla" (non reagisce): deve dare nessun effetto; se lo dà, l'analisi è sbagliata.
- Riportare sempre quanti secondi di segnale valido stanno dietro ogni numero.
