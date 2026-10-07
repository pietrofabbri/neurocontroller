# Neurocontroller - videogioco controllato da un sensore EEG

Progetto scolastico di orientamento (PNRR, a.s. 2025/26): un **videogioco in cui il
controller e' un sensore EEG** (BioAmp EXG Pill + Arduino) letto in tempo reale e
collegato a un gioco GameMaker. Realizzato da un gruppo di studenti volontari con il
docente referente, con metodo **MVP incrementale** e quattro ruoli (hardware, audio
design, deployment, game design).

> **Stato (7 ottobre 2026): prototipo di pipeline funzionante nell'ultimo anello (sensore ->
> gioco); calibrazione per persona con compiti cognitivi implementata ma provata solo con
> segnale SIMULATO; gioco a due giocatori richiesto dalla scheda NON ancora implementato.**
> Il dettaglio, requisito per requisito, e' in [`docs/03-stato-attuale.md`](docs/03-stato-attuale.md).

## Cos'e' il gioco richiesto

Due giocatori **cooperano** per fare piu' punti possibile in **10 minuti**.
**A** usa un controller tradizionale e fa variare la **musica**; **B** usa il controller
EEG e, guidato dalla musica di A, cambia il proprio stato mentale
(**concentrato / rilassato**). Il punteggio cresce quando lo stato di B e' coerente con
la condizione del gioco (esempio originale: terreno compatto/soffice per una talpa
che scava). Vedi [`docs/02-richieste-originali.md`](docs/02-richieste-originali.md).

## Ordine di lettura consigliato

1. [`docs/02-richieste-originali.md`](docs/02-richieste-originali.md) - **cosa e' stato chiesto** (requisiti `R-01...R-13`).
2. [`docs/01-architettura.md`](docs/01-architettura.md) - **come e' fatto** (pipeline, protocollo UDP, oggetti del gioco).
3. [`docs/03-stato-attuale.md`](docs/03-stato-attuale.md) - **a che punto siamo** rispetto alle richieste.
4. [`docs/04-roadmap-mvp.md`](docs/04-roadmap-mvp.md) - **come chiudere** (tappe M0-M6, decisioni aperte D1-D6).
5. [`docs/05-sicurezza-privacy-etica.md`](docs/05-sicurezza-privacy-etica.md) - **limiti scientifici, sicurezza, privacy**: da leggere prima di usarlo in pubblico.
6. [`docs/06-neuroville-e-fondamenti.md`](docs/06-neuroville-e-fondamenti.md) e [`docs/07-diario-studenti.md`](docs/07-diario-studenti.md) - materiale didattico e storia del lavoro.
7. [`docs/08-calibrazione.md`](docs/08-calibrazione.md) - **calibrazione per persona**: compiti cognitivi, metodo, cosa e' verificato e cosa no.
8. [`docs/GLOSSARIO.md`](docs/GLOSSARIO.md) - termini.

## Struttura del repository

```
README.md
docs/                  documentazione (numerata, vedi sopra)
game/BLeppo2/          progetto GameMaker (IDE 2024.14.4.222)
neurocontroller/       calibrazione per persona + riconoscimento dello stato + invio al gioco
tools/udp_sim.py       simulatore del bridge: prova il gioco senza sensore
tests/                 test automatici (unittest, solo libreria standard)
bridge/                bridge.py (seriale -> UDP)        DA RECUPERARE
firmware/              firmware Arduino modificato        DA RECUPERARE
data/                  dati dei test (anonimi) e schema   DA RECUPERARE
third_party/           licenze e attribuzioni (CC BY 4.0 per gli sprite)
```

## Calibrare una persona (il flusso di ogni sessione)

Ogni persona reagisce in modo diverso: prima di giocare si fa una **calibrazione di circa 7
minuti** con compiti cognitivi (respiro lento, calcolo mentale, movimenti volontari). Il
programma dice se per *quella persona* il controllo e' **usabile, debole o non affidabile**, e
si rifiuta di andare avanti se non lo e'. Metodo e limiti: [`docs/08-calibrazione.md`](docs/08-calibrazione.md).

```
python3 -m neurocontroller demo                        # prova guidata SENZA sensore (segnale simulato)
python3 -m neurocontroller ports                       # trova la porta dell'Arduino
python3 -m neurocontroller check                       # il segnale e' sensato?
python3 -m neurocontroller calibrate                   # calibra la prossima persona (P01, P02...)
python3 -m neurocontroller live --profile P01 --udp    # riconosce lo stato e comanda il gioco
```

Serve solo Python >= 3.8 (con il sensore vero anche `pip install pyserial`). I profili restano
sul computer in `data/profiles/` e **non** vanno in Git. Il codice del sensore reale e' ancora
**non verificato**: il formato seriale e i 250 campioni/s sono assunzioni (sezione 6 del
documento 08). Test: `python3 -m unittest discover -s tests`.

## Come provarlo (senza sensore)

Requisiti: **GameMaker** (stessa versione dell'IDE o successiva, per il progetto) e
**Python >= 3.8**.

1. Aprire `game/BLeppo2/BLeppo2.yyp` in GameMaker ed eseguire il gioco (il gioco apre
   un socket UDP sulla porta **6510**; una sola copia alla volta).
2. In un terminale, dalla radice del repository:

   ```
   python3 tools/udp_sim.py demo --seconds 10
   ```

   L'auto si muove a destra, su, a sinistra. Comandi singoli:
   `python3 tools/udp_sim.py send b --count 20` (`a` sinistra, `b` destra, `g` su).
3. Tenendo premuto il **tasto freccia su** la strada scorre.
4. Test del simulatore: `python3 -m unittest discover -s tests -v`.

> Il comportamento dentro GameMaker e' stato dedotto dalla lettura del codice: **non
> e' stato eseguito nell'ambiente di analisi**. Se il passo 2 non muove l'auto, vedi
> "Rischi noti del protocollo" in `docs/01-architettura.md` (provare `--no-nul`).

## Convenzioni

- **Nessun nome di studente** nel repository: si usano i ruoli.
- **Nessun dato EEG identificabile** versionato (`data/raw/` e' ignorata).
- Ogni modifica funzionale aggiorna `docs/03-stato-attuale.md`.
- Una tappa della roadmap e' chiusa solo quando il suo criterio di accettazione e' soddisfatto.
- Per chi riprende il progetto (persona o AI) senza il contesto della conversazione
  da cui e' nato: tutto cio' che serve e' in `docs/`. Le affermazioni sono marcate
  come **verificate** (dal codice), **riferite** (dal diario) o **inferenze/ipotesi**.

## Crediti e licenze

- Idea e coordinamento: docente referente. Codice del gioco e documento "progetto
  gioco mente": studenti del gruppo; bridge, firmware, guida: vedi i README di
  `bridge/` e `firmware/` (da recuperare).
- Sprite delle auto: **Formula64x64**, CC BY 4.0, autore Justinas0192 -
  vedi [`third_party/NOTICE.md`](third_party/NOTICE.md).
- **Licenza del codice del progetto: non ancora scelta** (decisione D5).
