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
        ora = json.loads(json.dumps({"finestre": mod.finestre(), "classificatore": mod.classificatore(), **mod.righe_e_qualita()}))
        # Non si confronta bit per bit: sin() e sum() differiscono di pochissimo tra sistemi e versioni di Python
        # (per esempio sum() e' piu' preciso dalla 3.12). Una deriva vera dell'algoritmo e' molto piu' grande.
        self._vicini(salvati, ora, "vettori")

    def _vicini(self, a, b, path):
        if isinstance(a, dict):
            self.assertEqual(sorted(a), sorted(b), path)
            for k in a:
                self._vicini(a[k], b[k], path + "." + k)
        elif isinstance(a, list):
            self.assertEqual(len(a), len(b), path)
            for i, (x, y) in enumerate(zip(a, b)):
                self._vicini(x, y, "%s[%d]" % (path, i))
        elif isinstance(a, (int, float)) and not isinstance(a, bool):
            self.assertAlmostEqual(a, b, delta=1e-4 + 1e-4 * abs(a), msg="%s: rigenerare con tools/genera_vettori_web.py" % path)
        else:
            self.assertEqual(a, b, path)


@unittest.skipUnless(NODE, "Node non installato")
class NodeTests(unittest.TestCase):
    def test_prove_javascript(self):
        files = sorted(str(p) for p in (APP / "test").glob("*.test.*js"))
        res = subprocess.run([NODE, "--test"] + files, capture_output=True, text=True, timeout=300)
        self.assertEqual(res.returncode, 0, res.stdout[-3000:] + res.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
