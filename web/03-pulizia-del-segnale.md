# 03 - La "bella pulizia" del segnale

*Richiesta del docente referente (7 ottobre 2026): il segnale vero con elettrodi sulla fronte e' molto
piu' sporco di quello simulato (palpebre, mascella) e non e' mai stato provato con il sensore; serve
una pulizia seria. Questo documento la progetta. **Non e' implementata.** Le soglie sono **proposte da
tarare** con dati veri; cio' che esiste gia' nel codice Python e' indicato con il file.*

## 1. Principi

1. **Meglio scartare che sbagliare.** Una finestra dubbia non entra nello stato e non da' punti.
2. **Il giocatore deve vedere la qualita'** del proprio segnale, in tempo reale, in modo comprensibile
   (non solo "errore").
3. **Il gioco non deve premiare il disturbo.** Serrare la mascella alza la potenza ad alta frequenza,
   cioe' fa sembrare l'utente "concentrato": se il sistema ci cade, il punteggio misura i muscoli,
   non la mente (`docs/05` sez. 1; `docs/08` sez. 4).
4. **Tutto cio' che e' stato deciso va misurato.** Ogni rilevatore ha una percentuale di successo e di
   falsi allarmi, misurata con il protocollo della sezione 6.
5. **Si dichiara cio' che non si puo' sapere** (sezione 7).

## 2. Fonti di disturbo

| Fonte | Come si vede nel segnale (fronte, un canale) | Contromisura | Gia' nel Python? |
|-------|-----------------------------------------------|--------------|------------------|
| **Palpebre (battito)** | onda lenta, ampia (decine/centinaia di microvolt), 200-400 ms, nella zona di delta/theta; molto marcata sulla fronte | rilevatore di battito (sez. 4.3); scartare la finestra | no (il blocco "movimenti volontari" la mostra, non la rileva) |
| **Movimento degli occhi** | gradini/onde lente | come sopra | no |
| **Mascella serrata / denti** | aumento improvviso della potenza oltre 30 Hz, a banda larga | rilevatore di raffica muscolare (sez. 4.4) | **si', in parte**: potenza oltre 42 Hz (`profile.is_artifact`, `HF_FACTORS`) |
| **Tensione della fronte / sopracciglia** | simile alla mascella ma piu' debole; cade **dentro la banda beta** | **non separabile con un solo canale** (sez. 7) | no, e non rilevabile |
| **Parlare, deglutire** | raffiche muscolari brevi | come mascella | in parte |
| **Rete a 50 Hz** | picco a 48-52 Hz | computer a batteria, lontano da cavi; controllo iniziale; eventuale filtro | **si'** (`dsp.signal_quality`, `MAINS_RANGE`) |
| **Cavo toccato / elettrodo che si stacca** | scatti netti, salti di livello | rilevatore di salti (sez. 4.2) | no |
| **Contatto scarso** | segnale piatto, oppure deriva lenta, oppure saturazione | controllo iniziale e continuo | **si'**: piatto e saturazione (`dsp.signal_quality`) |
| **Deriva lenta** | variazione sotto 1 Hz | rimozione della media (e della tendenza) per finestra | **si'** (`dsp.detrend`) |
| **Musica nelle cuffie** | possibile accoppiamento sui cavi | prova con la musica accesa (sez. 6) | no |
| **Movimento della testa / del corpo** | scatti, variazioni di contatto | come cavo toccato | no |

## 3. Catena di pulizia a livelli

**L0 - Preparazione fisica (prima della sessione).** Computer a batteria, lontano da alimentatori e
cavi di rete; pelle pulita e asciutta; elettrodi nuovi e a contatto; cavo fermato (nastro) per ridurre
i movimenti; riferimento posizionato come da istruzioni del produttore (*da verificare sul manuale*).
Verifica guidata nell'interfaccia (V-08).

**L1 - Controllo prima della sessione** (equivalente di `neurocontroller check`, ~5 s a riposo):
frequenza di campionamento **misurata** dai tempi di arrivo; segnale non piatto; saturazione sotto il 2%;
rete a 50 Hz sotto la soglia; stima del livello di disturbo a riposo. Esito semaforo (verde / giallo /
rosso) con **istruzioni di correzione** in italiano (come i messaggi di `dsp.signal_quality`).

**L2 - Pulizia continua, finestra per finestra.** Ogni finestra riceve una **qualita'**: `pulita`,
`dubbia` o `scartata`, in base ai rilevatori della sezione 4. Le finestre `scartate` e `dubbie` non
entrano nella media dello stato (come oggi: `StateClassifier` ignora le finestre `artefatto`).

**L3 - Giudizio sulla sessione.** Percentuale di finestre pulite, numero di battiti e raffiche rilevati,
verdetto di affidabilita' del profilo (`profile.Profile.level`, soglie `Q_USABLE_*`, `Q_WEAK_*`).
Se la percentuale di finestre pulite scende sotto una soglia (*proposta*: 60% su 30 s), il gioco
sospende i punti e mostra "segnale non affidabile" (V-11).

## 4. Rilevatori: specifiche proposte

*Parametri iniziali **da tarare**. Ogni rilevatore va validato come in sezione 6 prima di essere
dichiarato affidabile.*

### 4.1 Ampiezza e alta frequenza (esistono gia')
Ampiezza efficace (RMS) e rapporto `potenza(>42 Hz) / totale` della finestra, confrontati con i valori
tipici **della persona**, appresi dai blocchi puliti: multiplo scelto fra `RMS_FACTORS` e `HF_FACTORS`
in modo da scartare al massimo il 2,5% dei blocchi puliti per criterio (`profile._pick_factor`,
`MAX_FALSE_ALARM = 0.05`). Richiede frequenza di campionamento sopra 84 Hz.

### 4.2 Salti e scatti (nuovo)
Differenza tra campioni consecutivi; una finestra e' marcata se la differenza supera *k* volte la
mediana dei valori assoluti delle differenze (*proposta: k da 8 a 12, da tarare*). Si scartano 100 ms
prima e 300 ms dopo. Cattura cavo toccato, elettrodo staccato, scatto della testa.

### 4.3 Battito di palpebre (nuovo)
Picco isolato di ampiezza oltre *k* volte la RMS locale (*k da 3 a 5*), durata 200-400 ms, forma
monofasica, con energia concentrata sotto 8 Hz. Si scarta una zona di +-0,5 s attorno al picco. Si
conta anche il numero di battiti per minuto (utile al giudizio di sessione e per spiegare agli studenti
cosa si vede).

### 4.4 Raffica muscolare (nuovo, estende 4.1)
Aumento brusco della potenza 30-42 Hz **e** oltre 42 Hz rispetto alla mediana degli ultimi 10 s puliti
(*moltiplicatore da tarare*), con durata da 100 ms a qualche secondo. Distingue una raffica da un
livello alto costante (quest'ultimo e' tensione continua: sezione 7).

### 4.5 Rete elettrica in corso d'opera (esistente in controllo iniziale, esteso)
Il rapporto 48-52 Hz / totale viene calcolato anche durante la sessione; se supera la soglia per piu' di
alcuni secondi, avviso "disturbo di rete" e finestre `dubbie`. *Da valutare*: filtro a **notch** a 50 Hz
prima della FFT; si adotta **solo se** i dati mostrano che migliora la separazione (decisione sui dati,
non a priori).

### 4.6 Qualita' composita
`qualita = scartata` se scatta 4.1, 4.2, 4.3 o 4.4; `dubbia` se vicina alla soglia (*margine da tarare*)
o se la rete e' alta; altrimenti `pulita`. Questo e' il valore mostrato al giocatore e usato dal gioco.

## 5. Cosa vede il giocatore

- **Indicatore di qualita'** sempre presente (semaforo + barra "segnale pulito %" degli ultimi 30 s).
- **Motivo in parole semplici** quando e' rosso: "hai chiuso gli occhi forte", "stringi la mascella",
  "il cavo si e' mosso", "troppo disturbo di corrente: allontanati da cavi e caricatore".
- Il **punteggio si ferma** (non scende, non sale) mentre la qualita' e' insufficiente (V-11).
- Per gli studenti: una vista facoltativa "sotto il cofano" con il segnale, lo spettro e i punti in cui
  i rilevatori sono scattati (valore didattico: vedere perche' un battito sembra un'onda enorme).

## 6. Protocollo di validazione (la "sessione di pulizia")

Va fatto **con il sensore vero**, su piu' persone e in giorni diversi, **con la musica accesa** per meta'
dei blocchi. Ogni persona e' un codice `Pxx` (V-06); i dati restano locali e **non** vanno versionati
(`docs/05`, sezione 3).

| Blocco | Cosa fa la persona | Cosa deve succedere |
|--------|--------------------|---------------------|
| a | riposo, occhi aperti, ferma, 60 s | nessun rilevatore scatta (serve a misurare i **falsi allarmi**) |
| b | occhi chiusi, 30 s | alfa sale (sanity check, `docs/08` sez. 6); nessun rilevatore scatta |
| c | 20 battiti a ritmo, con pause | 4.3 scatta ad ogni battito (**hit rate**) |
| d | mascella serrata, 10 volte | 4.4 scatta (**hit rate**); l'indice `E` **non** deve finire in "concentrato" **senza** `artefatto` |
| e | sopracciglia alzate, 10 volte | 4.4 o 4.1 scatta |
| f | parlare ad alta voce, 20 s | 4.4 scatta sulle raffiche |
| g | calcolo mentale a occhi aperti, fermo, 60 s (serie del 7) | **nessuno** scatta (e' il compito vero); si misura `E` |
| h | muovere la testa a destra e a sinistra | 4.2 scatta |
| i | toccare il cavo / staccare un elettrodo | 4.2 e il controllo del contatto scattano |
| j | ripetizione di a-g **dopo 24 ore** | stabilita' dei criteri (V-13) |

**Criteri di accettazione proposti** (da rivedere dopo il primo giro di dati):

1. Falsi allarmi sui blocchi a, b, g: **non oltre il 5%** delle finestre (coerente con
   `MAX_FALSE_ALARM` del Python).
2. Hit rate su battiti, mascella, scatti del cavo: **almeno il 90%** degli eventi.
3. **Test anti-trucco**: durante il blocco d, il punteggio di gioco **non sale** (le finestre sono
   `artefatto` o `scartata`) in almeno il **95%** delle finestre.
4. **Test del confondente** (il piu' importante): confrontare `E` del blocco d (mascella) con `E` del
   blocco g (calcolo). Se `E(d)` e' **uguale o maggiore** di `E(g)` su **gran parte delle persone**, il
   solo `E` non distingue la mente dai muscoli: l'indice **non va usato da solo** per il gioco senza una
   modifica (sezione 7).
5. Parita' con il Python (V-18): i rilevatori gia' esistenti danno gli stessi esiti sugli stessi segnali
   registrati.

Ogni esito si registra per persona e per rilevatore in una tabella (hit rate, falsi allarmi), da
conservare **senza** dati personali. Se i criteri 1-3 non sono raggiunti, la tappa W1 **non si chiude**.

## 7. Limiti che nessuna pulizia elimina (da dire sempre)

- **Un solo canale.** Non si puo' separare in modo certo l'attivita' dei muscoli della fronte da quella
  cerebrale **dentro la banda beta**, che e' proprio quella che alimenta `E`. La lieve tensione della
  fronte mentre si fa un calcolo difficile **non e' rilevabile** da una raffica. Quindi anche con la
  pulizia migliore, un `E` alto puo' essere in parte *"stringo la fronte"* (`docs/08` sez. 4).
- **Cosa si puo' fare** (da provare, non garantito): (a) trattare lo stato come **stima** e dirlo
  (V-09); (b) provare indici meno legati alla beta (per esempio il rapporto alfa/theta) o combinazioni,
  **e giudicarli con il test del confondente**; (c) considerare un **secondo canale** o un riferimento
  diverso se in futuro cambia l'hardware (e' un'estensione legata al vincolo V-19, non una promessa).
- **Stabilita' nel tempo non dimostrata**: ricalibrare a ogni sessione (V-13).
- **Le soglie sono euristiche** finche' non ci sono dati veri di piu' persone.

Una conclusione negativa e' un risultato valido: *"con questo sensore e questi compiti lo stato non e'
distinguibile in modo affidabile"* e' coerente con R-12 e va riportata come tale.
