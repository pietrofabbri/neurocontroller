# 07 · Un secondo parametro che B può controllare con la mente

Stato: **proposta, non implementata** (10/10/2026). Richiesta del docente: pensare a un parametro, oltre a "concentrato / rilassato", che il giocatore B possa controllare con la mente. Questo documento spiega cosa è realistico con l'hardware attuale, confronta le opzioni e propone un percorso con criteri di accettazione. La decisione spetta al docente.

## 1. Che cosa abbiamo davvero

- **Un solo canale EEG** (BioAmp EXG Pill + Arduino), 10 bit, circa 193 campioni/s con il firmware attuale a 9600 baud (250 con `provaBCI.ino`).
- Un solo asse di controllo oggi: l'indice di impegno `E = ln(β / (α + θ))`, confrontato con una soglia personale ricavata dalla calibrazione. Il punteggio continuo `score_b` va da −1 (riposo) a +1 (calcolo mentale).
- Il segnale reale è ancora spesso disturbato (qualità 45% nella prima partita). **Qualunque nuovo parametro deve funzionare sulle sole finestre pulite** e peggiorerà se i disturbi non si risolvono.
- Non esiste ancora una validazione su più persone: tutto ciò che segue è un'ipotesi da misurare.

## 2. Criteri che un buon secondo parametro deve rispettare

1. **Controllabile a comando** dal giocatore, non solo uno stato che subisce (sonnolenza, emozione).
2. **Distinguibile dal primo asse**: se si muove insieme a rilassato/concentrato non aggiunge niente. Va misurata la correlazione con `score_b`.
3. **Calcolabile con ciò che c'è**: nessun hardware nuovo, o un hardware economico e dichiarato.
4. **Robusto agli artefatti**: non deve premiare muscoli, ciglia o movimenti.
5. **Comprensibile**: B e A devono capire perché cambia, per poterlo imparare.
6. **Misurabile e riproducibile**: con una procedura di calibrazione breve e un test–retest.

## 3. Opzioni

| # | Parametro | Come si ottiene | Controllabile? | Distinto dal 1° asse? | Esigenze | Giudizio |
|---|---|---|---|---|---|---|
| 1 | **Stabilità**: quanto B riesce a tenere fermo il proprio stato | Deviazione standard di `score_b` su ~8 s, solo finestre pulite (`1 − sd/sd_ref`) | Sì: è tenere l'attenzione senza oscillare | Parziale: dipende dalla stessa misura ma è un'altra proprietà (la varianza, non la media) | Nessuno | **Consigliato come primo passo** |
| 2 | **Agilità**: quanto in fretta B passa a un nuovo stato quando il terreno cambia | Tempo da un cambio di terreno a quando `score_b` entra nella fascia giusta | Sì: flessibilità attentiva | Parziale: altra proprietà della stessa serie | Nessuno; si può calcolare già oggi dalle serie salvate | **Consigliato, in parallelo e solo come analisi** |
| 3 | **Occhi chiusi / aperti** (ritmo α di Berger) | Aumento di α a occhi chiusi, rilevabile anche da una sola derivazione, più la deflessione lenta delle palpebre in fronte | Sì, ma è un gesto, non "mente" | **No**: a occhi chiusi α sale e `E` scende, contamina il primo asse | Nessuno | **Sconsigliato come comando**; utile come **prova di verifica** del segnale (20 s a occhi chiusi: α deve salire) |
| 4 | **Vigilanza vs sonnolenza** (θ/α) | Rapporto θ/α su finestre pulite | **No**: la sonnolenza non si comanda | Sì | Nessuno | Scartato come controllo; interessante come **variabile di ricerca** (stanchezza) |
| 5 | **Immaginazione motoria** (ERD del ritmo μ) | Calo di potenza 8–13 Hz su C3/C4 immaginando un movimento | Sì, ma richiede addestramento | Sì | Montaggio sulle aree sensomotorie e di norma ≥ 2 canali; sedute di addestramento | **Non adatto** a questo hardware e a sessioni brevi |
| 6 | **Asimmetria frontale** (α sinistra–destra, "approccio/ritiro") | Differenza di α tra due derivazioni frontali | Dubbio: evidenze deboli e molto discusse come comando | Sì | **Secondo canale** (altro sensore) | Sconsigliato come comando; possibile solo come ricerca |
| 7 | **Respiro / variabilità cardiaca** (coerenza a ~6 respiri al minuto) | ECG con lo stesso tipo di sensore ma altro montaggio, oppure cintura | Sì: è respirare lentamente | Sì: è un'altra fisiologia | **Secondo sensore** e montaggio diverso | Valido come **secondo asse vero**, ma non è "con la mente" in senso stretto e richiede hardware |
| 8 | **θ frontale medio** (attenzione focalizzata, meditazione) | Potenza θ su derivazione frontale | Sì, in meditatori; in generale incerto | Parziale: θ è già nel denominatore di `E` | Montaggio frontale medio | Interessante per il **progetto sulla meditazione**, da trattare come ricerca a parte |

## 4. Raccomandazione

Con **un canale e questo hardware non esiste, a mio giudizio, un secondo asse davvero indipendente e affidabile** (opzioni 5 e 6 richiedono altro montaggio, la 3 contamina il primo asse, la 4 non è controllabile). Quindi:

1. **Adottare la Stabilità (opzione 1) come secondo parametro**, dichiarando onestamente che è una **proprietà dello stesso segnale**, non un secondo canale. Ha un vantaggio forte: richiede un'abilità reale e allenabile (tenere lo stato senza oscillare) e dà ad A e B un compito in più da coordinare.
2. **Calcolare l'Agilità (opzione 2) come analisi**, subito, sulle serie già salvate (`game_series`: `terrain`, `score_b`, `quality`, `t`), senza ancora metterla nel gioco.
3. Se si vuole un **secondo asse vero**, la strada onesta è hardware: un secondo sensore (opzione 7, respiro/ECG) o un secondo canale per l'opzione 6. Va deciso a parte, con costi e consenso.

### Uso nel gioco (proposta per la Stabilità)

- Mappatura suggerita: stabilità alta → **scudo**: dopo un urto lo stordimento si riduce (fino a −60%) e il turbo non stordisce di più. Stabilità bassa → nessun bonus, **nessuna penalità** (così il parametro non punisce l'ansia o i disturbi).
- Calcolo: finestra mobile di 8 s con almeno 10 finestre pulite; `stab = clamp(1 − sd(score_b)/0,45, 0, 1)`; se non ci sono abbastanza finestre pulite il parametro vale 0 e lo si dice (come per i punti: V-11).
- Interfaccia: un secondo indicatore sotto "Stato di B"; nell'archivio nuove colonne (`stability_mean`, e `stability` nella serie), con la solita voce nel dizionario `06-dati-ricerca.md`.

## 5. Come si decide (criteri di accettazione prima di metterlo nel gioco)

1. **Non è lo stesso asse**: su almeno 5 partite reali di ≥ 3 persone, la correlazione tra `stability` e `|score_b|` (e tra `stability` e `score_b`) resta moderata (|r| < 0,6). Se è più alta, il parametro non aggiunge informazione.
2. **È allenabile ma non banale**: la distribuzione della stabilità per persona ha una varianza non trascurabile e **non** coincide con la qualità del segnale (se segue `quality_pct` misura i disturbi, non la mente).
3. **Robusto**: ricalcolato togliendo i secondi `reason ≠ ''`, il valore cambia poco.
4. **Test–retest**: due sedute della stessa persona, stessa musica, danno valori correlati (r ≥ 0,5). Con pochi dati si segnala come "non stabilito".
5. **Non premia i muscoli**: durante la prova "mascella" (`J` con segnale simulato) la stabilità non sale.
6. **Il segnale reale va prima sistemato**: finché la qualità media resta sotto il ~60%, **non** si mette nulla di nuovo nel gioco con il sensore vero.

## 6. Decisione richiesta

Scegliere tra: (a) procedere con Stabilità + analisi di Agilità; (b) solo analisi, niente cambi al gioco finché il segnale non è pulito; (c) valutare un secondo sensore (respiro/ECG). Finché non si decide, **nulla di questo documento è nel codice**.
