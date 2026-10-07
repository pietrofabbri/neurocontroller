"""Collegamento al gioco GameMaker via UDP.

Contratto dal lato del gioco (verificato leggendo `obj_player`, vedi
docs/01-architettura.md): pacchetti UDP alla porta 6510, ciascuno con UNA lettera
terminata da NUL: "a" sinistra, "b" destra, "g" su.

LA CORRISPONDENZA stato mentale -> comando e' PROVVISORIA (decisione D1 della
roadmap): per ora "concentrato" porta a destra e "rilassato" a sinistra, cosi'
la catena completa e' provabile. Il gioco vero (strada con due superfici e
punteggio, tappa M3) dovra' sostituirla.
"""
from __future__ import annotations

import socket
from typing import Dict, Optional

from .profile import ALL_STATES

COMMANDS = ("a", "b", "g")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 6510
DEFAULT_MAPPING: Dict[str, str] = {"concentrato": "b", "rilassato": "a"}


def encode(command: str, nul: bool = True) -> bytes:
    """Payload di un pacchetto. Deve restare identico a tools/udp_sim.py (c'e' un test)."""
    if command not in COMMANDS:
        raise ValueError("comando non valido %r: ammessi %s" % (command, ", ".join(COMMANDS)))
    return command.encode("ascii") + (b"\x00" if nul else b"")


def parse_mapping(text: str) -> Dict[str, str]:
    """Legge "concentrato=b,rilassato=a" (gli stati non citati non inviano nulla)."""
    mapping: Dict[str, str] = {}
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError("voce %r non valida: usare stato=comando" % part)
        state, command = (x.strip() for x in part.split("=", 1))
        if state not in ALL_STATES:
            raise ValueError("stato %r sconosciuto: ammessi %s" % (state, ", ".join(ALL_STATES)))
        if command not in COMMANDS:
            raise ValueError("comando %r non valido: ammessi %s" % (command, ", ".join(COMMANDS)))
        mapping[state] = command
    return mapping


class GameLink:
    """Invia al gioco il comando associato allo stato mentale corrente."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 mapping: Optional[Dict[str, str]] = None, nul: bool = True, repeat: int = 1,
                 sock: Optional[socket.socket] = None):
        if repeat < 1:
            raise ValueError("repeat deve essere >= 1")
        self.addr = (host, port)
        self.mapping = dict(DEFAULT_MAPPING if mapping is None else mapping)
        self.nul = nul
        self.repeat = repeat
        self._sock = sock or socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sent = 0

    def send_state(self, state: str) -> Optional[str]:
        """Restituisce il comando inviato, o None se lo stato non ha un comando."""
        command = self.mapping.get(state)
        if command is None:
            return None
        payload = encode(command, self.nul)
        for _ in range(self.repeat):
            self._sock.sendto(payload, self.addr)
            self.sent += 1
        return command

    def close(self) -> None:
        self._sock.close()
