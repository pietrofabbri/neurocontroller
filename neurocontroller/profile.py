"""Profilo di calibrazione di una persona e classificatore di stato.

Metodo (dettagli e limiti in docs/08-calibrazione.md):

  1. Ogni finestra di segnale (2 s) diventa un indice  E = ln( beta / (alfa + theta) ),
     un rapporto tra bande usato in letteratura come indice di "engagement": sale
     quando la beta cresce e l'alfa cala. E' un rapporto, quindi non dipende dalla
     scala del sensore.
  2. Le soglie anti-artefatto (ampiezza e alta frequenza) sono ricavate dai blocchi
     "puliti" della stessa persona. Una finestra sopra soglia e' scartata.
  3. Per ogni persona si misurano media e dispersione di E nei blocchi "rilassato" e
     "concentrato" (entrambi a occhi aperti); la soglia di decisione sta tra i due.
  4. La qualita' NON si giudica sullo stesso blocco usato per tarare: si tara su una
     coppia di blocchi (rilassato 1 + concentrato 1) e si verifica sull'altra coppia
     (rilassato 2 + concentrato 2), e viceversa ("validazione tra blocchi").
  5. Se la calibrazione non regge, il profilo lo dichiara ("non affidabile") e la
     modalita' live si rifiuta di partire senza --force.
"""
from __future__ import annotations

import json
import math
import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import dsp
from .protocol import (PROTOCOL_ID, ROLE_ARTIFACT, ROLE_CHECK, ROLE_FOCUS, ROLE_RELAX, Block)

SCHEMA_VERSION = 1

STATE_RELAXED = "rilassato"
STATE_FOCUSED = "concentrato"
STATE_NEUTRAL = "neutro"
STATE_ARTIFACT = "artefatto"
ALL_STATES = (STATE_RELAXED, STATE_FOCUSED, STATE_NEUTRAL, STATE_ARTIFACT)

# Soglie di qualita' (euristiche, da validare su dati reali: vedi docs/08)
Q_USABLE_DPRIME = 1.5
Q_USABLE_ACC = 0.80
Q_WEAK_DPRIME = 0.8
Q_WEAK_ACC = 0.65
MIN_CLEAN_WINDOWS = 8
MAX_FALSE_ALARM = 0.05
RMS_FACTORS = (1.5, 2.0, 2.5, 3.0, 4.0, 5.0)
HF_FACTORS = (2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 20.0)
ID_PATTERN = re.compile(r"^P\d{2,3}$")


class ProfileError(Exception):
    """Errore nella costruzione o nella lettura di un profilo."""


@dataclass
class BlockData:
    """Risultato dell'analisi di un blocco registrato (solo finestre dopo il transitorio)."""

    key: str
    role: str
    stimulus: str
    features: List[dsp.Features]
    mean_psd: List[float]
    freqs: List[float]
    n_samples: int
    # Utile per il simulatore e per i test: non finisce nel profilo
    raw: Optional[List[float]] = None


def analyze_block(block: Block, samples: Sequence[float], fs: float, n: int, hop: int,
                  keep_raw: bool = False) -> BlockData:
    """Trasforma i campioni di un blocco in finestre di caratteristiche (dopo il transitorio)."""
    trim_samples = int(round(block.trim * fs))
    feats: List[dsp.Features] = []
    psd_sum: Optional[List[float]] = None
    freqs: List[float] = []
    for start, window in dsp.sliding_windows(samples, n, hop):
        if start < trim_samples:
            continue
        f, freqs, psd = dsp.analyze_window(window, fs)
        feats.append(f)
        psd_sum = list(psd) if psd_sum is None else [a + b for a, b in zip(psd_sum, psd)]
    mean_psd = [v / len(feats) for v in psd_sum] if feats and psd_sum else []
    return BlockData(key=block.key, role=block.role, stimulus=block.stimulus, features=feats,
                     mean_psd=mean_psd, freqs=freqs, n_samples=len(samples),
                     raw=list(samples) if keep_raw else None)


# --------------------------------------------------------------------------------------
# Soglie anti-artefatto
# --------------------------------------------------------------------------------------

def _pick_factor(values: Sequence[float], factors: Sequence[float], max_fpr: float
                 ) -> Tuple[float, float, float]:
    """Il fattore piu' piccolo per cui la soglia mediana*fattore scarta non piu' di max_fpr."""
    med = max(statistics.median(values), 1e-12)
    for f in factors:
        thr = med * f
        if sum(1 for v in values if v > thr) / len(values) <= max_fpr:
            return f, thr, med
    f = factors[-1]
    return f, med * f, med


def is_artifact(rms: float, hf_ratio: float, artifact: Dict[str, float]) -> bool:
    return rms > artifact["rms_thr"] or hf_ratio > artifact["hf_thr"]


# --------------------------------------------------------------------------------------
# Classificazione a una dimensione
# --------------------------------------------------------------------------------------

def _mean_std(values: Sequence[float]) -> Tuple[float, float]:
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return mean, math.sqrt(var)


def _decision(mu_r: float, sd_r: float, mu_f: float, sd_f: float) -> Tuple[float, float]:
    """Soglia (media pesata sulle dispersioni) e d' tra due classi."""
    sd_r = max(sd_r, 1e-6)
    sd_f = max(sd_f, 1e-6)
    threshold = (mu_r * sd_f + mu_f * sd_r) / (sd_r + sd_f)
    pooled = math.sqrt((sd_r ** 2 + sd_f ** 2) / 2.0)
    return threshold, (mu_f - mu_r) / pooled


def _balanced_accuracy(relax_vals: Sequence[float], focus_vals: Sequence[float],
                       threshold: float) -> float:
    rec_r = sum(1 for v in relax_vals if v < threshold) / len(relax_vals)
    rec_f = sum(1 for v in focus_vals if v >= threshold) / len(focus_vals)
    return (rec_r + rec_f) / 2.0


# --------------------------------------------------------------------------------------
# Profilo
# --------------------------------------------------------------------------------------

@dataclass
class Profile:
    participant_id: str
    created: str
    simulated: bool
    source: str
    electrode: str
    protocol: str
    fs: float
    window: int
    bands: Dict[str, Tuple[float, float]]
    artifact: Dict[str, Optional[float]]
    state: Dict[str, float]
    quality: Dict[str, object]
    blocks: Dict[str, Dict[str, object]]
    schema_version: int = SCHEMA_VERSION

    # -- uso ------------------------------------------------------------------------
    @property
    def level(self) -> str:
        return str(self.quality.get("level", "non affidabile"))

    @property
    def usable(self) -> bool:
        return self.level in ("usabile", "debole")

    # -- salvataggio ----------------------------------------------------------------
    def to_dict(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "participant_id": self.participant_id,
            "created": self.created,
            "simulated": self.simulated,
            "source": self.source,
            "electrode": self.electrode,
            "protocol": self.protocol,
            "fs": self.fs,
            "window": self.window,
            "bands": {k: list(v) for k, v in self.bands.items()},
            "artifact": self.artifact,
            "state": self.state,
            "quality": self.quality,
            "blocks": self.blocks,
        }

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    @classmethod
    def from_dict(cls, d: Dict[str, object]) -> "Profile":
        if d.get("schema_version") != SCHEMA_VERSION:
            raise ProfileError("versione di profilo non supportata: %r (attesa %d)"
                               % (d.get("schema_version"), SCHEMA_VERSION))
        try:
            return cls(
                participant_id=str(d["participant_id"]), created=str(d["created"]),
                simulated=bool(d["simulated"]), source=str(d["source"]),
                electrode=str(d["electrode"]), protocol=str(d["protocol"]),
                fs=float(d["fs"]), window=int(d["window"]),
                bands={k: (float(v[0]), float(v[1])) for k, v in dict(d["bands"]).items()},
                artifact=dict(d["artifact"]), state=dict(d["state"]),
                quality=dict(d["quality"]), blocks=dict(d["blocks"]))
        except KeyError as exc:
            raise ProfileError("profilo incompleto: manca il campo %s" % exc) from None

    @classmethod
    def load(cls, path: Path) -> "Profile":
        try:
            return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise ProfileError("file di profilo non valido (%s): %s" % (path, exc)) from None


def build_profile(blocks: Dict[str, BlockData], *, participant_id: str, fs: float, window: int,
                  electrode: str, source: str, simulated: bool, created: Optional[str] = None
                  ) -> Profile:
    """Costruisce il profilo dai blocchi analizzati. Non solleva se la qualita' e' scarsa:
    la dichiara nel profilo (`quality`)."""
    messages: List[str] = []

    def role_blocks(role: str) -> List[BlockData]:
        return [b for b in blocks.values() if b.role == role]

    # 1) soglie anti-artefatto dai blocchi puliti (rilassato + concentrato)
    clean = [f for b in role_blocks(ROLE_RELAX) + role_blocks(ROLE_FOCUS) for f in b.features]
    if len(clean) < MIN_CLEAN_WINDOWS:
        raise ProfileError("troppo pochi dati nei blocchi di rilassamento/calcolo (%d finestre): "
                           "registrazione interrotta o troppo corta" % len(clean))
    rms_f, rms_thr, rms_med = _pick_factor([f.rms for f in clean], RMS_FACTORS, MAX_FALSE_ALARM / 2)
    hf_f, hf_thr, hf_med = _pick_factor([f.hf_ratio for f in clean], HF_FACTORS, MAX_FALSE_ALARM / 2)
    artifact = {"rms_factor": rms_f, "rms_thr": rms_thr, "rms_median": rms_med,
                "hf_factor": hf_f, "hf_thr": hf_thr, "hf_median": hf_med}

    def flagged(f: dsp.Features) -> bool:
        return is_artifact(f.rms, f.hf_ratio, artifact)

    false_alarm = sum(1 for f in clean if flagged(f)) / len(clean)
    artifact["false_alarm_rate"] = false_alarm
    art_blocks = role_blocks(ROLE_ARTIFACT)
    art_windows = [f for b in art_blocks for f in b.features]
    hit_rate = (sum(1 for f in art_windows if flagged(f)) / len(art_windows)) if art_windows else None
    artifact["hit_rate"] = hit_rate
    if hit_rate is None:
        messages.append("blocco dei movimenti volontari assente: non e' possibile controllare "
                        "che i disturbi (mascella, palpebre) si vedano nel segnale.")
    elif hit_rate < 0.20:
        messages.append("i movimenti volontari (mascella, palpebre) quasi non si vedono nel segnale "
                        "(%.0f%% delle finestre): il sensore potrebbe non essere a contatto o non "
                        "in posizione frontale; i disturbi reali potrebbero passare inosservati."
                        % (100 * hit_rate))

    # 2) controllo del sensore: effetto Berger (alfa piu' alta a occhi chiusi che a occhi aperti)
    berger = None
    closed = role_blocks(ROLE_CHECK)
    open_eyes = [f for b in role_blocks(ROLE_RELAX) + role_blocks(ROLE_FOCUS)
                 for f in b.features if not flagged(f)]
    closed_clean = [f for f in closed[0].features if not flagged(f)] if closed else []
    if closed_clean and open_eyes:
        a_closed = statistics.median(f.absolute["alpha"] for f in closed_clean)
        a_open = statistics.median(f.absolute["alpha"] for f in open_eyes)
        if a_open > 0:
            berger = a_closed / a_open
            if berger < 1.2:
                messages.append("a occhi chiusi l'alfa non aumenta rispetto a occhi aperti "
                                "(rapporto %.2f), mentre nella maggior parte delle persone "
                                "aumenta nettamente: controllare contatto e posizione degli "
                                "elettrodi." % berger)

    # 3) statistiche degli stati (solo finestre pulite)
    def clean_E(b: BlockData) -> List[float]:
        return [f.engagement for f in b.features if not flagged(f)]

    relax_sets = {b.key: clean_E(b) for b in role_blocks(ROLE_RELAX)}
    focus_sets = {b.key: clean_E(b) for b in role_blocks(ROLE_FOCUS)}
    all_r = [v for vs in relax_sets.values() for v in vs]
    all_f = [v for vs in focus_sets.values() for v in vs]
    if len(all_r) < MIN_CLEAN_WINDOWS or len(all_f) < MIN_CLEAN_WINDOWS:
        raise ProfileError("troppe finestre scartate come disturbo (rilassato: %d, concentrato: %d "
                           "utili): ripetere la calibrazione restando piu' fermi" % (len(all_r), len(all_f)))
    mu_r, sd_r = _mean_std(all_r)
    mu_f, sd_f = _mean_std(all_f)
    threshold, dprime = _decision(mu_r, sd_r, mu_f, sd_f)
    state = {"relax_mean": mu_r, "relax_std": sd_r, "focus_mean": mu_f, "focus_std": sd_f,
             "threshold": threshold, "dprime": dprime,
             "n_relax": float(len(all_r)), "n_focus": float(len(all_f))}

    # 4) validazione tra blocchi: tara su un gruppo, verifica sull'altro (e viceversa)
    def suffix(key: str) -> str:
        return key.rsplit("_", 1)[-1]

    groups = sorted({suffix(k) for k in list(relax_sets) + list(focus_sets)})
    accuracies: List[float] = []
    if len(groups) >= 2:
        for test_g in groups:
            tr_r = [v for k, vs in relax_sets.items() if suffix(k) != test_g for v in vs]
            tr_f = [v for k, vs in focus_sets.items() if suffix(k) != test_g for v in vs]
            te_r = [v for k, vs in relax_sets.items() if suffix(k) == test_g for v in vs]
            te_f = [v for k, vs in focus_sets.items() if suffix(k) == test_g for v in vs]
            if min(len(tr_r), len(tr_f), len(te_r), len(te_f)) < 3:
                continue
            m_r, s_r = _mean_std(tr_r)
            m_f, s_f = _mean_std(tr_f)
            thr, _ = _decision(m_r, s_r, m_f, s_f)
            accuracies.append(_balanced_accuracy(te_r, te_f, thr))
    cv_acc = statistics.mean(accuracies) if accuracies else None

    direction_ok = mu_f > mu_r
    if not direction_ok:
        messages.append("l'indice e' piu' ALTO a riposo che durante il calcolo: per questa persona il "
                        "segnale va nella direzione opposta a quella attesa, quindi non e' "
                        "interpretabile come 'concentrazione'.")
    if cv_acc is None:
        level = "non affidabile"
        messages.append("impossibile validare la calibrazione tra blocchi separati (dati insufficienti).")
    elif direction_ok and dprime >= Q_USABLE_DPRIME and cv_acc >= Q_USABLE_ACC:
        level = "usabile"
    elif direction_ok and dprime >= Q_WEAK_DPRIME and cv_acc >= Q_WEAK_ACC:
        level = "debole"
        messages.append("la distinzione tra rilassato e concentrato e' debole: il controllo sara' "
                        "impreciso. Provare a ripetere in un ambiente silenzioso e con i sensori "
                        "ben a contatto.")
    else:
        level = "non affidabile"
        messages.append("il segnale non distingue in modo ripetibile il rilassamento dal calcolo "
                        "(d'=%.2f, accuratezza tra blocchi %s). Possibili cause: contatto "
                        "elettrodi, posizione, ambiente rumoroso, oppure questo sensore/posizione "
                        "non e' adatto a questa persona." %
                        (dprime, "%.0f%%" % (100 * cv_acc) if cv_acc is not None else "n.d."))
    quality = {"level": level, "cross_block_accuracy": cv_acc, "dprime": dprime,
               "berger_ratio": berger, "direction_ok": direction_ok, "messages": messages}

    block_summary: Dict[str, Dict[str, object]] = {}
    for key, b in blocks.items():
        n = len(b.features)
        block_summary[key] = {
            "role": b.role, "stimulus": b.stimulus, "n_windows": n,
            "n_flagged": sum(1 for f in b.features if flagged(f)),
            "mean_rel": ({band: statistics.mean(f.rel[band] for f in b.features)
                          for band in dsp.BAND_NAMES} if n else {}),
            "mean_engagement": statistics.mean(f.engagement for f in b.features) if n else None,
        }

    return Profile(
        participant_id=participant_id,
        created=created or datetime.now().astimezone().isoformat(timespec="seconds"),
        simulated=simulated, source=source, electrode=electrode, protocol=PROTOCOL_ID,
        fs=fs, window=window, bands=dict(dsp.BANDS), artifact=artifact, state=state,
        quality=quality, blocks=block_summary)


# --------------------------------------------------------------------------------------
# Classificatore live
# --------------------------------------------------------------------------------------

@dataclass
class StateResult:
    state: str
    score: float       # -1 = tipico del rilassato, +1 = tipico del concentrato (fuori scala possibile)
    engagement: float
    artifact: bool


class StateClassifier:
    """Trasforma una finestra di caratteristiche nello stato mentale della persona calibrata.

    - finestra sopra le soglie di disturbo -> "artefatto" (non entra nella media);
    - altrimenti il punteggio e' la posizione dell'indice E tra le medie dei due stati,
      mediata sulle ultime `smooth` finestre pulite;
    - dentro la fascia `margin` attorno alla soglia lo stato e' "neutro".
    """

    def __init__(self, profile: Profile, margin: float = 0.25, smooth: int = 3):
        if smooth < 1:
            raise ValueError("smooth deve essere >= 1")
        if not 0.0 <= margin < 1.0:
            raise ValueError("margin deve stare in [0, 1)")
        self.profile = profile
        self.margin = margin
        self.smooth = smooth
        st = profile.state
        self._thr = st["threshold"]
        self._half_gap = max((st["focus_mean"] - st["relax_mean"]) / 2.0, 1e-6)
        self._history: List[float] = []

    def reset(self) -> None:
        self._history.clear()

    def update(self, features: dsp.Features) -> StateResult:
        if is_artifact(features.rms, features.hf_ratio, self.profile.artifact):
            return StateResult(STATE_ARTIFACT, 0.0, features.engagement, True)
        score = (features.engagement - self._thr) / self._half_gap
        self._history.append(score)
        if len(self._history) > self.smooth:
            self._history.pop(0)
        avg = sum(self._history) / len(self._history)
        if avg > self.margin:
            state = STATE_FOCUSED
        elif avg < -self.margin:
            state = STATE_RELAXED
        else:
            state = STATE_NEUTRAL
        return StateResult(state, avg, features.engagement, False)


# --------------------------------------------------------------------------------------
# Cartelle e identificativi
# --------------------------------------------------------------------------------------

def check_participant_id(pid: str, allow_custom: bool = False) -> str:
    """Gli identificativi sono anonimi (P01, P02...): niente nomi nei file."""
    if ID_PATTERN.match(pid):
        return pid
    if allow_custom and re.match(r"^[A-Za-z0-9_-]{1,16}$", pid):
        return pid
    raise ProfileError("identificativo %r non ammesso: usare un codice anonimo tipo P01, P02... "
                       "(niente nomi di persone; --allow-custom-id solo se sai cosa stai facendo)" % pid)


def next_participant_id(profiles_dir: Path) -> str:
    used = set()
    if Path(profiles_dir).is_dir():
        for p in Path(profiles_dir).glob("P*.json"):
            m = re.match(r"^P(\d+)", p.stem)
            if m:
                used.add(int(m.group(1)))
    n = 1
    while n in used:
        n += 1
    return "P%02d" % n
