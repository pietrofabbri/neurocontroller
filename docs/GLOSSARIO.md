# Glossario

Pensato per chi arriva al progetto senza contesto (collega, studente nuovo, altra AI).

| Termine | Significato in questo progetto |
|---------|--------------------------------|
| **EEG** | Elettroencefalografia: misura dell'attivita' elettrica del cervello tramite elettrodi sulla pelle. Qui con un solo canale. |
| **BioAmp EXG Pill** | Piccolo modulo amplificatore/filtro (Upside Down Labs) che porta il debolissimo segnale degli elettrodi a un livello leggibile da un microcontrollore. |
| **Arduino** | Scheda a microcontrollore che campiona il segnale e lo invia al computer via USB (porta seriale). |
| **Chords** | Software e firmware open source di Upside Down Labs per visualizzare/registrare i segnali del sensore. Il firmware e' stato modificato dal gruppo. |
| **Seriale** | Collegamento a flusso di byte tra Arduino e computer (USB). Il "monitor seriale" dell'IDE Arduino lo mostra a video. |
| **FFT** | *Fast Fourier Transform*: algoritmo che scompone un segnale nelle frequenze che lo compongono. Nella narrazione: "la Maga FFT". |
| **Bande (delta, theta, alfa, beta, gamma)** | Intervalli di frequenza dell'EEG (vedi `06-neuroville-e-fondamenti.md`). |
| **Artefatto** | Segnale non cerebrale che si mescola al segnale (muscoli, occhi, movimenti dei cavi). |
| **Bridge** | Programma Python (`bridge.py`) che legge il seriale e inoltra al gioco via UDP. |
| **UDP** | Protocollo di rete a pacchetti senza connessione; qui usato in locale tra bridge e gioco, porta 6510. |
| **GameMaker** | Motore/IDE per videogiochi 2D (linguaggio GML) con cui e' scritto il gioco. |
| **GML** | *GameMaker Language*, il linguaggio dei file `.gml`. |
| **Room** | "Stanza" di GameMaker: la scena in cui vivono le istanze degli oggetti. |
| **Evento Async Networking** | Evento di GameMaker (file `Other_68.gml`) che scatta quando arrivano dati dalla rete. |
| **MVP** | *Minimum Viable Product*: la versione piu' piccola che funziona; nel progetto, l'idea di crescere a piccoli passi mantenendo sempre un gioco funzionante. |
| **Giocatore A / Giocatore B** | A: controller tradizionale e musica; B: controller EEG (vedi `02-richieste-originali.md`). |
| **Stato "concentrato" / "rilassato"** | Le due condizioni mentali richieste a B; la loro definizione tecnica e' una decisione aperta (D2). |
| **PNRR** | Piano Nazionale di Ripresa e Resilienza: fonte dei fondi per le attivita' di orientamento in cui nasce il progetto. |
| **CEN** | Contemplative Education Network, rete citata come possibile fonte di finanziamento. |
| **Ruoli** | Hardware, Audio design, Deployment, Game design; ciascuno con un responsabile della documentazione. |
