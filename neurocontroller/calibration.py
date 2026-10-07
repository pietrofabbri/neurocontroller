"""Procedura guidata di calibrazione per persona.

Una chiamata a `run_calibration` esegue l'intero protocollo, costruisce il profilo e
salva i file. L'interfaccia utente e' separata (`ConsoleUI` / `QuietUI`) cosi' la
stessa logica gira in un terminale, in un test o in una futura interfaccia grafica.
"""
from __future__ import annotations

import csv
import os
import random
import textwrap
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import dsp
from .profile import (BlockData, Profile, ProfileError, analyze_block, build_profile,
                      check_participant_id)
from .protocol import Block, default_protocol, make_problem
from .sources import Source


class CalibrationError(Exception):
    """La calibrazione non puo' proseguire (segnale assente, interruzione...)."""


def default_data_dir() -> Path:
    """Cartella dei dati: $NEUROCONTROLLER_DATA oppure <repository>/data."""
    env = os.environ.get("NEUROCONTROLLER_DATA")
    return Path(env) if env else Path(__file__).resolve().parent.parent / "data"


# --------------------------------------------------------------------------------------
# Interfacce utente
# --------------------------------------------------------------------------------------

class QuietUI:
    """Non stampa e non attende: per test e per sorgenti simulate."""

    quiet_prompts = True

    def __init__(self) -> None:
        self.log: List[str] = []

    def info(self, text: str) -> None:
        self.log.append(text)

    def show_block(self, block: Block, index: int, total: int) -> None:
        self.log.append("[%d/%d] %s" % (index, total, block.title))

    def wait_ready(self) -> None:
        pass

    def countdown(self, seconds: int, sleep: bool) -> None:
        pass

    def prompt(self, text: str) -> None:
        self.log.append("  > " + text)


class ConsoleUI(QuietUI):
    """Terminale in italiano. `input_fn`/`print_fn`/`sleep_fn` sono sostituibili nei test."""

    def __init__(self, auto_start: bool = False, quiet_prompts: bool = False,
                 input_fn: Callable[[str], str] = input, print_fn: Callable[[str], None] = print,
                 sleep_fn: Callable[[float], None] = time.sleep):
        super().__init__()
        self.auto_start = auto_start
        self.quiet_prompts = quiet_prompts
        self._input = input_fn
        self._print = print_fn
        self._sleep = sleep_fn

    def info(self, text: str) -> None:
        self._print(text)

    def show_block(self, block: Block, index: int, total: int) -> None:
        self._print("")
        self._print("=" * 64)
        self._print("[%d/%d] %s  (%d secondi)" % (index, total, block.title, round(block.duration)))
        self._print("=" * 64)
        self._print(textwrap.fill(block.instruction, width=70))

    def wait_ready(self) -> None:
        if not self.auto_start:
            self._input("\nPremi INVIO quando sei pronto/a (poi niente tastiera fino alla fine del blocco)... ")

    def countdown(self, seconds: int, sleep: bool) -> None:
        for s in range(seconds, 0, -1):
            self._print("  si parte tra %d..." % s)
            if sleep:
                self._sleep(1.0)
        self._print("  VIA!")

    def prompt(self, text: str) -> None:
        if not self.quiet_prompts:
            self._print("  >>> " + text)


# --------------------------------------------------------------------------------------
# Registrazione
# --------------------------------------------------------------------------------------

def record_block(source: Source, block: Block, ui: QuietUI, rng: random.Random) -> List[float]:
    """Registra un blocco, mostrando le istruzioni a tempo. Restituisce i campioni."""
    fs = source.fs
    total = int(round(block.duration * fs))
    chunk = max(1, int(fs))  # un secondo alla volta
    prompts = sorted(block.prompts, key=lambda p: p.at)
    next_problem = 0.0
    samples: List[float] = []
    while len(samples) < total:
        t = len(samples) / fs
        while prompts and prompts[0].at <= t:
            due = prompts.pop(0)
            ui.prompt(due.text)
            if due.sim_state:
                source.set_state(due.sim_state)  # solo il simulatore reagisce
        if block.problem_kind and block.problem_interval > 0 and t >= next_problem:
            text = make_problem(block.problem_kind, rng)
            if text:
                ui.prompt(text)
            next_problem += block.problem_interval
        samples.extend(source.read(min(chunk, total - len(samples))))
    return samples


def check_signal(source: Source, ui: QuietUI, seconds: float = 5.0) -> Dict[str, object]:
    """Controllo preliminare del segnale. Solleva CalibrationError se il segnale e' inutilizzabile."""
    source.set_state("neutral")
    source.flush()
    data = source.read(int(seconds * source.fs))
    q = dsp.signal_quality(data, source.fs, adc_max=source.adc_max)
    if not q["ok"]:
        raise CalibrationError("controllo del segnale fallito: " + "; ".join(q["problems"]))  # type: ignore[arg-type]
    ui.info("Controllo del segnale: ok (ampiezza %.1f, disturbo di rete %.2f)"
            % (q["std"], q["mains_ratio"]))
    return q


def run_calibration(source: Source, participant_id: str, *,
                    protocol: Optional[Sequence[Block]] = None, electrode: str = "fronte",
                    ui: Optional[QuietUI] = None, seed: Optional[int] = None,
                    keep_raw: bool = False, skip_check: bool = False,
                    allow_custom_id: bool = False, hop_fraction: float = 0.5
                    ) -> Tuple[Profile, Dict[str, BlockData]]:
    """Esegue il protocollo e restituisce (profilo, dati dei blocchi). Non scrive file."""
    check_participant_id(participant_id, allow_custom_id)
    ui = ui or QuietUI()
    protocol = tuple(protocol) if protocol is not None else default_protocol()
    fs = source.fs
    n = dsp.window_size(fs)
    hop = max(1, int(n * hop_fraction))
    rng = random.Random(seed)

    if source.simulated:
        ui.info("*** SEGNALE SIMULATO: non e' EEG vero. Serve solo a provare il programma. ***")
    if not skip_check:
        check_signal(source, ui)

    blocks: Dict[str, BlockData] = {}
    try:
        for i, block in enumerate(protocol, start=1):
            ui.show_block(block, i, len(protocol))
            ui.wait_ready()
            ui.countdown(5, sleep=source.realtime)
            source.flush()
            source.set_state(block.sim_state)
            samples = record_block(source, block, ui, rng)
            blocks[block.key] = analyze_block(block, samples, fs, n, hop, keep_raw=keep_raw)
            ui.info("  fatto (%d finestre utili)" % len(blocks[block.key].features))
    except KeyboardInterrupt:
        raise CalibrationError("calibrazione interrotta: nessun profilo salvato") from None
    except (TimeoutError, EOFError) as exc:
        raise CalibrationError("registrazione interrotta: %s" % exc) from exc

    profile = build_profile(blocks, participant_id=participant_id, fs=fs, window=n,
                            electrode=electrode, source=source.description,
                            simulated=source.simulated)
    return profile, blocks


# --------------------------------------------------------------------------------------
# Salvataggio
# --------------------------------------------------------------------------------------

CSV_COLUMNS = ["participant_id", "session_date", "stimulus", "electrode_position", "band",
               "peak_hz", "peak_value", "mean_rel_power", "n_windows", "notes"]


def blocks_to_rows(profile: Profile, blocks: Dict[str, BlockData]) -> List[Dict[str, object]]:
    """Una riga per blocco e banda: picco dello spettro medio e potenza relativa media.

    E' il formato richiesto dal piano di test originale (F2): "per ogni test annotare
    il punto di massimo per ciascuna onda".
    """
    date = profile.created[:10]
    rows: List[Dict[str, object]] = []
    for key, b in blocks.items():
        if not b.features:
            continue
        for band, (lo, hi) in dsp.BANDS.items():
            idx = [i for i, f in enumerate(b.freqs) if lo <= f < hi]
            if idx:
                best = max(idx, key=lambda i: b.mean_psd[i])
                peak_hz, peak_value = b.freqs[best], b.mean_psd[best]
            else:
                peak_hz, peak_value = "", ""
            mean_rel = sum(f.rel[band] for f in b.features) / len(b.features)
            rows.append({
                "participant_id": profile.participant_id, "session_date": date,
                "stimulus": b.stimulus, "electrode_position": profile.electrode, "band": band,
                "peak_hz": ("%.2f" % peak_hz) if peak_hz != "" else "",
                "peak_value": ("%.4g" % peak_value) if peak_value != "" else "",
                "mean_rel_power": "%.4f" % mean_rel, "n_windows": len(b.features),
                "notes": "blocco %s%s" % (key, "; SIMULATO" if profile.simulated else "")})
    return rows


def save_session(profile: Profile, blocks: Dict[str, BlockData], data_dir: Path,
                 save_raw: bool = False) -> Dict[str, Path]:
    """Scrive profilo, tabella dei blocchi ed eventualmente i campioni grezzi.

    Le tre cartelle sono ignorate da Git (vedi .gitignore): contengono dati
    fisiologici di persone, anche se anonimi.
    """
    data_dir = Path(data_dir)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    paths: Dict[str, Path] = {}
    paths["profile"] = data_dir / "profiles" / ("%s.json" % profile.participant_id)
    profile.save(paths["profile"])
    csv_path = data_dir / "sessions" / ("%s_%s_blocchi.csv" % (profile.participant_id, stamp))
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(blocks_to_rows(profile, blocks))
    paths["blocks_csv"] = csv_path
    if save_raw:
        raw_dir = data_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        for key, b in blocks.items():
            if b.raw is None:
                continue
            p = raw_dir / ("%s_%s_%s.csv" % (profile.participant_id, stamp, key))
            p.write_text("\n".join("%.3f" % v for v in b.raw) + "\n", encoding="utf-8")
            paths["raw_" + key] = p
    return paths


def report_text(profile: Profile) -> str:
    """Riassunto leggibile del profilo, da mostrare a fine calibrazione."""
    q = profile.quality
    acc = q.get("cross_block_accuracy")
    lines = ["", "-" * 64,
             "PROFILO %s  -  qualita': %s" % (profile.participant_id, profile.level.upper()),
             "-" * 64,
             "  separazione rilassato/concentrato (d'): %.2f" % float(q["dprime"]),  # type: ignore[arg-type]
             "  accuratezza tra blocchi separati:      %s" %
             (("%.0f%%" % (100 * float(acc))) if acc is not None else "n.d."),  # type: ignore[arg-type]
             "  disturbi riconosciuti (movimenti):     %s" %
             (("%.0f%%" % (100 * float(profile.artifact["hit_rate"])))  # type: ignore[arg-type]
              if profile.artifact.get("hit_rate") is not None else "n.d."),
             "  falsi allarmi sui blocchi puliti:      %.0f%%" % (100 * float(profile.artifact["false_alarm_rate"]))]  # type: ignore[arg-type]
    for m in q.get("messages", []):  # type: ignore[union-attr]
        lines.append("  ! " + str(m))
    if profile.simulated:
        lines.append("  (profilo SIMULATO: non e' stato misurato nessun cervello)")
    return "\n".join(lines)
