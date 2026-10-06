# data/

Dati dei test EEG. **Attenzione: vedi `docs/05-sicurezza-privacy-etica.md`.**

## Stato: DA RECUPERARE

Il diario (17/03/2026) riferisce test su **5 persone**; il piano di lavoro (F2)
prevede di annotare, per ogni stimolo, il **punto di massimo per ciascuna onda**. I
dati **non sono nel repository**.

## Regole

- Qui solo dati **anonimi** (identificativi `P01`, `P02`, ...). **Mai** nomi, classe,
  data di nascita.
- I dati **grezzi** vanno in `data/raw/`, cartella **ignorata da Git**.
- Prima di dati su minorenni: consenso informato documentato.

## Schema proposto (non e' un formato esistente)

`eeg_test_template.csv` e' una **proposta** per riordinare i risultati quando
verranno recuperati; va adattata ai dati reali. Colonne:

| Colonna | Significato |
|---------|-------------|
| `participant_id` | identificativo anonimo (`P01`...) |
| `session_date` | data della sessione (AAAA-MM-GG) |
| `stimulus` | stimolo (matematica, memory, scacchi, lettura veloce, apnea, riflessi, videogioco, rilassamento con musica) |
| `electrode_position` | punto della testa dell'elettrodo attivo (testo libero) |
| `band` | `delta`, `theta`, `alpha`, `beta`, `gamma` |
| `peak_hz` | frequenza del massimo della banda, se disponibile |
| `peak_value` | valore del massimo, con l'unita' usata dal software |
| `notes` | note (es. movimenti, mascella serrata, rumore) |
