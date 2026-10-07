# 01 - Architettura

Descrive come e' fatto il sistema **oggi**, distinguendo con onesta' cio' che e'
**verificabile nel repository** da cio' che e' **riferito nel diario** ma i cui
file non sono ancora stati recuperati.

## 1. Pipeline end-to-end

```
 elettrodi sulla fronte/testa
        |  (segnale analogico, microvolt)
        v
 [BioAmp EXG Pill]  --- amplifica e filtra ---> uscita analogica
        |
        v
 [Arduino + firmware Chords modificato]  --- campiona (ADC) ---> seriale USB
        |
        v
 [bridge.py]  --- legge il seriale, calcola le bande (FFT), emette 3 uscite ---> UDP
        |
        v   UDP 127.0.0.1:6510, 1 carattere per pacchetto
 [GameMaker: obj_player, evento Async Networking]  --- muove il giocatore
        |
        v
 gioco (auto su strada che scorre)
```

| Anello | Stato in questo repository | Evidenza |
|--------|----------------------------|----------|
| Sensore BioAmp EXG Pill + Arduino | **Non verificabile** (hardware) | Diario 10/03, 17/03; scheda F1 |
| Firmware Arduino modificato | **Non presente** - da recuperare | Diario 7/04, 14/04; `firmware/README.md` |
| `bridge.py` (seriale -> UDP, 3 uscite) | **Non presente** - da recuperare | Diario 28/04 (creato), 5/05 (3 uscite); `bridge/README.md` |
| Ricezione UDP e movimento nel gioco | **Presente e leggibile** | `game/BLeppo2/objects/obj_player/` |
| Simulatore del bridge (per prove senza sensore) | **Aggiunto** in questo repository | `tools/udp_sim.py`, `tests/` |
| Calibrazione per persona e riconoscimento dello stato (alternativa a `bridge.py`) | **Aggiunto**, provato solo con segnale **simulato** | `neurocontroller/`, `docs/08-calibrazione.md` |

### 1.1 Il pacchetto `neurocontroller/` (nuovo)

Legge il sensore dalla porta seriale, calcola le bande con la FFT, **tara ogni persona
con una serie di compiti cognitivi** e riconosce lo stato mentale (rilassato /
concentrato), poi manda al gioco una lettera via UDP nello stesso formato descritto nella
sezione 2. **Non sostituisce** il lavoro degli studenti: finche' `bridge.py` e il firmware
non sono recuperati (`bridge/README.md`), e' il modo per avere l'intera catena in
questo repository. Assume una riga di testo per campione e 250 campioni al secondo:
**ipotesi da verificare** con il firmware vero (`docs/08-calibrazione.md`, sezione 6).

```
 Arduino --seriale--> sources.SerialSource --> dsp (FFT, bande) --> profile (stato)
                                                                        |
                                              game_link (UDP 6510, 1 lettera + NUL)
                                                                        v
                                                              GameMaker obj_player
```

Storia dell'integrazione secondo il diario: il primo tentativo di collegare Arduino
a GameMaker con l'estensione di terze parti "yellowafterlife" ha dato "scarsi
risultati" (24/03); sono passati a leggere i dati dal monitor seriale dell'IDE
Arduino (31/03), a modificare il firmware (7/04, 14/04) e infine a un **bridge
Python** (28/04) che inoltra i dati al gioco.

## 2. Protocollo bridge -> gioco (quello che il gioco si aspetta)

Ricavato **dal codice** di `obj_player` (`Create_0.gml`, `Other_68.gml`), quindi
verificato sul lato ricevente.

| Aspetto | Valore |
|---------|--------|
| Trasporto | **UDP**, il gioco apre un server con `network_create_server_raw(network_socket_udp, 6510, 1)` |
| Porta | **6510** |
| Indirizzo mittente atteso | non filtrato dal gioco; il bridge e il gioco girano sullo stesso computer (`127.0.0.1`) |
| Payload | una **stringa** letta con `buffer_read(buff, buffer_string)` (stringa terminata da NUL) |
| Comandi riconosciuti | `"a"` -> sinistra (`x -= spd`); `"b"` -> destra (`x += spd`); `"g"` -> su (`y -= spd`) |
| Altri valori | ignorati (nessuna azione) |
| Velocita' | `spd = 5` pixel per messaggio ricevuto |
| Bordi | "effetto Pac-Man": uscendo da un lato si rientra dal lato opposto |
| Ostacoli | se il passo successivo collide con `obj_muro`, il movimento non avviene |
| Debug | ogni messaggio e' scritto nella console con `show_debug_message("Onda: ...")` |

**Inferenza da confermare**: le tre lettere `a`, `b`, `g` corrispondono
molto probabilmente a **alfa**, **beta**, **gamma** (il diario del 5/05 dice che il
bridge emette "le onde divise in 3 diverse uscite"). Va verificato sul `bridge.py`
reale una volta recuperato.

**Rischi noti del protocollo attuale** (non sono bug dimostrati, sono punti in cui
un bridge diverso puo' non funzionare):

1. Il gioco legge una stringa NUL-terminata. Un mittente che invia `"b\n"` o `"b "`
   produce un valore diverso da `"b"` e il comando viene **ignorato in silenzio**.
2. Non c'e' un messaggio "nessuna attivita'" ne' un'intensita': ogni pacchetto e'
   un passo fisso. La *quantita'* di segnale non entra nel gioco.
3. Il socket non viene mai chiuso (nessun evento Clean Up): due copie del gioco sullo
   stesso computer entrano in conflitto sulla porta 6510.
4. Non verificato in questo ambiente: **non e' stato possibile eseguire GameMaker**
   qui, quindi il comportamento runtime e' dedotto dalla lettura del codice e dalla
   documentazione di GameMaker, non da una prova.

## 3. Il gioco (progetto GameMaker `game/BLeppo2`)

Progetto creato con GameMaker IDE **2024.14.4.222** (da `BLeppo2.yyp`), con opzioni
per Windows, macOS, Opera GX e Reddit. Risoluzione logica **352 x 208** (macro
`SCREEN_WIDTH`/`SCREEN_HEIGHT` definite in `obj_cam`).

### 3.1 Stanza `Room1`

Contiene (da `rooms/Room1/Room1.yy`): un'istanza di `obj_player` (posizione
176,104), una di `obj_cam`, una di `obj_game`, una di `obj_road`; livelli
`Instances`, `road`, `Tiles_1`, `Background`. **Non risultano istanze di `obj_muro`
ne' di `Obj_albero` nella stanza.**

### 3.2 Oggetti

| Oggetto | Ruolo | Dettagli verificati nel codice |
|---------|-------|--------------------------------|
| `obj_player` | L'auto (sprite `spr_car`). **Ricevitore EEG.** | Apre il socket UDP; muove l'auto in base al comando; `Step` chiama `ball_walls()` (bordi Pac-Man); se tocca `obj_muro` va al centro della stanza. |
| `obj_road` | Segmento di strada (sprite `spr_road`) che scorre. | Si muove in verticale con `lerp` verso una velocita' target (`spd = 3`) determinata da **tasti freccia su/giu' della tastiera**; si distrugge quando `y >= SCREEN_HEIGHT`. |
| `obj_game` | Generatore di strada. | Ogni 10 step, **se e' premuto il tasto freccia su**, crea un'istanza di `obj_road` in (`SCREEN_WIDTH/2`, 0). Ha anche un `Alarm_0` che ne crea una. |
| `obj_cam` | Camera. | Segue una posizione fissa; implementa lo **screen shake** (`shake_time`, `shake_time_strong`) che nessun altro oggetto attiva al momento. |
| `obj_muro` | Muro solido (sprite `spr_muro`). | Il suo `Collision` con se stesso e' praticamente inutile. |
| `Obj_albero` | Albero solido. | Nessun codice; non piazzato in stanza. |
| script `ball_walls` | Avvolgimento ai bordi. | Chiamato in `obj_player.Step`; la stessa logica e' duplicata nell'evento di rete. |

### 3.3 Lettura d'insieme (e cautela)

Oggi nel gioco **il giocatore EEG controlla l'auto** (sinistra/destra/su) mentre
**lo scorrimento della strada dipende dalla tastiera**. Questa separazione e'
*compatibile* con il germe del gioco a due giocatori (uno controlla l'avanzamento
della strada con la tastiera, l'altro guida con il cervello), ma il codice non lo
dichiara ne' lo sfrutta: va trattata come **ipotesi**, non come intenzione
documentata. Vedi `03-stato-attuale.md` e la decisione D1 in `04-roadmap-mvp.md`.

### 3.4 Asset

Gli sprite delle auto provengono dal pacchetto **Formula64x64** (licenza
**CC BY 4.0**, autore indicato nel file di licenza: Justinas0192). Il file di licenza
originale e' in `third_party/Formula64x64/license.txt`; l'attribuzione e' in
`third_party/NOTICE.md`. **Obbligo di legge della licenza: mantenere l'attribuzione.**

## 4. Elementi citati nelle fonti ma non presenti nel repository

| Elemento | Dove e' citato | Stato |
|----------|----------------|-------|
| `bridge.py` (versione con 3 uscite) | diario 28/04, 5/05 ("salvato su classroom") | da recuperare |
| Firmware Arduino modificato | diario 7/04, 14/04 | da recuperare |
| "Guida" per chi si aggiunge al gruppo | diario 21/04 | da recuperare |
| Static web app | diario 28/04 | da recuperare |
| Dati dei test su 5 persone | diario 10/03-17/03; F2 | da recuperare |
| Suoni "molto acuti" che alzano i valori | diario 17/03 | da recuperare e da trattare come ipotesi |
