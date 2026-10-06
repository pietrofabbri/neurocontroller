#!/usr/bin/env python3
"""
udp_sim.py - Simulatore del "bridge" EEG per provare il gioco SENZA sensore.

Invia al gioco GameMaker (obj_player, evento Async Networking) gli stessi
comandi che invierebbe il bridge reale: caratteri singoli via UDP.

Contratto attuale (vedi docs/01-architettura.md, sezione "Protocollo"):
  - trasporto : UDP, default 127.0.0.1:6510
  - payload   : una stringa di UN carattere
                "a" -> il giocatore va a sinistra (x -= spd)
                "b" -> il giocatore va a destra   (x += spd)
                "g" -> il giocatore va su         (y -= spd)
  - terminatore NUL (\\x00): attivo di default. In GameMaker il codice del gioco
    usa buffer_read(buff, buffer_string), che legge una stringa terminata da
    NUL. Con --no-nul si invia il solo carattere (utile per confrontare il
    comportamento del bridge reale, che non e' nel repository).

NOTA: questo script e' stato scritto per il repository; NON e' il bridge.py
degli studenti (quello non e' ancora stato recuperato, vedi bridge/README.md).

Uso:
  python3 tools/udp_sim.py send b --count 20 --interval 0.05
  python3 tools/udp_sim.py demo --seconds 10
  python3 tools/udp_sim.py --help

Solo libreria standard (Python >= 3.8).
"""
from __future__ import annotations

import argparse
import socket
import sys
import time
from typing import Iterable

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 6510
VALID_COMMANDS = ("a", "b", "g")

# Sequenza usata dalla modalita' demo: un giro di prova di tutti i comandi.
DEMO_SEQUENCE = ("b",) * 10 + ("g",) * 10 + ("a",) * 10 + ("g",) * 5


def encode(command: str, nul: bool = True) -> bytes:
    """Trasforma un comando ('a', 'b', 'g') nel payload da spedire."""
    if command not in VALID_COMMANDS:
        raise ValueError(
            f"comando non valido {command!r}: ammessi {', '.join(VALID_COMMANDS)}"
        )
    return command.encode("ascii") + (b"\x00" if nul else b"")


def send_commands(
    commands: Iterable[str],
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    interval: float = 0.05,
    nul: bool = True,
) -> int:
    """Invia i comandi uno alla volta, attendendo `interval` secondi tra l'uno e l'altro.

    Restituisce il numero di pacchetti inviati.
    """
    sent = 0
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for command in commands:
            sock.sendto(encode(command, nul=nul), (host, port))
            sent += 1
            if interval > 0:
                time.sleep(interval)
    return sent


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulatore del bridge EEG -> GameMaker (UDP)."
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="default: %(default)s")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="default: %(default)s")
    parser.add_argument(
        "--no-nul",
        action="store_true",
        help="non aggiungere il terminatore NUL al payload",
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    p_send = sub.add_parser("send", help="invia lo stesso comando piu' volte")
    p_send.add_argument("command", choices=VALID_COMMANDS)
    p_send.add_argument("--count", type=int, default=1)
    p_send.add_argument("--interval", type=float, default=0.05, help="secondi tra i pacchetti")

    p_demo = sub.add_parser("demo", help="ripete una sequenza di prova di tutti i comandi")
    p_demo.add_argument("--seconds", type=float, default=10.0, help="durata totale")
    p_demo.add_argument("--interval", type=float, default=0.05, help="secondi tra i pacchetti")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    nul = not args.no_nul

    if args.mode == "send":
        if args.count < 1:
            print("--count deve essere >= 1", file=sys.stderr)
            return 2
        sent = send_commands(
            [args.command] * args.count, args.host, args.port, args.interval, nul
        )
        print(f"inviati {sent} pacchetti {args.command!r} a {args.host}:{args.port}")
        return 0

    # demo
    deadline = time.monotonic() + args.seconds
    sent = 0
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        while time.monotonic() < deadline:
            for command in DEMO_SEQUENCE:
                if time.monotonic() >= deadline:
                    break
                sock.sendto(encode(command, nul=nul), (args.host, args.port))
                sent += 1
                time.sleep(args.interval)
    print(f"demo terminata: {sent} pacchetti inviati a {args.host}:{args.port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
