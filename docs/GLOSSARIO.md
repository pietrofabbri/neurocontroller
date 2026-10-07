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
| **Stato "concentrato" / "rilassato"** | Le due condizioni mentali richieste a B; la loro definizione tecnica (D2) e' stata proposta e implementata per persona (`08-calibrazione.md`), ma non e' ancora validata su EEG vero. |
| **PNRR** | Piano Nazionale di Ripresa e Resilienza: fonte dei fondi per le attivita' di orientamento in cui nasce il progetto. |
| **CEN** | Contemplative Education Network, rete citata come possibile fonte di finanziamento. |
| **Ruoli** | Hardware, Audio design, Deployment, Game design; ciascuno con un responsabile della documentazione. |
| **Calibrazione** | Breve serie di compiti cognitivi (rilassamento, calcolo mentale, movimenti volontari) con cui il sistema impara come reagisce **quella persona**. Vedi `08-calibrazione.md`. |
| **Profilo** | Riassunto della calibrazione di una persona (soglie, qualita', codice anonimo). Non contiene campioni grezzi. Vive in `data/profiles/`, fuori da Git. |
| **Indice E (engagement)** | `ln(beta / (alfa + theta))`: un unico numero per finestra di segnale; sale quando la beta cresce e l'alfa cala. E' un rapporto, quindi indipendente dalla scala del sensore. |
| **d' (d primo)** | Misura di quanto due distribuzioni (qui: indice E a riposo e nel calcolo) sono separate rispetto alla loro dispersione. Piu' alto = piu' distinguibili. |
| **Validazione tra blocchi** | Tarare su un blocco e verificare sull'altro, mai sullo stesso: evita di giudicare buona una calibrazione solo perche' riconosce i dati su cui e' stata fatta. |
| **Effetto Berger** | A occhi chiusi l'alfa aumenta (di norma nettamente) rispetto a occhi aperti. Qui e' usato solo come controllo che il sensore veda un segnale cerebrale. |
| **Persona simulata** | Segnale sintetico (tipica, debole, nulla) costruito secondo il modello assunto: serve a provare il programma, **non e' EEG** e non prova che il metodo funzioni. |
| **Livello di qualita'** | Verdetto della calibrazione: *usabile*, *debole* o *non affidabile*. Con un profilo non affidabile la modalita' `live` si rifiuta di partire senza `--force`. |
