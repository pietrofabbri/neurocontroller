"""Test del protocollo di calibrazione: struttura, scalatura, problemi generati."""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neurocontroller import protocol as P  # noqa: E402


class DefaultProtocolTests(unittest.TestCase):
    def setUp(self):
        self.proto = P.default_protocol()

    def test_keys_are_unique(self):
        keys = [b.key for b in self.proto]
        self.assertEqual(len(keys), len(set(keys)))

    def test_each_state_is_recorded_in_two_separate_blocks(self):
        # serve alla validazione tra blocchi: tarare su un blocco, verificare sull'altro
        relax = [b for b in self.proto if b.role == P.ROLE_RELAX]
        focus = [b for b in self.proto if b.role == P.ROLE_FOCUS]
        self.assertEqual(len(relax), 2)
        self.assertEqual(len(focus), 2)

    def test_relax_and_focus_suffixes_pair_up(self):
        # profile.py raggruppa i blocchi dal suffisso _1/_2 della chiave
        self.assertEqual({b.key.rsplit("_", 1)[-1] for b in self.proto if b.role == P.ROLE_RELAX},
                         {b.key.rsplit("_", 1)[-1] for b in self.proto if b.role == P.ROLE_FOCUS})

    def test_there_is_one_eyes_closed_check_and_one_artifact_block(self):
        self.assertEqual(sum(b.role == P.ROLE_CHECK for b in self.proto), 1)
        self.assertEqual(sum(b.role == P.ROLE_ARTIFACT for b in self.proto), 1)

    def test_total_duration_is_about_five_minutes(self):
        total = P.total_duration(self.proto)
        self.assertGreater(total, 240)
        self.assertLess(total, 360)

    def test_relax_blocks_are_not_eyes_closed(self):
        # il rilassamento deve essere a occhi APERTI, altrimenti si misurerebbero le palpebre
        for b in self.proto:
            if b.role == P.ROLE_RELAX:
                self.assertIn("occhi_aperti", b.stimulus)
                self.assertNotIn("chiudi", b.instruction.lower())

    def test_tasks_are_silent(self):
        for b in self.proto:
            if b.role in (P.ROLE_RELAX, P.ROLE_FOCUS):
                self.assertIn("non parlare", b.instruction.lower())

    def test_artifact_prompts_are_within_the_block(self):
        art = next(b for b in self.proto if b.role == P.ROLE_ARTIFACT)
        self.assertTrue(art.prompts)
        self.assertTrue(all(0 <= p.at < art.duration for p in art.prompts))
        self.assertEqual([p.at for p in art.prompts], sorted(p.at for p in art.prompts))

    def test_trim_is_shorter_than_block(self):
        for b in self.proto:
            self.assertLess(b.trim, b.duration)


class ScaledTests(unittest.TestCase):
    def test_scale_changes_durations(self):
        base = P.default_protocol()
        half = P.scaled(base, 0.5)
        self.assertEqual(len(half), len(base))
        self.assertLess(P.total_duration(half), P.total_duration(base))

    def test_minimum_block_length(self):
        tiny = P.scaled(P.default_protocol(), 0.001)
        self.assertTrue(all(b.duration >= 8.0 for b in tiny))

    def test_prompts_scale_with_block(self):
        base = next(b for b in P.default_protocol() if b.role == P.ROLE_ARTIFACT)
        half = next(b for b in P.scaled(P.default_protocol(), 0.5) if b.role == P.ROLE_ARTIFACT)
        k = half.duration / base.duration
        for p0, p1 in zip(base.prompts, half.prompts):
            self.assertAlmostEqual(p1.at, p0.at * k)
            self.assertLess(p1.at, half.duration)

    def test_trim_never_exceeds_a_quarter_of_the_block(self):
        for b in P.scaled(P.default_protocol(), 0.001):
            self.assertLessEqual(b.trim, b.duration / 4.0 + 1e-9)

    def test_invalid_factor(self):
        for bad in (0, -1):
            with self.assertRaises(ValueError):
                P.scaled(P.default_protocol(), bad)


class ProblemTests(unittest.TestCase):
    def test_multiplications_are_well_formed_and_reproducible(self):
        a = [P.make_problem("moltiplicazioni", random.Random(7)) for _ in range(3)]
        b = [P.make_problem("moltiplicazioni", random.Random(7)) for _ in range(3)]
        self.assertEqual(a, b)
        for text in a:
            x, y = (int(v) for v in text.split(" x "))
            self.assertTrue(12 <= x <= 49 and 3 <= y <= 9)

    def test_unknown_kind(self):
        self.assertIsNone(P.make_problem("sconosciuto", random.Random(0)))


if __name__ == "__main__":
    unittest.main()
