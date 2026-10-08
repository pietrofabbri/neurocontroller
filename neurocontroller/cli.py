"""Riga di comando:  python3 -m neurocontroller <comando>

  ports       elenca le porte seriali (per trovare quella dell'Arduino)
  check       controlla che il sensore mandi un segnale sensato
  calibrate   calibrazione guidata di una persona (crea il profilo)
  live        riconosce lo stato mentale in tempo reale (e comanda il gioco)
  demo        prova completa SENZA sensore, con segnale simulato
  profiles    elenca i profili salvati
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from . import __version__, dsp
from .calibration import (CalibrationError, ConsoleUI, check_signal, default_data_dir, report_text,
                          run_calibration, save_session)
from .game_link import DEFAULT_HOST, DEFAULT_MAPPING, DEFAULT_PORT, GameLink, parse_mapping
from .live import LiveError, LiveRunner, LiveUpdate
from .profile import (Profile, ProfileError, StateClassifier, check_participant_id,
                      next_participant_id)
from .protocol import default_protocol, scaled
from .sources import (DEFAULT_FS, PERSONAS, CsvReplaySource, SerialSource, SimulatedSource, Source,
                      list_serial_ports, pick_port)

DEFAULT_SCRIPT = "relax:12,focus:12,jaw:3,relax:8,focus:8"


class CliError(Exception):
    """Errore d'uso: mostrato all'utente senza traceback."""


# --------------------------------------------------------------------------------------
# Argomenti comuni
# --------------------------------------------------------------------------------------

def _add_source_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("sorgente del segnale")
    g.add_argument("--source", choices=("serial", "simulated", "replay"), default="serial",
                   help="da dove arrivano i dati (default: serial = sensore vero)")
    g.add_argument("--serial-port", default=os.environ.get("NEUROCONTROLLER_PORT"),
                   help="porta seriale, es. COM3 o /dev/ttyACM0 (oppure variabile NEUROCONTROLLER_PORT)")
    g.add_argument("--baud", type=int, default=115200)
    g.add_argument("--fs", type=float, default=DEFAULT_FS,
                   help="campioni al secondo del sensore (da verificare con 'check'; default %(default)s)")
    g.add_argument("--column", type=int, default=0, help="colonna del campione nelle righe di testo")
    g.add_argument("--adc-max", type=float, default=1023.0,
                   help="valore massimo dell'ADC: 1023 = 10 bit (default), 4095 = 12 bit...")
    g.add_argument("--replay-file", help="file con un campione per riga (con --source replay)")
    g.add_argument("--persona", choices=sorted(PERSONAS), default="tipica",
                   help="solo con --source simulated: come reagisce la persona simulata")
    g.add_argument("--seed", type=int, default=0, help="solo simulato: seme casuale")
    g.add_argument("--data-dir", help="cartella dei dati (default: <repository>/data)")


def _build_source(args: argparse.Namespace, script: Optional[Sequence[Tuple[str, float]]] = None) -> Source:
    if args.source == "simulated":
        source: Source = SimulatedSource(args.fs, PERSONAS[args.persona], seed=args.seed, script=script)
        source.adc_max = args.adc_max
        return source
    if args.source == "replay":
        if not args.replay_file:
            raise CliError("con --source replay serve --replay-file <file>")
        try:
            source = CsvReplaySource(args.replay_file, fs=args.fs, column=args.column)
        except (OSError, ValueError) as exc:
            raise CliError("impossibile leggere %s: %s" % (args.replay_file, exc)) from None
        source.adc_max = args.adc_max
        return source
    port = args.serial_port
    if not port:
        found = list_serial_ports()
        port = pick_port(found)
        if port is None:
            if found:
                elenco = "; ".join("%s (%s)" % p for p in found)
                raise CliError("piu' porte seriali disponibili: %s. Scegliere con --serial-port." % elenco)
            raise CliError("nessuna porta seriale trovata: collegare l'Arduino (e installare pyserial: "
                           "pip install pyserial), oppure usare --source simulated per provare senza "
                           "sensore. 'python3 -m neurocontroller ports' mostra le porte.")
    try:
        return SerialSource(port, baud=args.baud, fs=args.fs, column=args.column,
                            adc_max=args.adc_max)
    except RuntimeError as exc:
        raise CliError(str(exc)) from None
    except Exception as exc:  # errori della libreria seriale (porta occupata, inesistente...)
        raise CliError("impossibile aprire la porta %s: %s" % (port, exc)) from None


def _parse_script(text: str) -> List[Tuple[str, float]]:
    steps = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise CliError("voce %r non valida: usare stato:secondi (es. relax:10)" % part)
        state, secs = part.split(":", 1)
        try:
            steps.append((state.strip(), float(secs)))
        except ValueError:
            raise CliError("durata non valida in %r" % part) from None
    if not steps:
        raise CliError("copione vuoto")
    return steps


def _data_dir(args: argparse.Namespace) -> Path:
    return Path(args.data_dir) if args.data_dir else default_data_dir()


def _load_profile(ref: str, data_dir: Path) -> Profile:
    path = Path(ref)
    if not path.suffix:
        path = data_dir / "profiles" / ("%s.json" % ref)
    if not path.exists():
        raise CliError("profilo non trovato: %s (usare 'profiles' per l'elenco)" % path)
    try:
        return Profile.load(path)
    except ProfileError as exc:
        raise CliError(str(exc)) from None


def _bar(score: float, width: int = 21) -> str:
    """Barra da -1.5 (rilassato) a +1.5 (concentrato) con il centro segnato."""
    pos = int(round((max(-1.5, min(1.5, score)) + 1.5) / 3.0 * (width - 1)))
    cells = ["."] * width
    cells[width // 2] = "|"
    cells[pos] = "#"
    return "".join(cells)


# --------------------------------------------------------------------------------------
# Comandi
# --------------------------------------------------------------------------------------

def cmd_ports(args: argparse.Namespace, out: Callable[[str], None]) -> int:
    """Elenca le porte seriali, per trovare quella dell'Arduino senza indovinare."""
    ports = list_serial_ports()
    if not ports:
        out("Nessuna porta seriale trovata. Collegare l'Arduino con il cavo USB; se la libreria "
            "manca: pip install pyserial")
        return 1
    out("Porte seriali disponibili:")
    for device, description in ports:
        out("  %-16s %s" % (device, description))
    if len(ports) == 1:
        out("Una sola porta: i comandi 'check' e 'calibrate' la useranno da soli.")
    else:
        out("Piu' porte: indicare quella giusta con --serial-port.")
    return 0


def cmd_check(args: argparse.Namespace, out: Callable[[str], None]) -> int:
    source = _build_source(args)
    ui = ConsoleUI(quiet_prompts=True, print_fn=out)
    out("Sorgente: %s" % source.description)
    try:
        if source.simulated:
            out("*** SEGNALE SIMULATO: non e' EEG vero. ***")
        check_signal(source, ui)
        if source.realtime:
            source.flush()
            t0 = time.monotonic()
            n = int(source.fs * 4)
            source.read(n)
            measured = n / max(time.monotonic() - t0, 1e-6)
            out("Frequenza di campionamento misurata: %.0f campioni/s (dichiarata: %.0f)"
                % (measured, source.fs))
            if abs(measured - source.fs) / source.fs > 0.10:
                out("ATTENZIONE: differisce di oltre il 10%%. Rilanciare con --fs %.0f, altrimenti le "
                    "bande di frequenza risultano sbagliate." % measured)
                return 2
    except (CalibrationError, TimeoutError, ValueError) as exc:
        out("ERRORE: %s" % exc)
        return 1
    finally:
        source.close()
    return 0


def cmd_calibrate(args: argparse.Namespace, out: Callable[[str], None],
                  input_fn: Callable[[str], str] = input) -> int:
    data_dir = _data_dir(args)
    profiles_dir = data_dir / "profiles"
    pid = args.id or next_participant_id(profiles_dir)
    try:
        check_participant_id(pid, args.allow_custom_id)
    except ProfileError as exc:
        raise CliError(str(exc)) from None
    if (profiles_dir / ("%s.json" % pid)).exists() and not args.overwrite:
        raise CliError("il profilo %s esiste gia': usare --overwrite per sostituirlo, oppure un altro "
                       "codice (il prossimo libero e' %s)" % (pid, next_participant_id(profiles_dir)))
    source = _build_source(args)
    protocol = scaled(default_protocol(), args.duration_scale) if args.duration_scale != 1.0 \
        else default_protocol()
    ui = ConsoleUI(auto_start=args.yes, quiet_prompts=not source.realtime, input_fn=input_fn,
                   print_fn=out, sleep_fn=time.sleep if source.realtime else (lambda s: None))
    # registrazione + circa 10 s per blocco tra conto alla rovescia e INVIO
    minutes = (sum(b.duration for b in protocol) + 10 * len(protocol)) / 60.0
    out("Sorgente: %s" % source.description)
    out("Calibrazione di %s  -  %d blocchi, circa %.0f minuti" % (pid, len(protocol), minutes))
    out("Elettrodo: %s. Consiglio: stanza silenziosa, computer a batteria." % args.electrode)
    try:
        profile, blocks = run_calibration(
            source, pid, protocol=protocol, electrode=args.electrode, ui=ui, seed=args.seed,
            keep_raw=args.save_raw, allow_custom_id=args.allow_custom_id)
    except (CalibrationError, ProfileError) as exc:
        out("ERRORE: %s" % exc)
        return 1
    finally:
        source.close()
    paths = save_session(profile, blocks, data_dir, save_raw=args.save_raw)
    out(report_text(profile))
    if not getattr(args, "_demo", False):
        out("")
        out("Profilo salvato:  %s" % paths["profile"])
        out("Tabella blocchi:  %s" % paths["blocks_csv"])
    if not profile.usable:
        out("Questo profilo e' NON AFFIDABILE: 'live' rifiutera' di usarlo senza --force.")
    return 0


def cmd_live(args: argparse.Namespace, out: Callable[[str], None]) -> int:
    data_dir = _data_dir(args)
    profile = _load_profile(args.profile, data_dir)
    if not profile.usable and not args.force:
        raise CliError("il profilo %s e' %s: i risultati non sarebbero significativi. Ripetere la "
                       "calibrazione, oppure --force per provare lo stesso." % (profile.participant_id,
                                                                                profile.level.upper()))
    script = _parse_script(args.script or DEFAULT_SCRIPT) if args.source == "simulated" else None
    source = _build_source(args, script)
    if profile.simulated != source.simulated:
        out("ATTENZIONE: il profilo e' %s ma la sorgente e' %s: i risultati non hanno senso." %
            ("SIMULATO" if profile.simulated else "reale", "SIMULATA" if source.simulated else "reale"))
    link = None
    if args.udp:
        try:
            mapping = parse_mapping(args.map) if args.map else dict(DEFAULT_MAPPING)
            link = GameLink(args.host, args.udp_port, mapping, nul=not args.no_nul, repeat=args.repeat)
        except ValueError as exc:
            raise CliError(str(exc)) from None
        out("Invio al gioco su %s:%d con corrispondenza %s (PROVVISORIA)" %
            (args.host, args.udp_port, ", ".join("%s->%s" % kv for kv in sorted(link.mapping.items()))))
    if source.simulated:
        out("*** SEGNALE SIMULATO: non e' EEG vero. ***")
    out("Profilo %s (%s). Ctrl+C per fermare." % (profile.participant_id, profile.level))
    try:
        classifier = StateClassifier(profile, margin=args.margin, smooth=args.smooth)
        runner = LiveRunner(source, classifier, link, hop_fraction=args.hop,
                            on_update=lambda u: out(_format_update(u)),
                            pace=bool(link) and not source.realtime)
        seconds = args.seconds if args.seconds is not None else (
            sum(s for _, s in script) if script else None)
        runner.run(seconds)
    except (LiveError, ValueError) as exc:
        out("ERRORE: %s" % exc)
        return 1
    finally:
        source.close()
        if link:
            link.close()
    return 0


def _format_update(u: LiveUpdate) -> str:
    cmd = (" -> '%s'" % u.command) if u.command else ""
    return "%6.1fs  %-11s [%s]  E=%+.2f%s" % (u.t, u.result.state, _bar(u.result.score),
                                              u.result.engagement, cmd)


def cmd_demo(args: argparse.Namespace, out: Callable[[str], None]) -> int:
    """Catena completa senza sensore: calibrazione simulata, poi live simulato."""
    out("DEMO con segnale SIMULATO: nessun cervello viene misurato. Mostra solo come funziona il programma.")
    args.source = "simulated"
    with tempfile.TemporaryDirectory(prefix="neurocontroller-demo-") as tmp:
        args.data_dir = tmp
        args.id = "P01"
        args.yes = True
        args.overwrite = True
        args.save_raw = False
        args.allow_custom_id = False
        args.electrode = "fronte (simulato)"
        args._demo = True
        rc = cmd_calibrate(args, out)
        if rc != 0:
            return rc
        out("")
        out("--- ora il riconoscimento in tempo reale ---")
        args.profile = "P01"
        args.force = False
        args.script = DEFAULT_SCRIPT
        args.seconds = None
        args.margin = 0.25
        args.smooth = 3
        args.hop = 0.5
        return cmd_live(args, out)


def cmd_serve(args: argparse.Namespace, out: Callable[[str], None]) -> int:
    from pathlib import Path as _P
    from .server import make_server
    root = _P(__file__).resolve().parent.parent
    static = _P(args.static_dir) if args.static_dir else root / "web" / "app"
    if not (static / "index.html").is_file():
        raise CliError("non trovo la web app in %s (manca index.html)" % static)
    db = _data_dir(args) / "web" / "giochi.sqlite3"
    try:
        server, _ = make_server(db, static, host=args.host, port=args.port)
    except OSError as exc:
        raise CliError("non riesco ad ascoltare su %s:%d (%s). Prova un'altra porta con --port."
                       % (args.host, args.port, exc))
    shown = "localhost" if args.host in ("127.0.0.1", "0.0.0.0", "::1") else args.host
    out("Web app pronta: apri in Chrome o Edge  http://%s:%d/" % (shown, args.port))
    out("Database: %s   (resta su questo computer; non va versionato)" % db)
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        out("ATTENZIONE: in ascolto su %s: i dati sono raggiungibili dalla rete." % args.host)
    out("Per fermare: Ctrl+C")
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


def cmd_profiles(args: argparse.Namespace, out: Callable[[str], None]) -> int:
    pdir = _data_dir(args) / "profiles"
    files = sorted(pdir.glob("P*.json")) if pdir.is_dir() else []
    if not files:
        out("Nessun profilo in %s" % pdir)
        return 0
    out("%-6s %-10s %-15s %6s %9s  %s" % ("id", "data", "qualita'", "d'", "acc.blocchi", "note"))
    for f in files:
        try:
            p = Profile.load(f)
        except ProfileError as exc:
            out("%-6s PROFILO ILLEGGIBILE: %s" % (f.stem, exc))
            continue
        acc = p.quality.get("cross_block_accuracy")
        out("%-6s %-10s %-15s %6.2f %11s  %s" % (
            p.participant_id, p.created[:10], p.level, float(p.quality["dprime"]),  # type: ignore[arg-type]
            ("%.0f%%" % (100 * float(acc))) if acc is not None else "n.d.",  # type: ignore[arg-type]
            "SIMULATO" if p.simulated else ""))
    return 0


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m neurocontroller",
        description="Calibrazione per persona e stato mentale da un sensore EEG.")
    parser.add_argument("--version", action="version", version="neurocontroller " + __version__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ports", help="elenca le porte seriali (per trovare quella dell'Arduino)")

    p = sub.add_parser("check", help="controlla il segnale del sensore")
    _add_source_args(p)

    p = sub.add_parser("calibrate", help="calibrazione guidata di una persona")
    _add_source_args(p)
    p.add_argument("--id", help="codice anonimo (P01, P02...); se omesso, il prossimo libero")
    p.add_argument("--allow-custom-id", action="store_true", help="consente codici diversi da Pnn")
    p.add_argument("--electrode", default="fronte", help="dove e' posto l'elettrodo attivo (testo libero)")
    p.add_argument("--yes", action="store_true", help="non attendere INVIO tra i blocchi")
    p.add_argument("--duration-scale", type=float, default=1.0,
                   help="accorcia/allunga i blocchi (solo per prove: usare 1 con persone vere)")
    p.add_argument("--save-raw", action="store_true",
                   help="salva anche i campioni grezzi in data/raw (dati personali: vedi docs/05)")
    p.add_argument("--overwrite", action="store_true", help="sostituisce un profilo esistente")

    p = sub.add_parser("live", help="riconoscimento dello stato in tempo reale")
    _add_source_args(p)
    p.add_argument("--profile", required=True, help="codice del profilo (P01) o percorso del file")
    p.add_argument("--seconds", type=float, help="durata (default: finche' non si preme Ctrl+C)")
    p.add_argument("--force", action="store_true", help="usa anche un profilo non affidabile")
    p.add_argument("--margin", type=float, default=0.25, help="fascia 'neutro' attorno alla soglia")
    p.add_argument("--smooth", type=int, default=3, help="finestre su cui mediare")
    p.add_argument("--hop", type=float, default=0.25, help="avanzamento tra aggiornamenti (frazione di finestra)")
    p.add_argument("--script", help="solo simulato: copione tipo 'relax:10,focus:10,jaw:3'")
    g = p.add_argument_group("collegamento al gioco")
    g.add_argument("--udp", action="store_true", help="invia i comandi al gioco GameMaker")
    g.add_argument("--host", default=DEFAULT_HOST)
    g.add_argument("--udp-port", type=int, default=DEFAULT_PORT)
    g.add_argument("--map", help="corrispondenza stato=comando, es. concentrato=b,rilassato=a")
    g.add_argument("--repeat", type=int, default=1, help="pacchetti per ogni aggiornamento")
    g.add_argument("--no-nul", action="store_true", help="non aggiungere il terminatore NUL")

    p = sub.add_parser("demo", help="prova completa senza sensore (segnale simulato)")
    _add_source_args(p)
    p.add_argument("--duration-scale", type=float, default=0.5)
    p.add_argument("--udp", action="store_true", help="invia i comandi al gioco GameMaker")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--udp-port", type=int, default=DEFAULT_PORT)
    p.add_argument("--map", help="corrispondenza stato=comando")
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--no-nul", action="store_true")

    p = sub.add_parser("profiles", help="elenca i profili salvati")
    p.add_argument("--data-dir")

    p = sub.add_parser("serve", help="avvia la web app (talpa) con il database locale")
    p.add_argument("--data-dir")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1",
                   help="indirizzo di ascolto (default: solo questo computer)")
    p.add_argument("--static-dir", help="cartella della web app (default: web/app)")
    return parser


def main(argv: Optional[Sequence[str]] = None, out: Callable[[str], None] = print,
         input_fn: Callable[[str], str] = input) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "ports":
            return cmd_ports(args, out)
        if args.command == "check":
            return cmd_check(args, out)
        if args.command == "calibrate":
            return cmd_calibrate(args, out, input_fn)
        if args.command == "live":
            return cmd_live(args, out)
        if args.command == "demo":
            return cmd_demo(args, out)
        if args.command == "serve":
            return cmd_serve(args, out)
        return cmd_profiles(args, out)
    except CliError as exc:
        out("ERRORE: %s" % exc)
        return 2
    except KeyboardInterrupt:
        out("\nInterrotto.")
        return 130
