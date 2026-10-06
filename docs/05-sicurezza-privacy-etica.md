# 05 - Sicurezza, privacy e limiti scientifici

Questo progetto misura **segnali elettrici del corpo di persone reali**, in un
contesto scolastico. Questo documento raccoglie cio' che va tenuto presente prima
di usarlo in pubblico, di pubblicarne i dati o di presentarlo all'orientamento.
Non e' un parere legale: dove serve, la scuola (dirigenza, responsabile della
protezione dei dati) decide.

## 1. Limiti scientifici: cosa il sistema NON dimostra

La scheda originale persegue il pensiero critico (R-12). Applicarlo al progetto
stesso e' la lezione migliore da raccontare.

- **Un solo canale.** Con un sensore monocanale sulla fronte non si misura "la
  concentrazione" in modo validato: si misura l'attivita' elettrica in un punto.
- **Artefatti muscolari.** Le bande alte (beta, gamma) in un EEG da fronte sono
  facilmente contaminate da attivita' dei muscoli della fronte, delle sopracciglia
  e della mascella e da movimenti degli occhi. Un valore alto di beta/gamma puo'
  voler dire "ho serrato la mascella" e non "sono concentrato". Questo andrebbe
  documentato nei test (M2).
- **Le associazioni banda-stato sono semplificazioni didattiche.** La tabella
  in `06-neuroville-e-fondamenti.md` e' una sintesi da manuale; le stesse bande
  compaiono in stati diversi (per esempio theta e alfa in meditazione e in
  sonnolenza).
- **Ipotesi sui suoni.** Il diario (17/03) riferisce che suoni "molto acuti" con
  frequenze vicine a quelle cerebrali di concentrazione assoluta alzano i valori.
  E' un'osservazione su **5 persone**, senza gruppo di controllo: va presentata come
  **ipotesi da mettere alla prova**, non come risultato. Inoltre un suono acuto
  non "entra in risonanza" con le onde cerebrali: le frequenze di un suono (centinaia
  o migliaia di Hz) sono su una scala diversa da quelle dell'EEG (1-42 Hz).
- **Non e' un dispositivo medico** e non va presentato come tale.

Formula consigliata per il pubblico: *"E' un esperimento per capire cosa possiamo
e cosa non possiamo misurare con un sensore economico."*

## 2. Sicurezza elettrica

- Il modulo BioAmp EXG Pill e' progettato per l'uso con sensori a contatto con la
  pelle. **Verificare le istruzioni di sicurezza del produttore** (Upside Down Labs)
  prima di ogni sessione: di norma, per ridurre i rischi, si raccomanda di
  alimentare il sistema in modo isolato dalla rete elettrica (per esempio un
  computer portatile **a batteria**, scollegato dal caricatore, e non un alimentatore
  collegato alla rete). *Questo punto va confermato sul manuale del produttore.*
- Usare solo elettrodi adatti all'uso sulla pelle e **mai** applicare elettrodi in
  condizioni di dubbio (pelle irritata, ferite).
- Ogni partecipante deve poter **interrompere in qualsiasi momento**.

## 3. Privacy e dati

Il segnale EEG riferito a una persona identificabile e' un **dato biometrico/di
salute**: va trattato con particolare cautela, e il consenso dei minori richiede il
consenso di chi esercita la responsabilita' genitoriale.

Regole di lavoro per questo repository:

1. **Nessun nome di studente** nei file (si usano i ruoli). Le fonti originali con
   i nomi non sono state copiate (vedi `docs/sources/README.md`).
2. **Nessun dato EEG grezzo identificabile** versionato. La cartella `data/raw/` e'
   ignorata da Git. In `data/` si mettono solo dati **anonimi** (identificativi tipo
   `P01`, `P02`), senza data di nascita, nome, classe.
3. Prima di salvare dati su persone minorenni: **consenso informato** documentato
   (cosa si misura, perche', quanto si conserva, chi vede i dati, possibilita' di
   ritirarsi).
4. Per la **demo pubblica** (open day): preferire il **controllo da tastiera** o
   un volontario adulto/consenziente; **nessuna registrazione** di segnali dei
   visitatori.
5. Il repository va creato **privato** finche' non e' stata fatta una verifica
   (nomi, dati, consenso, eventuali immagini di persone, indicazioni della scuola).

## 4. Licenze

- **Asset grafici** (auto): CC BY 4.0, obbligo di **attribuzione** (vedi
  `third_party/NOTICE.md`).
- **Codice del progetto**: licenza **non ancora scelta** (decisione D5). Senza
  licenza esplicita, per impostazione predefinita nessuno puo' riusare il codice.
- Il firmware originale (Chords) e' di terzi: rispettarne la licenza quando verra'
  incluso.

## 5. Contenuti per minori e comunicazione

Nei materiali per le medie (open day) evitare promesse del tipo "legge i pensieri"
o "misura la concentrazione". Usare la narrazione "Neuroville"
(`06-neuroville-e-fondamenti.md`), che e' chiara senza essere inesatta.
