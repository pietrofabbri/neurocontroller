"""Elaborazione del segnale: FFT, spettro di potenza, potenza per banda, indici.

Solo libreria standard, cosi' gira su qualsiasi PC senza installare nulla.
La FFT e' una radix-2 iterativa: va bene per finestre di qualche centinaio di
campioni (es. 512), non per grandi moli di dati.

Convenzioni:
  - le bande sono intervalli contigui [basso, alto): le soglie della scheda di
    progetto (3,9 / 7,5 / 13,9 Hz) sono approssimate a 4 / 8 / 14 Hz;
  - la potenza "totale" e' quella tra 1 e 42 Hz;
  - le potenze sono in unita' arbitrarie (conteggi ADC al quadrato / Hz): gli
    indici usati dal progetto sono sempre RAPPORTI, quindi indipendenti dalla scala.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterator, List, Sequence, Tuple

BANDS: Dict[str, Tuple[float, float]] = {
    "delta": (1.0, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 14.0),
    "beta": (14.0, 30.0),
    "gamma": (30.0, 42.0),
}
BAND_NAMES = tuple(BANDS)
TOTAL_RANGE = (1.0, 42.0)
MAINS_RANGE = (48.0, 52.0)  # rete elettrica europea, 50 Hz
_EPS = 1e-12

_TWIDDLES: Dict[int, List[complex]] = {}
_HANN: Dict[int, List[float]] = {}


def _twiddles(n: int) -> List[complex]:
    table = _TWIDDLES.get(n)
    if table is None:
        table = [
            complex(math.cos(-2.0 * math.pi * k / n), math.sin(-2.0 * math.pi * k / n))
            for k in range(n // 2)
        ]
        _TWIDDLES[n] = table
    return table


def fft(x: Sequence[float]) -> List[complex]:
    """FFT radix-2. La lunghezza deve essere una potenza di 2."""
    n = len(x)
    if n == 0 or n & (n - 1):
        raise ValueError("la lunghezza deve essere una potenza di 2 (ricevuti %d campioni)" % n)
    a = [complex(v) for v in x]
    j = 0
    for i in range(1, n):  # permutazione bit-reversal
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    tw = _twiddles(n)
    size = 2
    while size <= n:
        half = size // 2
        step = n // size
        for start in range(0, n, size):
            k = 0
            for off in range(start, start + half):
                u = a[off]
                v = a[off + half] * tw[k]
                a[off] = u + v
                a[off + half] = u - v
                k += step
        size <<= 1
    return a


def next_pow2(n: int) -> int:
    p = 1
    while p < n:
        p <<= 1
    return p


def window_size(fs: float, seconds: float = 2.0) -> int:
    """Lunghezza (potenza di 2) della finestra di analisi: almeno `seconds` secondi."""
    return next_pow2(int(math.ceil(seconds * fs)))


def _hann(n: int) -> List[float]:
    w = _HANN.get(n)
    if w is None:
        w = [0.5 - 0.5 * math.cos(2.0 * math.pi * k / (n - 1)) for k in range(n)]
        _HANN[n] = w
    return w


def detrend(x: Sequence[float]) -> List[float]:
    """Toglie media e andamento lineare (deriva lenta del segnale)."""
    n = len(x)
    if n < 2:
        return [float(v) for v in x]
    mean_i = (n - 1) / 2.0
    mean_x = sum(x) / n
    num = 0.0
    den = 0.0
    for i, v in enumerate(x):
        num += (i - mean_i) * (v - mean_x)
        den += (i - mean_i) ** 2
    slope = num / den if den else 0.0
    return [v - mean_x - slope * (i - mean_i) for i, v in enumerate(x)]


def power_spectrum(window: Sequence[float], fs: float) -> Tuple[List[float], List[float], float]:
    """Spettro di potenza a un lato (finestra di Hann).

    Restituisce (frequenze, densita' di potenza, rms del segnale senza deriva).
    """
    n = len(window)
    x = detrend(window)
    rms = math.sqrt(sum(v * v for v in x) / n)
    w = _hann(n)
    spec = fft([xi * wi for xi, wi in zip(x, w)])
    scale = 1.0 / (fs * sum(wi * wi for wi in w))
    half = n // 2
    psd = []
    for k in range(half + 1):
        p = (spec[k].real ** 2 + spec[k].imag ** 2) * scale
        if 0 < k < half:
            p *= 2.0
        psd.append(p)
    freqs = [k * fs / n for k in range(half + 1)]
    return freqs, psd, rms


def band_power(freqs: Sequence[float], psd: Sequence[float], lo: float, hi: float,
               exclude: Tuple[float, float] = (0.0, 0.0)) -> float:
    """Potenza nella banda [lo, hi), escludendo eventualmente l'intervallo `exclude`."""
    if len(freqs) < 2:
        return 0.0
    df = freqs[1] - freqs[0]
    total = 0.0
    for f, p in zip(freqs, psd):
        if lo <= f < hi and not (exclude[0] <= f < exclude[1]):
            total += p
    return total * df


@dataclass
class Features:
    """Caratteristiche di una finestra di segnale."""

    rel: Dict[str, float]        # potenza relativa per banda (somma ~ 1)
    absolute: Dict[str, float]   # potenza assoluta per banda (unita' arbitrarie)
    total: float                 # potenza 1-42 Hz
    rms: float                   # ampiezza efficace del segnale (conteggi ADC)
    hf_ratio: float              # potenza oltre 42 Hz / potenza 1-42 Hz (indizio di muscoli)
    engagement: float            # ln( beta / (alpha + theta) )

    def to_dict(self) -> Dict[str, object]:
        return {
            "rel": dict(self.rel),
            "absolute": dict(self.absolute),
            "total": self.total,
            "rms": self.rms,
            "hf_ratio": self.hf_ratio,
            "engagement": self.engagement,
        }


def analyze_window(window: Sequence[float], fs: float) -> Tuple[Features, List[float], List[float]]:
    """Calcola le caratteristiche di una finestra. Restituisce (Features, frequenze, psd)."""
    freqs, psd, rms = power_spectrum(window, fs)
    absolute = {name: band_power(freqs, psd, lo, hi) for name, (lo, hi) in BANDS.items()}
    total = band_power(freqs, psd, TOTAL_RANGE[0], TOTAL_RANGE[1])
    rel = {name: (v / total if total > _EPS else 0.0) for name, v in absolute.items()}
    nyq = fs / 2.0
    if nyq >= 60.0:
        hf = band_power(freqs, psd, TOTAL_RANGE[1], nyq, exclude=MAINS_RANGE)
    else:  # campionamento basso: l'unico indizio disponibile e' la banda gamma
        hf = absolute["gamma"]
    hf_ratio = hf / total if total > _EPS else 0.0
    engagement = math.log(
        (absolute["beta"] + _EPS) / (absolute["alpha"] + absolute["theta"] + _EPS)
    )
    feats = Features(rel=rel, absolute=absolute, total=total, rms=rms,
                     hf_ratio=hf_ratio, engagement=engagement)
    return feats, freqs, psd


def sliding_windows(samples: Sequence[float], n: int, hop: int) -> Iterator[Tuple[int, Sequence[float]]]:
    """Genera (indice di inizio, finestra) con passo `hop`."""
    if n <= 0 or hop <= 0:
        raise ValueError("n e hop devono essere positivi")
    for start in range(0, len(samples) - n + 1, hop):
        yield start, samples[start:start + n]


def signal_quality(samples: Sequence[float], fs: float, adc_min: float = 0.0,
                   adc_max: float = 1023.0, flat_std: float = 0.5) -> Dict[str, object]:
    """Controllo grossolano del segnale prima di calibrare.

    Segnala: segnale piatto (sensore scollegato/non alimentato), saturazione dell'ADC,
    forte disturbo di rete a 50 Hz. Non dimostra che il segnale sia EEG: dice solo
    se e' ragionevole procedere.
    """
    problems: List[str] = []
    n = len(samples)
    if n < 2:
        return {"ok": False, "std": 0.0, "clip_fraction": 0.0, "mains_ratio": 0.0,
                "problems": ["pochissimi campioni ricevuti"]}
    mean = sum(samples) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in samples) / n)
    clipped = sum(1 for v in samples if v <= adc_min or v >= adc_max)
    clip_fraction = clipped / n
    mains_ratio = 0.0
    nwin = 1 << (n.bit_length() - 1)
    if nwin >= 128 and fs / 2.0 > MAINS_RANGE[1]:
        freqs, psd, _ = power_spectrum(samples[:nwin], fs)
        total = band_power(freqs, psd, TOTAL_RANGE[0], TOTAL_RANGE[1])
        mains = band_power(freqs, psd, MAINS_RANGE[0], MAINS_RANGE[1])
        mains_ratio = mains / total if total > _EPS else 0.0
    if std < flat_std:
        problems.append("segnale piatto: sensore scollegato, non alimentato o porta sbagliata")
    if clip_fraction > 0.02:
        problems.append("il segnale tocca i limiti dell'ADC (%.0f%% dei campioni): "
                        "guadagno troppo alto o elettrodi non a contatto" % (100 * clip_fraction))
    if mains_ratio > 1.0:
        problems.append("forte disturbo a 50 Hz (rete elettrica): allontanarsi da cavi e "
                        "alimentatori, usare il computer a batteria")
    return {"ok": not problems, "std": std, "clip_fraction": clip_fraction,
            "mains_ratio": mains_ratio, "problems": problems}
