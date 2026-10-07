"""Igiene del repository: i dati fisiologici non devono poter finire in Git per errore.

Si controlla con `git check-ignore`, cioe' con le regole che Git applica davvero (non
solo leggendo il testo del .gitignore). Se git non e' disponibile i test vengono saltati.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _ignored(rel: str) -> bool:
    res = subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return res.returncode == 0


@unittest.skipUnless(shutil.which("git") and (ROOT / ".git").exists(), "serve un clone git")
class DataIgnoredTests(unittest.TestCase):
    def test_personal_data_dirs_are_ignored(self):
        for rel in ("data/profiles/P01.json", "data/sessions/P01_20260101-000000_blocchi.csv",
                    "data/raw/P01_20260101-000000_focus_1.csv"):
            with self.subTest(path=rel):
                self.assertTrue(_ignored(rel), "%s dovrebbe essere ignorato da Git" % rel)

    def test_documentation_in_data_is_not_ignored(self):
        for rel in ("data/README.md", "data/eeg_test_template.csv"):
            with self.subTest(path=rel):
                self.assertFalse(_ignored(rel), "%s deve restare versionato" % rel)


if __name__ == "__main__":
    unittest.main()
