# 04 - Roadmap MVP per chiudere il progetto

Principio guida (da R-09): **ogni tappa lascia il gioco funzionante** e ha un
criterio di accettazione verificabile. Le tappe sono ordinate per dipendenza, non
per durata; non sono state stimate durate perche' non si conoscono i tempi reali
del gruppo. Dimensioni relative: **S** (un incontro), **M** (due-tre incontri),
**L** (piu' di tre).

> Stato di questo documento: **proposta**. Le decisioni D1-D6 (sezione 3) sono
> **aperte** e vanno prese dal docente referente prima delle tappe che ne dipendono.

## 1. Tappe

| Tappa | Obiettivo | Accettazione | Dipende da | Dim. |
|-------|-----------|--------------|------------|------|
| **M0** | Base riproducibile: il repository si apre in GameMaker e l'auto si muove con il **simulatore** (senza sensore). | `python3 tools/udp_sim.py demo` muove l'auto in tutte le direzioni; `python3 -m unittest discover -s tests` passa. | - | S |
| **M1** | Recuperare i pezzi mancanti: `bridge.py`, firmware, guida, web app, dati dei test. Aggiungerli in `bridge/`, `firmware/`, `docs/`, `data/` con README che spieghino come usarli. | Un compagno che non ha mai visto il progetto, seguendo solo i README, porta un valore dal sensore alla console del gioco. | M0 | M |
| **M2** | **Da segnale a stato**: definire e implementare "concentrato" / "rilassato" **per persona** con compiti cognitivi di calibrazione; emettere lo **stato** (non solo una lettera di movimento). | **Implementato** (`neurocontroller/`, `docs/08-calibrazione.md`), con verdetto di affidabilita' per persona. **Da chiudere con sessioni vere**: su EEG reale, lo stato cambia in modo ripetibile tra rilassamento e calcolo mentale a occhi aperti, e la tensione muscolare e' documentata come confondente. Se la maggior parte delle persone risulta "non affidabile", la conclusione e' che sensore/posizione/compiti non bastano. | M1 (per il formato seriale reale), D2 | L |
| **M3** | **Meccanica centrale** (R-06, R-07): la strada ha due tipi di superficie che si alternano a caso; il punteggio cresce quando lo stato di B e' coerente con la superficie. | Con il simulatore che alterna stati, il punteggio sale quando coerente e non sale quando incoerente; comportamento coperto da una prova manuale scritta. | M2 (o simulatore di stati), D1 | M |
| **M3b** | **Movimento dolce** (richiesta del docente, 07/10/2026): l'auto non deve seguire ogni finestra ma una *tendenza* mentale mediata nel tempo. Oggi ogni aggiornamento (circa 1 al secondo) sposta l'auto di un passo fisso (5 px per pacchetto, `--repeat` per amplificarlo) e la media e' solo su 3 finestre (`--smooth`). Da fare: media mobile piu' lunga sul punteggio continuo e velocita' laterale proporzionale alla tendenza, non un comando a scatti. | Con il simulatore che alterna gli stati, il movimento laterale ha meno inversioni al secondo e l'auto non oscilla; regolabile da un solo parametro. | M0, D1 | S |
| **M4** | **Ruolo di A** (R-02, R-03): A guida (evitare ostacoli) e comanda la musica. | A e B giocano insieme sullo stesso computer; la musica cambia su comando di A. | M3, D3 | M |
| **M5** | **Partita da 10 minuti** (R-01): timer, punteggio finale, salvataggio **locale** (CSV) del risultato. | Una partita completa produce una riga di risultato nel file. | M4, D4 | S |
| **M6** | **Modalita' demo senza sensore** + video: tutto giocabile da tastiera, e una registrazione di 60-90 secondi del sistema reale funzionante. | La demo parte con un solo comando; il video mostra la pipeline vera. | M5 | S |
| **v2** | Risultati online con statistiche (R-10), gioco su due computer, ambientazione "talpa" (R-06). | - | M6 | L |

**Percorso minimo per presentare il progetto** se i tempi stringono: **M0 -> M1 -> M6**
(il gioco com'e', ma documentato, riproducibile e con video). M2-M5 portano il
progetto a coincidere con la scheda originale.

## 2. Perche' questa direzione (e non un'altra)

- **Costruisce su cio' che esiste**: riusa auto, strada e ricezione UDP; non si
  butta nulla del lavoro fatto.
- **Rende reale cio' che la scheda chiede** senza reinventare l'ambientazione:
  R-07 vale con la talpa come con l'auto (due superfici invece di due terreni).
- **Ordina il rischio**: la tappa piu' incerta (M2, trasformare il segnale in stato)
  e' isolata e puo' essere sostituita da un simulatore di stati, cosi' M3-M5
  procedono comunque.

## 3. Decisioni aperte

| ID | Domanda | Opzioni | Effetto |
|----|---------|---------|---------|
| **D1** | Qual e' la definizione di "v1" del gioco? | (a) auto singolo giocatore documentato com'e' (percorso minimo); (b) meccanica "superficie coerente con lo stato" sull'auto esistente (M3); (c) rifare in tema talpa. | Decide l'estensione di M3-M5. Proposta: **(b)**. |
| **D2** | Come si ricava "concentrato/rilassato" dalle bande? | Soglie su rapporti tra bande calibrate per persona; oppure confronto con una baseline individuale. | **Proposta implementata, da confermare**: indice `ln(beta/(alfa+theta))` con soglia per persona e verifica tra blocchi separati (`docs/08-calibrazione.md`, sezioni 3 e 5). Le soglie di qualita' sono euristiche, da rivedere con dati di piu' persone. |
| **D3** | Controller 1/2 di A: due dispositivi o due funzioni? | Tastiera + mouse/gamepad; tasti diversi sulla stessa tastiera. | Forma di M4. |
| **D4** | Come si calcola il punteggio? | Tempo in coerenza; profondita' raggiunta; mix. | Forma di M3/M5. |
| **D5** | Visibilita' e licenza del repository. | Privato / pubblico; licenza per il codice (non ancora scelta). | Vedi `05-sicurezza-privacy-etica.md`. |
| **D6** | Chi fa cosa (studenti vs docente) nelle tappe. | Assegnare le mansioni R-11 alle tappe. | Calendario. |

## 4. Convenzioni di lavoro

- Un'unica tappa alla volta; **una tappa e' chiusa solo quando il suo criterio di
  accettazione e' soddisfatto**.
- Ogni modifica funzionale aggiorna `03-stato-attuale.md`.
- Nessun nome di studente nel repository: si usano i **ruoli** (hardware, audio,
  deployment, game design).
