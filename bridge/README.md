# bridge/

Qui deve stare **`bridge.py`**: il programma che legge i dati dell'Arduino dalla
porta seriale e li inoltra al gioco via UDP.

## Stato: DA RECUPERARE

Secondo il diario (`docs/07-diario-studenti.md`) il file e' stato creato il
28/04/2026 e aggiornato il 05/05/2026 per emettere "le onde divise in 3 diverse
uscite"; si trovava su Google Classroom. **Non e' in questo repository** e non e'
stato spacciato per suo un sostituto: `tools/udp_sim.py` simula solo il lato "uscita",
e il pacchetto `neurocontroller/` (`docs/08-calibrazione.md`) e' una **alternativa
nuova**, con una calibrazione per persona, che parla al gioco nello stesso formato.
Quando `bridge.py` verra' recuperato va aggiunto qui cosi' com'e', e confrontato.

## Cosa deve fare (contratto verso il gioco)

Vedi `docs/01-architettura.md`, sezione 2:

- invia pacchetti **UDP** a `127.0.0.1:6510`;
- ogni pacchetto e' **un solo carattere** (`a`, `b`, `g`) **terminato da NUL**;
- nessun `\n` finale: il gioco confronta la stringa con `"a"`/`"b"`/`"g"`.

## Checklist quando verra' aggiunto

- [ ] Copiare `bridge.py` qui senza modifiche (primo commit "cosi' com'e'").
- [ ] Documentare in questo README: dipendenze (es. `pyserial`), porta seriale,
      baud rate, come si lancia.
- [ ] Verificare il significato di `a`, `b`, `g` (ipotesi: alfa, beta, gamma) e
      aggiornare `docs/01-architettura.md`.
- [ ] Verificare che il terminatore corrisponda a quanto il gioco si aspetta.
- [ ] Non committare chiavi, nomi di persone o percorsi personali.
