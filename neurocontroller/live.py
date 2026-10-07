"""Modalita' live: legge il segnale, riconosce lo stato mentale della persona calibrata
e (se richiesto) manda il comando al gioco."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from . import dsp
from .game_link import GameLink
from .profile import Profile, StateClassifier, StateResult
from .sources import Source


class LiveError(Exception):
    """Impossibile avviare o proseguire la modalita' live."""


@dataclass
class LiveUpdate:
    t: float                  # secondi di segnale dall'inizio
    result: StateResult
    command: Optional[str]    # comando inviato al gioco (None se nessuno)


class LiveRunner:
    def __init__(self, source: Source, classifier: StateClassifier, link: Optional[GameLink] = None,
                 hop_fraction: float = 0.25, on_update: Optional[Callable[[LiveUpdate], None]] = None):
        profile = classifier.profile
        if abs(source.fs - profile.fs) > 1e-6:
            raise LiveError("la frequenza di campionamento della sorgente (%.0f Hz) e' diversa da quella "
                            "del profilo (%.0f Hz): ricalibrare" % (source.fs, profile.fs))
        if not 0.0 < hop_fraction <= 1.0:
            raise ValueError("hop_fraction deve stare in (0, 1]")
        self.source = source
        self.classifier = classifier
        self.link = link
        self.n = profile.window
        self.hop = max(1, int(self.n * hop_fraction))
        self.on_update = on_update

    def run(self, seconds: Optional[float] = None) -> List[LiveUpdate]:
        """Esegue per `seconds` secondi di segnale (all'infinito se None, fino a Ctrl+C)."""
        fs = self.source.fs
        self.classifier.reset()
        updates: List[LiveUpdate] = []
        self.source.flush()
        buffer = self.source.read(self.n)
        read = len(buffer)
        try:
            while True:
                feats, _, _ = dsp.analyze_window(buffer, fs)
                result = self.classifier.update(feats)
                command = self.link.send_state(result.state) if self.link else None
                update = LiveUpdate(read / fs, result, command)
                updates.append(update)
                if self.on_update:
                    self.on_update(update)
                if seconds is not None and read / fs >= seconds:
                    break
                new = self.source.read(self.hop)
                read += len(new)
                buffer = buffer[len(new):] + new
        except KeyboardInterrupt:
            pass
        except (TimeoutError, EOFError) as exc:
            raise LiveError("lettura interrotta: %s" % exc) from exc
        return updates
