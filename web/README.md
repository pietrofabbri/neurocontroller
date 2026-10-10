# web/ - versione web del neurocontroller

> **Stato (10 ottobre 2026): app W0.2** - la **talpa** (partita di 5 minuti, terreni a 5 livelli, ostacoli e gemme),
> musica di A a 3 cursori, database locale con scheda del partecipante e consenso (`05-talpa-w0.md`, `06-dati-ricerca.md`).
> Si avvia con `python3 -m neurocontroller serve`. Il sensore vero e' stato collegato e **una partita e' stata giocata**,
> ma il segnale e' risultato molto disturbato: la pulizia del segnale (`03`) e' ancora solo progettata.

## Che cos'e'

L'idea e' rifare il neurocontroller come **applicazione web**: una pagina che gira nel browser, senza
installare nulla, in cui

- il **giocatore B** e' controllato dal **sensore EEG** (BioAmp EXG Pill + Arduino, letto via USB dal
  browser) oppure, in assenza di sensore, da una **persona simulata**;
- il **giocatore A** usa un controller tradizionale (tastiera o gamepad) e fa variare la **musica** per
  aiutare B a restare nello stato mentale giusto;
- si gioca in due, in **5 minuti** (richiesta originale: 10; dimezzati il 10/10/2026), con un punteggio condiviso.

E' la stessa richiesta originale (`docs/02-richieste-originali.md`, R-01...R-09), su una piattaforma
che si presta anche ad altro: si puo' **far vedere** a chi non ha mai visto il progetto (per esempio
nell'orientamento alle scuole medie) e puo' accogliere **altre cuffie** in futuro.

## Rapporto con la versione GameMaker

- Il gioco GameMaker degli studenti (`game/BLeppo2/`) **non viene toccato ne' buttato**. Se gli
  studenti vogliono proseguirlo, hanno tutto quello che serve (protocollo UDP documentato in
  `docs/01-architettura.md`, pacchetto Python `neurocontroller/` che gli parla).
- **Chi cura questa documentazione abbandona l'ipotesi di sviluppare ulteriormente il lato
  GameMaker.** Resta pero' compatibile: la versione web non lo sostituisce, e' un **secondo
  binario**. Il confronto tra le due scelte puo' essere materia di lezione.
- Un browser **non puo' inviare pacchetti UDP**: la versione web **non** comanda il gioco
  GameMaker. Per comandarlo serve ancora il pacchetto Python.

## Indice

| File | Contenuto |
|------|-----------|
| [`01-decisioni-e-vincoli.md`](01-decisioni-e-vincoli.md) | Decisioni prese, **vincoli** (V-xx), tracciabilita' verso i requisiti originali R-xx |
| [`02-architettura.md`](02-architettura.md) | Moduli, flusso dei dati, cosa si eredita dal codice Python, piattaforma browser |
| [`03-pulizia-del-segnale.md`](03-pulizia-del-segnale.md) | **La "bella pulizia"**: disturbi, rilevatori, protocollo di validazione, limiti |
| [`04-piano-e-accettazione.md`](04-piano-e-accettazione.md) | Tappe W0-W4 con criteri di accettazione, rischi, decisioni aperte |
| [`05-talpa-w0.md`](05-talpa-w0.md) | La talpa: come si avvia, regole del gioco, sensore, database, cosa manca, prima prova reale |
| [`06-dati-ricerca.md`](06-dati-ricerca.md) | **Dizionario dei dati**, protocollo di raccolta, etica e privacy, limiti, analisi |
| [`07-secondo-parametro-mentale.md`](07-secondo-parametro-mentale.md) | Proposta (non implementata) di un secondo parametro controllabile con la mente |
| [`app/`](app/) | il codice (HTML, JavaScript, CSS: nessuna compilazione, V-14) |

## Come leggere questi documenti

- Cio' che e' **verificato nel codice del repository** e' indicato con il file (per esempio
  `neurocontroller/dsp.py`). Cio' che e' **proposta** e' etichettato *proposta* o *da tarare*.
  Cio' che dipende da **EEG vero** e' *non verificato*: nessun EEG vero e' mai stato misurato con
  questo progetto (`docs/08-calibrazione.md`, sezione 7).
- Gli identificatori: `R-xx` requisiti originali; `D1-D6` decisioni aperte della roadmap GameMaker;
  `V-xx` vincoli della versione web; `WD-x` decisioni aperte della versione web; `W0-W4` tappe.
- I documenti sono pensati per essere letti **senza il contesto della conversazione** in cui sono nati,
  anche da un'altra persona o da un'altra intelligenza artificiale.
