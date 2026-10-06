# 07 - Diario di lavoro degli studenti (2026)

Trascrizione **fedele** del diario tenuto dagli studenti (i refusi sono mantenuti
per non alterare la fonte). Le date sono quelle indicate nel diario; il
documento originale **non e' incluso** nel repository (vedi `docs/sources/README.md`).
Le annotazioni di questo repository sono tra parentesi quadre.

| Data | Cosa e' stato fatto (dalla fonte) |
|------|-----------------------------------|
| 03/03/2026 | Presentazione del progetto: il docente ha spiegato su cosa si basera' (onde delta, theta, alpha, beta, gamma e su quale frequenza si alzano). Poi si e' iniziato a creare idee per il gioco. |
| 10/03/2026 | Uso di GameMaker; creato l'oggetto *player*; iniziata la scrittura del codice del primo oggetto per farlo muovere nella room. Un altro gruppo, nel frattempo, ha testato le onde cerebrali con un modulo aggiunto a un Arduino. |
| 17/03/2026 | Il gruppo che testa i valori cerebrali ha finito i test, arrivando a **5 persone testate**. Con i parametri di 5 persone, passo successivo: cercare suoni che permettessero l'innalzamento dei valori cerebrali; trovati suoni molto acuti con frequenze simili a quelle del cervello in concentrazione assoluta. [Osservazione da trattare come ipotesi: vedi `05-sicurezza-privacy-etica.md`.] |
| 24/03/2026 | Cercato il modo di mandare in input i dati dell'Arduino a GameMaker; alla fine usata la zip di "yellowafterlife" e scritto un codice basilare per visualizzare il funzionamento dell'Arduino. Avendo avuto scarsi risultati, scaricato Arduino IDE e iniziata la lettura e comprensione del codice condiviso su GitHub dal produttore (Chords-Arduino-Firmware). [La frase si interrompe: "...e successivamente abbiamo incominciato."] |
| 31/03/2026 | Tentativo di mettere in pratica l'invio dei dati dall'Arduino a GameMaker. Poi guardati semplicemente i dati sul monitor seriale di Arduino IDE: **ottenuti dei dati**. |
| 07/04/2026 | Iniziato il lavoro concreto modificando il firmware, sperimentando sul codice fino ad avere un diagramma dei dati in uscita dall'Arduino. |
| 14/04/2026 | Modificato il firmware dell'Arduino in modo che i dati siano visibili nell'applicazione Arduino IDE **senza usare Chords**. |
| 21/04/2026 | Condiviso il lavoro svolto con i compagni e creata una **guida** per chi vorra' aggiungersi. |
| 28/04/2026 | Provato a collegare Arduino a GameMaker **senza l'estensione YAL**, usando un codice Python salvato su Classroom di nome `bridge.py`. Creata anche la **static web app**. |
| 05/05/2026 | Riorganizzato e aggiornato `bridge.py` per dare in uscita le onde divise in **3 diverse uscite**. |
| (senza data) | Il diario termina con una riga "giorno" priva di data e contenuto. |

## Lettura d'insieme

- Pivot principale: dal plugin di terze parti (YAL) a un bridge Python custom,
  dopo risultati scarsi.
- Il diario e' un **registro di attivita'**, non una documentazione di risultati:
  non contiene i dati dei test, ne' le conclusioni sulle bande, ne' un manuale d'uso.
- Il periodo dopo il 5 maggio non e' documentato.
