#!/usr/bin/env python3
"""Controlla che in Git non siano stati tracciati dati personali o file che non devono starci.

Perche' serve anche con il .gitignore: `git add -f` lo aggira, e un commit con un profilo
di calibrazione o un PDF con i nomi degli studenti resta nella storia del repository.
Questo controllo gira in locale (`python3 tools/check_repo.py`) e nella CI a ogni push.

Controlla solo i file TRACCIATI (`git ls-files`), non quelli presenti sul disco.
Esce con 0 se e' tutto a posto, con 1 se trova qualcosa, con 2 se non puo' controllare.

Solo libreria standard (Python >= 3.8).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

ROOT = Path(__file__).resolve().parent.parent

# In data/ si possono versionare solo la descrizione e l'intestazione del formato.
DATA_ALLOWED = {"data/README.md", "data/eeg_test_template.csv"}

# Estensioni che non devono stare nel repository: i PDF originali contengono nomi di
# studenti (vedi docs/sources/README.md), gli archivi possono contenere qualsiasi cosa.
FORBIDDEN_SUFFIXES = (".pdf", ".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".bundle")

# Codici anonimi dei partecipanti usati come nome di file: P01.json, P01_..._blocchi.csv
PARTICIPANT_FILE = re.compile(r"(^|/)P\d{2,3}[._]")


def tracked_files(root: Path) -> List[str]:
    res = subprocess.run(["git", "ls-files", "-z"], cwd=root, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.decode("utf-8", "replace").strip() or "git ls-files fallito")
    return [p for p in res.stdout.decode("utf-8").split("\0") if p]


def problems(paths: Iterable[str]) -> List[Tuple[str, str]]:
    """Elenco di (file, motivo). Funzione pura: e' quella che si testa."""
    found: List[Tuple[str, str]] = []
    for path in paths:
        low = path.lower()
        if path.startswith("data/") and path not in DATA_ALLOWED:
            found.append((path, "in data/ possono stare solo %s" % ", ".join(sorted(DATA_ALLOWED))))
        elif low.endswith(FORBIDDEN_SUFFIXES):
            found.append((path, "tipo di file non ammesso (PDF/archivi): possono contenere dati personali"))
        elif PARTICIPANT_FILE.search(path) and not path.startswith(("tests/", "docs/")):
            found.append((path, "sembra un file di un partecipante (codice P01...)"))
    return found


def main(argv: List[str] = None, out=print) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", default=str(ROOT), help="radice del repository (default: questo)")
    args = parser.parse_args(argv)
    try:
        files = tracked_files(Path(args.root))
    except (RuntimeError, OSError) as exc:
        out("ERRORE: impossibile leggere i file tracciati da Git: %s" % exc)
        return 2
    found = problems(files)
    if not found:
        out("OK: nessun dato personale o file vietato tra i %d file tracciati." % len(files))
        return 0
    out("TROVATI %d FILE CHE NON DEVONO ESSERE IN GIT:" % len(found))
    for path, reason in found:
        out("  %s  -  %s" % (path, reason))
    out("")
    out("Se non e' ancora stato pubblicato:  git rm --cached <file>  e nuovo commit.")
    out("Se e' gia' stato pubblicato i dati restano nella STORIA di Git: serve riscrivere la")
    out("storia (non basta cancellare il file) e, se erano dati veri, avvisare chi di dovere.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
