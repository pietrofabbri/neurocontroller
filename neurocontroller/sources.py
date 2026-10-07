"""Sorgenti di segnale: simulata, porta seriale, riproduzione da file CSV.

Tutte espongono la stessa interfaccia (`Source`): cosi' calibrazione e modalita'
live non sanno se dietro c'e' un sensore vero oppure no.

ATTENZIONE - il simulatore NON e' EEG:
  genera un segnale sintetico costruito secondo il MODELLO ASSUNTO dal progetto
  (alfa alto a occhi chiusi, beta alto durante il calcolo...). Serve a provare il
  programma senza sensore e a far girare i test. Che un classificatore riconosca
  quel segnale sintetico NON dimostra che funzioni su EEG vero.
"""
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

DEFAULT_FS = 250.0  # ASSUNZIONE: da verificare con il firmware reale (vedi docs/08)


class Source:
    """Interfaccia comune."""

    realtime = False      # True se read() attende davvero i dati (seriale)
    simulated = False     # True se il segnale e' sintetico
    description = "sorgente generica"
    fs: float = DEFAULT_FS
    # Valore massimo dell'ADC (1023 = 10 bit). Serve solo al controllo di saturazione: una scheda
    # con piu' bit (es. 4095 = 12 bit) va dichiarata con --adc-max, altrimenti il controllo
    # scambierebbe il segnale normale per un segnale saturo.
    adc_max: float = 1023.0

    def read(self, n: int) -> List[float]:  # pragma: no cover - interfaccia
        raise NotImplementedError

    def flush(self) -> None:
        """Scarta i dati accumulati (es. durante il conto alla rovescia)."""

    def set_state(self, state: str) -> None:
        """Solo per il simulatore: dice che stato simulare. Altrove non fa nulla."""

    def close(self) -> None:
        """Libera le risorse."""


# --------------------------------------------------------------------------------------
# Simulatore
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Persona:
    """Come reagisce una persona (inventata) ai diversi stati.

    reactivity: 1 = reazione "da manuale"; 0 = il segnale non cambia mai (caso in cui
    la calibrazione deve dichiararsi non affidabile).
    """

    name: str
    reactivity: float = 1.0
    alpha_hz: float = 10.0
    gain: float = 1.0
    noise: float = 2.0
    emg_gain: float = 1.0


PERSONAS: Dict[str, Persona] = {
    "tipica": Persona("tipica", reactivity=0.85, alpha_hz=10.0),
    "debole": Persona("debole", reactivity=0.3, alpha_hz=10.6),
    "nulla": Persona("nulla", reactivity=0.0, alpha_hz=9.4),
}

# Ampiezza efficace (RMS) per banda, in conteggi ADC, per ogni stato simulato.
_NEUTRAL = {"delta": 6.0, "theta": 4.0, "alpha": 6.0, "beta": 4.0, "gamma": 1.0}
_TARGETS: Dict[str, Dict[str, float]] = {
    # occhi chiusi: alfa molto alto
    "closed": {"delta": 5.0, "theta": 4.0, "alpha": 15.0, "beta": 3.0, "gamma": 0.8},
    # rilassamento a occhi aperti: alfa un po' piu' alto, beta basso
    "relax": {"delta": 5.5, "theta": 4.5, "alpha": 8.5, "beta": 3.0, "gamma": 0.8},
    # concentrazione (calcolo): alfa piu' basso, beta piu' alto
    "focus": {"delta": 5.0, "theta": 4.5, "alpha": 5.0, "beta": 6.5, "gamma": 1.4},
}
_BAND_CENTERS = {"delta": (1.8, 2.6, 3.4), "theta": (4.8, 6.0, 7.2), "alpha": (0.0, 0.0, 0.0),
                 "beta": (16.0, 21.0, 27.0), "gamma": (32.5, 36.0, 39.5)}
_MOD_DEPTH = 0.9  # variabilita' da una finestra all'altra (piu' alta = piu' difficile)
SIM_STATES = ("closed", "relax", "focus", "neutral", "jaw", "blink", "eyes")


class SimulatedSource(Source):
    """Segnale EEG sintetico con stati controllabili. NON e' EEG vero."""

    realtime = False
    simulated = True

    def __init__(self, fs: float = DEFAULT_FS, persona: Persona = PERSONAS["tipica"],
                 seed: Optional[int] = 0, script: Optional[Sequence[Tuple[str, float]]] = None):
        self.fs = float(fs)
        self.persona = persona
        self.description = "SIMULATO (persona %s): segnale sintetico, non EEG" % persona.name
        self._rng = random.Random(seed)
        self._state = "neutral"
        self._i = 0
        self._script: List[Tuple[str, float]] = list(script) if script else []
        self._script_pos = 0
        self._script_left = 0
        if self._script:
            self._load_script_step()
        self._phases: Dict[Tuple[str, int], float] = {}
        self._freqs: Dict[Tuple[str, int], float] = {}
        for band, centers in _BAND_CENTERS.items():
            for k, c in enumerate(centers):
                center = persona.alpha_hz + (-1.2, 0.0, 1.2)[k] if band == "alpha" else c
                self._freqs[(band, k)] = center
                self._phases[(band, k)] = self._rng.uniform(0, 2 * math.pi)
        self._mod = {b: 1.0 for b in _NEUTRAL}
        self._drift_phase = self._rng.uniform(0, 2 * math.pi)
        self._prev_white = 0.0
        self._blink_until = -1
        self._blink_start = 0
        self._next_blink = int(0.8 * self.fs)
        self._eye_sign = 1.0

    # -- controllo dello stato ------------------------------------------------------
    def set_state(self, state: str) -> None:
        if state not in SIM_STATES:
            raise ValueError("stato simulato sconosciuto %r: ammessi %s" % (state, ", ".join(SIM_STATES)))
        self._state = state

    def _load_script_step(self) -> None:
        state, seconds = self._script[self._script_pos % len(self._script)]
        self.set_state(state)
        self._script_left = max(1, int(round(seconds * self.fs)))

    def _amps(self) -> Dict[str, float]:
        target = _TARGETS.get(self._state)
        if target is None:  # neutral / jaw / blink / eyes: ampiezze di base
            return _NEUTRAL
        r = self.persona.reactivity
        return {b: _NEUTRAL[b] + r * (target[b] - _NEUTRAL[b]) for b in _NEUTRAL}

    # -- generazione --------------------------------------------------------------------
    def read(self, n: int) -> List[float]:
        out: List[float] = []
        rng = self._rng
        p = self.persona
        two_pi = 2 * math.pi
        amps = self._amps()
        for _ in range(n):
            if self._script:
                if self._script_left <= 0:
                    self._script_pos += 1
                    self._load_script_step()
                    amps = self._amps()
                self._script_left -= 1
            if self._i % int(max(1, self.fs // 2)) == 0:  # modulazione lenta dell'ampiezza
                for b in self._mod:
                    self._mod[b] = max(0.2, 0.8 * self._mod[b] + 0.2 * (1.0 + _MOD_DEPTH * rng.gauss(0, 1)))
                amps = self._amps()
            t = self._i / self.fs
            v = 0.0
            for (band, k), f in self._freqs.items():
                ph = self._phases[(band, k)] + two_pi * f * t
                rms = amps[band] * self._mod[band] / math.sqrt(3.0)
                v += rms * math.sqrt(2.0) * math.sin(ph)
            v += rng.gauss(0, p.noise)
            v += 1.0 * math.sin(two_pi * 50.0 * t)           # rete elettrica
            v += 10.0 * math.sin(two_pi * 0.2 * t + self._drift_phase)  # deriva lenta
            if self._state == "jaw":                          # muscoli: rumore ad alta frequenza
                white = rng.gauss(0, 25.0 * p.emg_gain)
                v += white - self._prev_white
                self._prev_white = white
            elif self._state == "blink":                      # ammiccamenti: impulsi lenti e grandi
                if self._i >= self._next_blink and self._blink_until < self._i:
                    self._blink_start = self._i
                    self._blink_until = self._i + int(0.25 * self.fs)
                    self._next_blink = self._i + int(rng.uniform(1.1, 1.8) * self.fs)
                if self._i <= self._blink_until:
                    x = (self._i - self._blink_start) / max(1, self._blink_until - self._blink_start)
                    v += 90.0 * math.sin(math.pi * x)
            elif self._state == "eyes":                       # movimenti oculari: gradini
                if self._i % int(1.2 * self.fs) == 0:
                    self._eye_sign = -self._eye_sign
                v += 35.0 * self._eye_sign
            out.append(min(1023.0, max(0.0, 512.0 + p.gain * v)))
            self._i += 1
        return out


# --------------------------------------------------------------------------------------
# Porta seriale
# --------------------------------------------------------------------------------------

_SPLIT = re.compile(r"[,;\t ]+")


def parse_line(raw: bytes, column: int = 0) -> Optional[float]:
    """Legge un campione da una riga ASCII ("512" oppure "512,498,..."). None se non valida."""
    try:
        text = raw.decode("ascii", errors="ignore").strip()
    except Exception:
        return None
    if not text:
        return None
    parts = [p for p in _SPLIT.split(text) if p]
    if column >= len(parts):
        return None
    try:
        return float(parts[column])
    except ValueError:
        return None


class SerialSource(Source):
    """Legge campioni da una porta seriale, una riga ASCII per campione.

    LIMITE NOTO: assume righe di testo (come il Serial Plotter di Arduino). Il
    firmware originale Chords puo' inviare pacchetti binari; il firmware modificato
    dal gruppo non e' ancora nel repository (vedi firmware/README.md). Quando sara'
    noto il formato reale, va aggiunto qui il parser corrispondente.
    """

    realtime = True
    simulated = False
    MAX_CONSECUTIVE_BAD = 200

    def __init__(self, port: str, baud: int = 115200, fs: float = DEFAULT_FS, column: int = 0,
                 timeout: float = 2.0, opener: Optional[Callable[[], object]] = None,
                 adc_max: float = 1023.0):
        self.fs = float(fs)
        self.adc_max = float(adc_max)
        self.column = column
        self.bad_lines = 0
        self.description = "seriale %s @ %d baud (assunti %.0f campioni/s)" % (port, baud, fs)
        if opener is None:
            try:
                import serial  # type: ignore  # pyserial
            except ImportError:
                raise RuntimeError(
                    "manca la libreria pyserial: installarla con  pip install pyserial") from None

            def opener() -> object:  # noqa: E306
                return serial.Serial(port, baud, timeout=timeout)
        self._ser = opener()

    def read(self, n: int) -> List[float]:
        out: List[float] = []
        consecutive_bad = 0
        while len(out) < n:
            line = self._ser.readline()
            if not line:
                raise TimeoutError("nessun dato dalla porta seriale: sensore spento, "
                                   "cavo scollegato o porta/baud sbagliati")
            value = parse_line(line, self.column)
            if value is None:
                self.bad_lines += 1
                consecutive_bad += 1
                if consecutive_bad > self.MAX_CONSECUTIVE_BAD:
                    raise ValueError("formato dei dati non riconosciuto: attese righe di testo con "
                                     "un numero per campione (ultima riga: %r)" % line[:40])
                continue
            consecutive_bad = 0
            out.append(value)
        return out

    def flush(self) -> None:
        reset = getattr(self._ser, "reset_input_buffer", None)
        if reset:
            reset()

    def close(self) -> None:
        close = getattr(self._ser, "close", None)
        if close:
            close()


def list_serial_ports() -> List[Tuple[str, str]]:
    """Porte seriali presenti, come (dispositivo, descrizione). Vuoto se pyserial manca.

    Serve a evitare di dover indovinare "COM3" o "/dev/ttyACM0": si collega l'Arduino e si
    lancia `python3 -m neurocontroller ports`.
    """
    try:
        from serial.tools import list_ports  # type: ignore  # pyserial
    except ImportError:
        return []
    return sorted((p.device, p.description or "") for p in list_ports.comports())


def pick_port(ports: Sequence[Tuple[str, str]]) -> Optional[str]:
    """Sceglie la porta da sola solo se non c'e' ambiguita': una sola porta disponibile."""
    return ports[0][0] if len(ports) == 1 else None


# --------------------------------------------------------------------------------------
# Riproduzione da file
# --------------------------------------------------------------------------------------

class CsvReplaySource(Source):
    """Rilegge campioni registrati (un valore per riga, o colonna scelta di un CSV)."""

    realtime = False
    simulated = False

    def __init__(self, path: str, fs: float = DEFAULT_FS, column: int = 0):
        self.fs = float(fs)
        self.description = "file %s (assunti %.0f campioni/s)" % (path, fs)
        values: List[float] = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                v = parse_line(line.encode("utf-8"), column)
                if v is not None:
                    values.append(v)
        if not values:
            raise ValueError("nessun campione numerico trovato in %s" % path)
        self._values = values
        self._pos = 0

    def read(self, n: int) -> List[float]:
        if self._pos + n > len(self._values):
            raise EOFError("il file e' finito (%d campioni disponibili)" % len(self._values))
        chunk = self._values[self._pos:self._pos + n]
        self._pos += n
        return chunk
