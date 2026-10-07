"""Test del controllo anti-dati-personali (tools/check_repo.py)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import check_repo  # noqa: E402


class ProblemsTests(unittest.TestCase):
    def test_clean_repository_has_no_problems(self):
        paths = ["README.md", "docs/08-calibrazione.md", "neurocontroller/profile.py",
                 "tests/test_profile.py", "data/README.md", "data/eeg_test_template.csv",
                 "game/BLeppo2/BLeppo2.yyp", "third_party/Formula64x64/license.txt"]
        self.assertEqual(check_repo.problems(paths), [])

    def test_personal_data_in_data_is_flagged(self):
        for path in ("data/profiles/P01.json", "data/sessions/P01_20261007-101010_blocchi.csv",
                     "data/raw/P01_x_focus_1.csv", "data/notes.txt"):
            with self.subTest(path=path):
                self.assertEqual([p for p, _ in check_repo.problems([path])], [path])

    def test_pdf_and_archives_are_flagged_anywhere(self):
        for path in ("docs/sources/scheda.PDF", "Bleppo2_complete.zip", "x/y/backup.tar.gz",
                     "neurocontroller.bundle"):
            with self.subTest(path=path):
                self.assertEqual(len(check_repo.problems([path])), 1)

    def test_participant_named_file_outside_data_is_flagged(self):
        self.assertEqual(len(check_repo.problems(["export/P03_profilo.json"])), 1)

    def test_tests_and_docs_may_mention_participant_codes_in_filenames(self):
        self.assertEqual(check_repo.problems(["docs/P01_esempio.md", "tests/P01_fixture.csv"]), [])

    def test_similar_names_are_not_flagged(self):
        self.assertEqual(check_repo.problems(["docs/PROFILO.md", "tools/Pipeline.py", "Pxx.txt"]), [])


class EndToEndTests(unittest.TestCase):
    """Su un repository git temporaneo vero, compreso l'aggiramento con `git add -f`."""

    def git(self, root, *args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.invalid", *args],
                       cwd=root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def make_repo(self, tmp):
        root = Path(tmp)
        self.git(root, "init", "-q")
        (root / ".gitignore").write_text("data/profiles/\n", encoding="utf-8")
        (root / "README.md").write_text("x\n", encoding="utf-8")
        (root / "data" / "profiles").mkdir(parents=True)
        (root / "data" / "profiles" / "P01.json").write_text("{}\n", encoding="utf-8")
        return root

    def run_check(self, root):
        lines = []
        rc = check_repo.main(["--root", str(root)], out=lines.append)
        return rc, "\n".join(lines)

    def test_ignored_profile_is_not_tracked_so_check_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repo(tmp)
            self.git(root, "add", "-A")
            self.git(root, "commit", "-q", "-m", "x")
            rc, text = self.run_check(root)
        self.assertEqual(rc, 0, text)
        self.assertIn("OK", text)

    def test_forced_add_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repo(tmp)
            self.git(root, "add", "-A")
            self.git(root, "add", "-f", "data/profiles/P01.json")
            self.git(root, "commit", "-q", "-m", "x")
            rc, text = self.run_check(root)
        self.assertEqual(rc, 1)
        self.assertIn("data/profiles/P01.json", text)
        self.assertIn("STORIA", text)

    def test_not_a_git_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, text = self.run_check(Path(tmp))
        self.assertEqual(rc, 2)
        self.assertIn("ERRORE", text)

    def test_this_repository_is_clean(self):
        if not (ROOT / ".git").exists():
            self.skipTest("serve un clone git")
        rc, text = self.run_check(ROOT)
        self.assertEqual(rc, 0, text)


if __name__ == "__main__":
    unittest.main()
