# data/

Dati dei test EEG. **Attenzione: vedi `docs/05-sicurezza-privacy-etica.md`.**

## Cosa c'e' in questa cartella

| Percorso | Contenuto | In Git? |
|----------|-----------|---------|
| `README.md`, `eeg_test_template.csv` | questa descrizione e l'intestazione del formato | si |
| `profiles/P01.json` ... | profili di calibrazione per persona (riassunti, **niente campioni grezzi**) | **no** (ignorata) |
| `sessions/P01_<data>_blocchi.csv` ... | tabella per blocco e banda, scritta da `python3 -m neurocontroller calibrate` | **no** (ignorata) |
| `raw/` | campioni grezzi, solo con `--save-raw` | **no** (ignorata) |

Le tre cartelle di dati vengono create dal programma al primo salvataggio: **sono dati
fisiologici di persone**, anche se con codice anonimo, e restano sul computer. Un test
(`tests/test_repo_hygiene.py`) verifica che Git le ignori. Per usare un'altra cartella:
`--data-dir` oppure la variabile d'ambiente `NEUROCONTROLLER_DATA`.

## Stato dei dati degli studenti: DA RECUPERARE

Il diario (17/03/2026) riferisce test su **5 persone**; il piano di lavoro (F2) prevede di
annotare, per ogni stimolo, il **punto di massimo per ciascuna onda**. Quei dati **non sono
nel repository**. Se esistono, vanno convertiti nel formato sotto e conservati **fuori da
Git** finche' non e' verificato il consenso (vedi `docs/05-sicurezza-privacy-etica.md`).

## Regole

- Solo dati **anonimi** (identificativi `P01`, `P02`, ...). **Mai** nomi, classe, data di nascita.
- Prima di dati su minorenni: consenso informato documentato.
- I dati **simulati** (`--source simulated`) sono marcati `SIMULATO` nelle note e non vanno
  mai mischiati con quelli veri.

## Formato di `sessions/*_blocchi.csv`

E' il formato richiesto dal piano di test originale ("per ogni test annotare il punto di
massimo per ciascuna onda"), con due colonne in piu'. Una riga per blocco e per banda:

| Colonna | Significato |
|---------|-------------|
| `participant_id` | identificativo anonimo (`P01`...) |
| `session_date` | data della sessione (AAAA-MM-GG) |
| `stimulus` | compito del blocco (`occhi_chiusi`, `rilassamento_occhi_aperti`, `calcolo_sottrazioni`, `calcolo_moltiplicazioni`, `artefatti`) |
| `electrode_position` | punto della testa dell'elettrodo attivo (testo libero, opzione `--electrode`) |
| `band` | `delta`, `theta`, `alpha`, `beta`, `gamma` |
| `peak_hz` | frequenza del massimo dello spettro medio **dentro la banda** |
| `peak_value` | valore di quel massimo (unita' arbitrarie: confrontabile solo dentro la stessa sessione) |
| `mean_rel_power` | potenza media della banda **relativa** al totale 1-42 Hz (0-1): e' la misura da confrontare tra persone e sessioni |
| `n_windows` | finestre di analisi usate nel blocco |
| `notes` | blocco di origine; `SIMULATO` se il segnale non era vero |

Per il formato dei profili vedi `docs/08-calibrazione.md`.
