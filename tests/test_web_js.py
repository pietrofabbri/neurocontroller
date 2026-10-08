"""Prove del lato JavaScript della versione web: parita' con il Python (V-18) e nucleo di gioco.

Richiedono Node (>= 18); se manca, le prove vengono saltate. Nessuna dipendenza da installare."""
import importlib.util
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "web" / "app"
NODE = shutil.which("node")


def _carica_generatore():
    spec = importlib.util.spec_from_file_location("genera_vettori_web", ROOT / "tools" / "genera_vettori_web.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class VettoriTests(unittest.TestCase):
    def test_vettori_aggiornati(self):
        """Il file dei vettori corrisponde a cio' che il Python calcola oggi (niente deriva silenziosa)."""
        mod = _carica_generatore()
        salvati = json.loads((APP / "test" / "vettori.json").read_text(encoding="utf-8"))
        ora = json.loads(json.dumps({"finestre": mod.finestre(), "classificatore": mod.classificatore()}))
        self.assertEqual(salvati, ora, "rigenerare con: python3 tools/genera_vettori_web.py")


@unittest.skipUnless(NODE, "Node non installato")
class NodeTests(unittest.TestCase):
    def test_prove_javascript(self):
        files = sorted(str(p) for p in (APP / "test").glob("*.test.*js"))
        res = subprocess.run([NODE, "--test"] + files, capture_output=True, text=True, timeout=300)
        self.assertEqual(res.returncode, 0, res.stdout[-3000:] + res.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
