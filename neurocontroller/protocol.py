"""Protocollo di calibrazione: la sequenza di compiti cognitivi eseguita da ogni persona.

Scelte di progetto (motivazioni in docs/08-calibrazione.md):
  * i due stati da distinguere (rilassato / concentrato) sono entrambi a OCCHI APERTI,
    perche' durante il gioco si guarda lo schermo: se "rilassato" fosse "occhi chiusi"
    il sistema imparerebbe a riconoscere le palpebre e non lo stato mentale;
  * gli occhi chiusi servono solo come CONTROLLO del sensore (l'alfa deve salire);
  * i compiti sono SILENZIOSI e senza movimenti (niente voce, niente tastiera):
    parlare e muoversi producono artefatti muscolari che sporcano il segnale;
  * ogni stato e' registrato in DUE blocchi separati, cosi' si puo' verificare che
    la calibrazione regga da un blocco all'altro (e non solo "dentro" lo stesso blocco);
  * l'ultimo blocco chiede movimenti volontari (mascella, palpebre, occhi) per
    controllare che i disturbi si vedano nel segnale.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, replace
from typing import Optional, Tuple

PROTOCOL_ID = "v1"

ROLE_CHECK = "check"        # controllo del sensore, non usato per i due stati
ROLE_RELAX = "relax"
ROLE_FOCUS = "focus"
ROLE_ARTIFACT = "artifact"


@dataclass(frozen=True)
class Prompt:
    at: float            # secondi dall'inizio del blocco
    text: str
    sim_state: str = ""  # solo simulatore: stato da simulare da questo momento


@dataclass(frozen=True)
class Block:
    key: str
    title: str
    role: str
    duration: float            # secondi
    instruction: str
    sim_state: str             # che stato simulare quando la sorgente e' simulata
    stimulus: str              # nome usato nei file CSV
    trim: float = 5.0          # secondi iniziali scartati (transitorio)
    prompts: Tuple[Prompt, ...] = ()
    problem_kind: str = ""     # "moltiplicazioni": mostra un problema nuovo a intervalli
    problem_interval: float = 0.0


COMMON = ("Resta fermo/a, non parlare, non serrare la mascella. "
          "Tieni lo sguardo sul punto fisso (il cursore sullo schermo).")


def default_protocol() -> Tuple[Block, ...]:
    """Protocollo standard (circa 6 minuti di registrazione)."""
    return (
        Block(
            key="closed", title="Occhi chiusi, a riposo", role=ROLE_CHECK, duration=45,
            sim_state="closed", stimulus="occhi_chiusi", trim=5,
            instruction="Chiudi gli occhi e stai fermo/a, senza pensare a niente di preciso. "
                        "(Serve a controllare che il sensore veda il segnale 'alfa'.)"),
        Block(
            key="relax_1", title="Rilassamento a occhi aperti (1)", role=ROLE_RELAX, duration=60,
            sim_state="relax", stimulus="rilassamento_occhi_aperti",
            instruction=COMMON + " Respira lentamente: 4 secondi per inspirare, 6 per espirare. "
                                 "Lascia andare i pensieri."),
        Block(
            key="focus_1", title="Calcolo mentale: sottrazioni (1)", role=ROLE_FOCUS, duration=60,
            sim_state="focus", stimulus="calcolo_sottrazioni",
            instruction=COMMON + " Parti da 1000 e sottrai 7 di seguito, a mente "
                                 "(993, 986, 979...). Se sbagli, riparti da dove ricordi. "
                                 "NON dire i numeri ad alta voce."),
        Block(
            key="relax_2", title="Rilassamento a occhi aperti (2)", role=ROLE_RELAX, duration=60,
            sim_state="relax", stimulus="rilassamento_occhi_aperti",
            instruction=COMMON + " Come prima: respiro lento, 4 secondi dentro e 6 fuori."),
        Block(
            key="focus_2", title="Calcolo mentale: moltiplicazioni (2)", role=ROLE_FOCUS, duration=60,
            sim_state="focus", stimulus="calcolo_moltiplicazioni",
            problem_kind="moltiplicazioni", problem_interval=7.0,
            instruction=COMMON + " Compariranno delle moltiplicazioni: calcolale a mente, "
                                 "senza dire il risultato. Non importa se non fai in tempo."),
        Block(
            key="artifacts", title="Movimenti volontari (controllo dei disturbi)", role=ROLE_ARTIFACT,
            duration=48, sim_state="neutral", stimulus="artefatti", trim=0,
            instruction="Seguirai alcune istruzioni su cosa fare: serrare la mascella, "
                        "sbattere le palpebre, muovere gli occhi. Serve a vedere come "
                        "appaiono i disturbi nel segnale.",
            prompts=(
                Prompt(2, "STRINGI la mascella forte per 3 secondi", "jaw"),
                Prompt(6, "rilassa", "neutral"),
                Prompt(10, "STRINGI la mascella forte per 3 secondi", "jaw"),
                Prompt(14, "rilassa", "neutral"),
                Prompt(18, "SBATTI le palpebre forte, 5 volte", "blink"),
                Prompt(24, "rilassa", "neutral"),
                Prompt(28, "MUOVI gli occhi a destra e a sinistra, lentamente", "eyes"),
                Prompt(36, "rilassa", "neutral"),
                Prompt(40, "STRINGI la mascella forte per 3 secondi", "jaw"),
                Prompt(44, "rilassa", "neutral"),
            )),
    )


def scaled(protocol: Tuple[Block, ...], factor: float) -> Tuple[Block, ...]:
    """Versione accorciata/allungata del protocollo (per prove rapide). Minimo 8 s per blocco."""
    if factor <= 0:
        raise ValueError("il fattore di scala deve essere positivo")
    out = []
    for b in protocol:
        duration = max(8.0, b.duration * factor)
        k = duration / b.duration
        out.append(replace(
            b, duration=duration, trim=min(b.trim, duration / 4.0) if b.trim else 0.0,
            prompts=tuple(Prompt(p.at * k, p.text, p.sim_state) for p in b.prompts),
            problem_interval=b.problem_interval * min(1.0, k) if b.problem_interval else 0.0))
    return tuple(out)


def make_problem(kind: str, rng: random.Random) -> Optional[str]:
    """Genera il testo di un problema da mostrare. Solo 'moltiplicazioni' per ora."""
    if kind == "moltiplicazioni":
        return "%d x %d" % (rng.randint(12, 49), rng.randint(3, 9))
    return None


def total_duration(protocol: Tuple[Block, ...]) -> float:
    return sum(b.duration for b in protocol)
