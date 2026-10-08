# 04 - Piano a tappe, accettazione, rischi e decisioni aperte

*Stato: **proposta**, nessuna tappa avviata (decisione `WD-2`: per ora solo documentazione).*
Principio (R-09, V-02): **ogni tappa lascia l'applicazione funzionante** e si chiude solo quando il suo
criterio di accettazione e' soddisfatto. Le tappe sono ordinate per dipendenza; non si stimano durate
(non si conoscono i tempi reali del gruppo). Dimensioni: **S** (un incontro), **M** (due-tre), **L** (piu' di tre).

## 1. Tappe

| Tappa | Obiettivo | Accettazione (verificabile) | Dipende da | Dim. |
|-------|-----------|------------------------------|------------|------|
| **W0** | **[FATTA 9/10/2026, vedi `05-talpa-w0.md`; resta da provare a mano una partita da 10 minuti]** **Gioco a due senza sensore.** Pagina statica con `SimulatedSource` (tipica / debole / nulla, a tempo reale), gioco con condizione che cambia (V-03), punteggio, A con la tastiera, musica di A. Etichetta "simulato" permanente (V-10). | Apribile da browser senza installare nulla; una partita completa da 10 minuti produce un punteggio; con "persona nulla" il punteggio **non** cresce (V-11); i test del nucleo passano nel browser. | - | M |
| **W0-demo** | **Modalita' dimostrativa** per chi non ha il sensore (per esempio le scuole medie): un controllo manuale al posto di B, spiegazioni di pochi secondi, partita breve. | Si capisce in 60-90 secondi cosa fa ognuno dei due giocatori, **senza** spiegazioni orali. | W0 | S |
| **W1a** | **Nucleo di elaborazione con parita'.** FFT, bande, `E`, classificatore, calibrazione (protocollo `v1`) in un Web Worker. | Sui **vettori di riferimento** generati dal Python (V-18) i numeri coincidono entro la tolleranza dichiarata; la calibrazione con `SimulatedSource` da' gli stessi verdetti del Python (tipica usabile, debole non usabile, nulla non affidabile). | W0 | M |
| **W1b** | **Sensore vero via USB** (`SerialSource`) e controllo iniziale L1, con misura della frequenza reale. | Con il sensore collegato, un utente non esperto arriva al semaforo verde seguendo le istruzioni a schermo; formato diverso dal previsto -> messaggio chiaro, non blocco. Dichiarate le assunzioni verificate (`02`, sez. 4). | W1a; hardware; formato del firmware | M |
| **W1c** | **Pulizia del segnale** (`03`): rilevatori 4.2-4.4, indicatore di qualita', sospensione dei punti. | Criteri 1-5 di `03`, sezione 6, raggiunti su **almeno 5 persone** e **2 giorni**; test anti-trucco superato. Se **non** raggiunti: la tappa non si chiude e si documenta il risultato negativo. | W1b; sessioni vere | L |
| **W2** | **Musica A->B** con parametri comandabili e registrazione locale dei parametri attivi per finestra. | A cambia almeno 3 parametri in tempo reale; la musica non scatta mentre il Worker elabora; il registro locale ha i parametri per finestra. | W0 | M |
| **W3** | **Ruoli completi e partita da 10 minuti.** A con due gruppi di comandi (R-03), timer, punteggio finale, salvataggio **locale** (scarico di un CSV senza dati personali). | Una partita completa a due (R-01) produce una riga di risultato scaricabile; la sospensione dei punti per qualita' scarsa e' visibile. | W0, W2; `WD-G` | M |
| **W4** | **Estensioni**: adattatori per altre cuffie (V-19), risultati online con statistiche (R-10) **solo** dopo decisione esplicita sulla protezione dei dati (V-04), partita su due computer. | Da definire quando si arriva qui. | W3 | L |

**Percorso minimo per mostrare qualcosa:** W0 -> W0-demo. Funziona **anche senza sensore e senza
risolvere il problema scientifico**: e' la parte che si puo' presentare per prima, dichiarandola simulata.

## 2. Rischi

| ID | Rischio | Probabilita' / impatto | Mitigazione |
|----|---------|------------------------|-------------|
| **WR-1** | Il segnale vero e' troppo sporco e `E` non separa rilassato e concentrato con un canale frontale. | **Alta** probabilita', **alto** impatto sul gioco con il sensore. Indipendente dal web. | W0 funziona senza sensore; `03` sez. 6-7: il risultato negativo e' valido e va riportato; test del confondente; provare indici alternativi. |
| **WR-2** | Il firmware ha un formato diverso (binario, piu' colonne, frequenza diversa). | Media / medio | W1b misura e avvisa; parser aggiuntivo; recuperare il firmware (`firmware/README.md`). |
| **WR-3** | Web Serial non disponibile nel browser della scuola. | Media / medio | V-16: modalita' simulata e da tastiera sempre disponibile; pubblicazione su https; computer con Chrome o Edge dedicato. |
| **WR-4** | La rete della scuola filtra l'indirizzo della pubblicazione. | Media / medio | V-15 (offline); copia locale su `localhost`. |
| **WR-5** | Un disturbo "vince" la partita (la mascella fa punti). | Media / alto (invalida il significato del gioco) | V-11, test anti-trucco in `03`. |
| **WR-6** | La musica nelle cuffie disturba il sensore. | Bassa-media / medio | Validare con la musica accesa; altoparlante lontano. |
| **WR-7** | Dati biometrici di minori trattati male. | Bassa / **molto alto** | V-04, V-05, V-06, V-07; la scuola decide (`docs/05`). |
| **WR-8** | Divergenza tra Python e JavaScript con il tempo. | Media / medio | V-18: vettori di riferimento generati dal Python e usati dai test web. |

## 3. Decisioni aperte (WD-x)

Le decisioni D1-D6 della roadmap GameMaker restano in `docs/04-roadmap-mvp.md`.

| ID | Domanda | Opzioni | Effetto |
|----|---------|---------|---------|
| **WD-A** | Dove si pubblica la versione web? | (a) pagina nello stesso repository (con GitHub Pages, la cartella pubblicabile e' la radice o `docs/`, non `web/`: servirebbe un flusso di pubblicazione dedicato); (b) repository separato; (c) solo uso locale su `localhost`. | Raggiungibilita' da qualunque computer della scuola; separazione dal repository degli studenti. |
| **WD-B** | La versione web sta nello stesso repository degli studenti? | Si' (cartella `web/`) / no (repository dedicato) | Visibilita' e firma dei commit; si lega a **D5** (visibilita' e licenza del repository). |
| **WD-C** | Ambientazione. | Auto (come nel brainstorming), talpa (esempio R-06), astratta | Solo aspetto; vale `V-03`. |
| **WD-D** | Calcolo del punteggio (D4 della roadmap). | Tempo in coerenza; profondita'; mix | Forma di W0, W3. |
| **WD-E** | Firma dei commit e attribuzione degli strumenti usati. | A scelta del docente referente | Solo convenzione; non cambia il codice. |
| **WD-F** | Licenza del codice web (D5). | Non ancora scelta | Condizioni di riuso. |
| **WD-G** | I "due controller" di A (R-03): due dispositivi o due gruppi di tasti? | Tastiera + gamepad / due gruppi di tasti / mouse + tastiera | Forma di W3. |
| **WD-H** | Persone reali per la validazione: chi, quante, con quale consenso e dove. | Da concordare con la scuola (`docs/05`) | Condiziona W1c. |

## 4. Collegamento con il resto del repository

- Requisiti: `docs/02-richieste-originali.md` (R-01...R-13).
- Metodo e parametri da riprodurre: `docs/08-calibrazione.md`, `neurocontroller/`.
- Limiti scientifici, sicurezza, privacy: `docs/05-sicurezza-privacy-etica.md` (da leggere **prima** di ogni
  sessione con persone).
- Versione GameMaker e decisioni D1-D6: `docs/04-roadmap-mvp.md`.
- Questa cartella **non modifica** nessun altro file del progetto, tranne i rimandi in `README.md`,
  `docs/03-stato-attuale.md` e `docs/04-roadmap-mvp.md`.
