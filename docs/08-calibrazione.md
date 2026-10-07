# 08 - Calibrazione per persona

Questo documento descrive il pacchetto Python `neurocontroller/`, che trasforma il segnale
del sensore in uno **stato mentale stimato** (rilassato / concentrato) **tarato su ogni
persona** con una breve serie di compiti cognitivi. Risponde alla richiesta: *"i dati di
test devono essere impostabili molto facilmente ogni volta; una serie di test cognitivi che
tarano il controller su ogni persona"*, e realizza la parte tecnica della tappa **M2** della
roadmap (`04-roadmap-mvp.md`).

> **Stato: implementato e provato solo con segnale SIMULATO.** Nessun EEG vero e'
> stato ancora misurato con questo codice. Cio' che e' verificato e cio' che non lo e'
> sta nella sezione 7: **leggerla prima di dire a qualcuno che "funziona"**.

## 1. Uso rapido

Requisiti: Python >= 3.8. Per il sensore vero serve anche `pyserial`
(`pip install pyserial`); per le prove simulate non serve nulla.

Dalla radice del repository:

```
python3 -m neurocontroller demo                       # prova completa SENZA sensore
python3 -m neurocontroller ports                      # trova la porta dell'Arduino
python3 -m neurocontroller check                      # il segnale e' sensato?
python3 -m neurocontroller calibrate                  # calibra la prossima persona (P01, P02...)
python3 -m neurocontroller profiles                   # elenca i profili e la loro qualita'
python3 -m neurocontroller live --profile P01 --udp   # riconosce lo stato e comanda il gioco
```

Per ogni nuova persona i passi sono sempre gli stessi: **collegare, `check`, `calibrate`,
leggere il verdetto, `live`**. Il codice `P01`, `P02`... e' assegnato da solo; i nomi di
persona sono rifiutati. Senza sensore ogni comando accetta `--source simulated`
(con `--persona tipica|debole|nulla` per vedere come si comporta con persone diverse).

Opzioni utili: `--serial-port` (se ci sono piu' porte), `--fs` (campioni al secondo, vedi
sezione 6), `--adc-max` (4095 per una scheda a 12 bit), `--electrode` (dove e' posto
l'elettrodo, finisce nei file), `--yes` (non attendere INVIO tra i blocchi).

## 2. I compiti cognitivi (protocollo `v1`)

Circa **5,5 minuti** di registrazione, circa 6,5-7 con conto alla rovescia e pause. Ogni stato
e' registrato in **due blocchi separati** (1 e 2).

| # | Blocco | Durata | A cosa serve |
|---|--------|--------|--------------|
| 1 | Occhi chiusi, a riposo | 45 s | **Controllo del sensore**: l'alfa deve salire (effetto Berger). Non entra nei due stati. |
| 2 | Rilassamento a occhi aperti (1): respiro 4 s dentro / 6 s fuori | 60 s | stato **rilassato** |
| 3 | Calcolo mentale: sottrazioni di 7 da 1000 (1) | 60 s | stato **concentrato** |
| 4 | Rilassamento a occhi aperti (2) | 60 s | stato **rilassato**, blocco di verifica |
| 5 | Calcolo mentale: moltiplicazioni a mente (2) | 60 s | stato **concentrato**, blocco di verifica |
| 6 | Movimenti volontari: mascella, palpebre, occhi | 48 s | controllo dei **disturbi** (vedi sezione 4) |

Scelte di progetto, ciascuna con il suo motivo:

- **Rilassato e concentrato sono entrambi a occhi APERTI.** Durante il gioco si guarda lo
  schermo. Se "rilassato" fosse "occhi chiusi", il sistema imparerebbe a riconoscere le
  palpebre, non lo stato mentale. Gli occhi chiusi servono solo come controllo.
- **Compiti silenziosi e fermi.** Parlare, scrivere e muoversi producono segnali muscolari
  molto piu' grandi di quelli cerebrali.
- **Due blocchi per stato.** Permettono di tarare su un blocco e **verificare sull'altro**:
  una calibrazione che riconosce solo il blocco su cui e' stata fatta non vale nulla.
- **Un blocco di movimenti volontari.** Verifica che mascella e palpebre *si vedano* nel
  segnale: se non si vedono, il sensore non e' a contatto e i disturbi reali passeranno
  inosservati.
- I primi 5 secondi di ogni blocco sono scartati (la persona sta ancora entrando nel
  compito); fa eccezione il blocco dei movimenti volontari, dove si guarda tutto.

Il protocollo e' in `neurocontroller/protocol.py` ed e' pensato per essere **modificato**
(compiti, durate, istruzioni) senza toccare il resto; se si cambia, va cambiato anche
`PROTOCOL_ID`.

## 3. Come si ricava lo stato

1. Il segnale e' diviso in **finestre di circa 2 secondi** (512 campioni a 250 Hz), con
   sovrapposizione.
2. Per ogni finestra la **FFT** (`dsp.py`) da' la potenza nelle bande delta, theta, alfa,
   beta, gamma (confini 1-4-8-14-30-42 Hz: le soglie 3,9 / 7,5 / 13,9 Hz della scheda
   originale sono approssimate a numeri interi).
3. Da ogni finestra si ricava **un solo numero**, l'indice
   `E = ln( beta / (alfa + theta) )`. E' un rapporto tra bande, quindi **non dipende dalla
   scala del sensore**. Sale quando la beta cresce e l'alfa cala. Rapporti di questo tipo
   sono usati in letteratura come indice di "engagement" (viene attribuito a Pope e
   colleghi, 1995: **citazione da verificare sul testo originale**).
4. Per ogni persona si misurano media e dispersione di `E` nei blocchi *rilassato* e
   *concentrato*; la **soglia** sta tra le due medie, pesata sulle dispersioni.
5. In diretta, ogni finestra riceve un punteggio da -1 (tipico del riposo di *quella
   persona*) a +1 (tipico del suo calcolo mentale), **mediato sulle ultime 3 finestre
   pulite**. Dentro una fascia di +-0,25 attorno alla soglia lo stato e' **neutro**.
   Le finestre con disturbo sono "artefatto" e non entrano nella media.

Il punteggio e' **relativo alla persona**: non ha senso confrontare i valori di `E` di due
persone, ne' usare il profilo di una per un'altra.

## 4. Disturbi (artefatti)

Le soglie anti-disturbo sono **apprese dai blocchi puliti della stessa persona**: una
finestra e' scartata se l'ampiezza efficace o la potenza oltre 42 Hz (muscoli) superano un
multiplo del valore tipico. Il multiplo e' il piu' piccolo che scarta al massimo il 2,5% dei
blocchi puliti per ciascun criterio. Il blocco dei movimenti volontari misura quanti disturbi
veri vengono riconosciuti (`hit_rate`) e i blocchi puliti quanti falsi allarmi (`false_alarm_rate`).

**Limite importante.** Sulla fronte l'attivita' dei muscoli (fronte, sopracciglia, mascella)
cade **anche dentro la banda beta**, la stessa che alimenta `E`. Il controllo sopra coglie i
disturbi grossolani, **non** la lieve tensione facciale che molte persone hanno mentre
fanno un calcolo difficile. Quindi un `E` alto durante il calcolo potrebbe misurare in parte
*"stringo la fronte"* e non *"sto pensando"*. Il progetto non puo' escluderlo con un solo canale;
va detto, e se ne tiene conto nel modo di presentarlo (`05-sicurezza-privacy-etica.md`).

## 5. Come si giudica la qualita' della calibrazione

Il programma **non si limita a salvare il profilo: dichiara se e' affidabile**. Si usano:

- **d'** (separazione): quanto sono distanti le due distribuzioni di `E` rispetto alla loro
  dispersione;
- **accuratezza tra blocchi**: si tara su (rilassato 1 + concentrato 1), si verifica su
  (rilassato 2 + concentrato 2) e viceversa; e' la media delle due direzioni;
- **direzione**: `E` deve essere piu' alto nel calcolo che a riposo; altrimenti per quella
  persona l'indice non significa "concentrazione".

| Livello | Condizione | Effetto |
|---------|-----------|---------|
| **usabile** | direzione giusta, d' >= 1,5 e accuratezza >= 80% | `live` parte |
| **debole** | direzione giusta, d' >= 0,8 e accuratezza >= 65% | `live` parte, il controllo sara' impreciso |
| **non affidabile** | tutto il resto, o dati insufficienti | `live` **si rifiuta** senza `--force` |

Compaiono anche messaggi in chiaro (contatto, alfa a occhi chiusi che non sale, direzione
opposta, movimenti non visibili). **Le soglie 1,5 / 80% / 0,8 / 65% sono euristiche scelte
da noi, non validate su dati reali**: vanno riviste quando ci saranno dati di piu' persone
(sezione 8).

## 6. Primo collegamento con il sensore: cosa controllare

Tre ipotesi del codice sono **assunzioni non verificate**, perche' il firmware modificato dal
gruppo non e' ancora nel repository (`firmware/README.md`):

1. **Formato dei dati**: una riga di testo ASCII per campione (come il Serial Plotter di
   Arduino), eventualmente con piu' colonne (`--column`). Il firmware originale Chords puo'
   inviare pacchetti binari: in quel caso `check` fallisce con "formato non riconosciuto" e
   va aggiunto un parser in `sources.py`.
2. **Campioni al secondo**: assunti 250. Il comando `check` **misura** la frequenza reale e
   avvisa se differisce piu' del 10%: se succede, rilanciare con `--fs <valore misurato>`,
   altrimenti le bande risultano sbagliate.
3. **ADC a 10 bit** (0-1023): per schede con piu' bit usare `--adc-max` (altrimenti il
   controllo di saturazione scambia il segnale normale per un segnale saturo).

Altre verifiche da fare la prima volta: computer **a batteria** e lontano da cavi e
alimentatori (il disturbo di rete a 50 Hz e' segnalato da `check`); sensore a contatto
(il blocco dei movimenti volontari mostra se si vedono mascella e palpebre); e che l'alfa
salga davvero a occhi chiusi (messaggio nel report).

## 7. Cosa e' stato verificato e cosa no

**Verificato (con il codice e i test del repository):**

- FFT, bande e indici su segnali sintetici di frequenza nota (`tests/test_dsp.py`).
- Che con un segnale **simulato** costruito sul modello assunto, la persona "tipica" venga
  dichiarata usabile, la "debole" mai usabile e la "nulla" sempre non affidabile (misurato
  su 12 semi casuali: tipica 12/12 usabile; debole 0/12 usabile; nulla 12/12 non affidabile).
- Che la catena complessa (calibrazione, profilo, live, invio UDP) giri end-to-end, che i
  file prodotti abbiano le colonne documentate, che i nomi di persona siano rifiutati e che
  `live` si rifiuti di partire con un profilo non affidabile (oltre 150 test automatici:
  `python3 -m unittest discover -s tests`).
- Che il lato Python parli al gioco come il gioco si aspetta: la porta e le lettere sono
  confrontate **con i file `.gml`** del gioco (`tests/test_live_and_link.py`).

**NON verificato:**

- **Tutto cio' che riguarda EEG vero.** Il simulatore e' costruito secondo lo stesso modello
  che il classificatore assume (alfa alto a occhi chiusi, beta alto nel calcolo): che il
  classificatore lo riconosca e' **circolare** e non dimostra che funzioni su una testa vera.
- Che l'indice `E` separi davvero rilassato e concentrato **con un solo canale frontale** e
  questi compiti. E' l'ipotesi principale del progetto, ancora da mettere alla prova.
- La **stabilita' nel tempo**: la verifica "tra blocchi" avviene nella stessa sessione, a pochi
  minuti di distanza. Non dimostra che il profilo valga domani. **Ricalibrare a ogni sessione.**
- Le soglie di qualita' e di disturbo (euristiche), e le tre assunzioni della sezione 6.
- L'esecuzione di GameMaker: non e' stato possibile avviarlo in questo ambiente.

## 8. Come raccogliere dati utili (e cosa farne)

Per decidere se il metodo regge servono **piu' persone** (non decine di sessioni della stessa).
Per ognuna: una calibrazione completa, con consenso (`05-sicurezza-privacy-etica.md`), codice
anonimo, e `--electrode` compilato. Poi si guarda con `profiles`: quante persone risultano
usabili? Quanto varia d'? Un blocco di verifica in giorni diversi per qualcuna di loro dice se
il profilo e' stabile. Se la gran parte risulta "non affidabile", la conclusione onesta e' che
**questo sensore in questa posizione con questi compiti non basta**, e il progetto va
presentato cosi'; lo sapremo grazie al fatto che il programma lo dichiara.

## 9. Dati salvati

| Cosa | Dove | In Git? |
|------|------|---------|
| Profilo della persona (riassunto: soglie, qualita'; **nessun campione grezzo**) | `data/profiles/P01.json` | **No** (ignorato) |
| Tabella per blocco e banda (formato richiesto dal piano di test originale) | `data/sessions/P01_<data>_blocchi.csv` | **No** (ignorato) |
| Campioni grezzi, **solo con `--save-raw`** | `data/raw/` | **No** (ignorato) |

Sono dati fisiologici di persone, anche se con codice anonimo: restano sul computer.
La cartella si cambia con `--data-dir` o con la variabile `NEUROCONTROLLER_DATA`.
Un test (`tests/test_repo_hygiene.py`) verifica che Git le ignori davvero.

## 10. Collegamento al gioco

`live --udp` invia al gioco una lettera per aggiornamento, nel formato che `obj_player` legge
(UDP 127.0.0.1:6510, un carattere + NUL). La corrispondenza **stato -> lettera e'
PROVVISORIA**: oggi "concentrato" = `b` (destra) e "rilassato" = `a` (sinistra), solo per
poter provare la catena. Non e' il gioco richiesto: la meccanica vera (superfici, punteggio, ruolo
di A, musica) e' la tappa M3 e dipende dalla decisione D1. Gli stati "neutro" e "artefatto"
non inviano nulla, cosi' un disturbo non muove l'auto. La corrispondenza si cambia con
`--map concentrato=b,rilassato=a`.

## 11. Struttura del codice

| Modulo | Compito |
|--------|---------|
| `dsp.py` | FFT, spettro, potenza per banda, indici, controllo del segnale |
| `protocol.py` | sequenza dei compiti, durate, istruzioni |
| `sources.py` | sorgenti: simulata (con persone inventate), seriale, file; elenco porte |
| `profile.py` | profilo, qualita', classificatore di stato, codici anonimi |
| `calibration.py` | procedura guidata, interfaccia a terminale, salvataggio |
| `live.py`, `game_link.py` | riconoscimento in diretta e invio UDP al gioco |
| `cli.py` | comandi `ports`, `check`, `calibrate`, `live`, `demo`, `profiles` |

Solo libreria standard (pyserial opzionale, per il sensore). Per aggiungere un compito
cognitivo: nuovo `Block` in `protocol.py` con `role` `relax` o `focus` e la chiave che
termina con `_1`/`_2` (serve alla verifica tra blocchi).
