"""Test del profilo, della qualita' della calibrazione e del classificatore di stato."""
import functools
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neurocontroller import dsp  # noqa: E402
from neurocontroller.calibration import run_calibration  # noqa: E402
from neurocontroller.profile import (ALL_STATES, STATE_ARTIFACT, STATE_FOCUSED,  # noqa: E402
                                     STATE_NEUTRAL, STATE_RELAXED, Profile, ProfileError,
                                     StateClassifier, check_participant_id, next_participant_id)
from neurocontroller.sources import PERSONAS, SimulatedSource  # noqa: E402

FS = 250.0


@functools.lru_cache(maxsize=None)
def calibrate(persona: str, seed: int = 0):
    """Calibrazione simulata (in cache: i profili non vengono modificati dai test)."""
    source = SimulatedSource(FS, PERSONAS[persona], seed=seed)
    profile, _ = run_calibration(source, "P01", seed=seed)
    return profile


class CalibrationQualityTests(unittest.TestCase):
    """La calibrazione deve saper dire 'per questa persona non funziona'."""

    SEEDS = range(4)

    def test_typical_persona_is_usable_on_every_seed(self):
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                p = calibrate("tipica", seed)
                self.assertEqual(p.level, "usabile")
                self.assertTrue(p.usable)
                self.assertGreater(p.quality["dprime"], 1.5)

    def test_weak_persona_is_never_declared_usable(self):
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                self.assertNotEqual(calibrate("debole", seed).level, "usabile")

    def test_unresponsive_persona_is_always_unreliable(self):
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                p = calibrate("nulla", seed)
                self.assertEqual(p.level, "non affidabile")
                self.assertFalse(p.usable)
                self.assertTrue(p.quality["messages"])

    def test_profile_is_marked_simulated(self):
        self.assertTrue(calibrate("tipica").simulated)

    def test_cross_block_accuracy_is_reported(self):
        acc = calibrate("tipica").quality["cross_block_accuracy"]
        self.assertIsNotNone(acc)
        self.assertGreaterEqual(acc, 0.0)
        self.assertLessEqual(acc, 1.0)

    def test_artifact_thresholds_do_not_flag_clean_blocks_much(self):
        self.assertLess(calibrate("tipica").artifact["false_alarm_rate"], 0.10)

    def test_voluntary_movements_are_detected(self):
        self.assertGreater(calibrate("tipica").artifact["hit_rate"], 0.4)


class ProfileFileTests(unittest.TestCase):
    def test_save_load_round_trip(self):
        p = calibrate("tipica")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "P01.json"
            p.save(path)
            q = Profile.load(path)
        self.assertEqual(q.participant_id, p.participant_id)
        self.assertEqual(q.level, p.level)
        self.assertAlmostEqual(q.state["threshold"], p.state["threshold"])
        self.assertEqual(q.window, p.window)
        self.assertEqual(set(q.bands), set(dsp.BANDS))

    def test_profile_contains_no_raw_samples(self):
        # il profilo e' un riassunto: niente campioni grezzi, quindi niente dati ricostruibili
        text = json.dumps(calibrate("tipica").to_dict())
        self.assertLess(len(text), 20000)

    def test_unsupported_version_is_rejected(self):
        d = calibrate("tipica").to_dict()
        d["schema_version"] = 999
        with self.assertRaises(ProfileError):
            Profile.from_dict(d)

    def test_missing_field_is_reported(self):
        d = calibrate("tipica").to_dict()
        del d["state"]
        with self.assertRaises(ProfileError):
            Profile.from_dict(d)

    def test_corrupt_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "P01.json"
            path.write_text("{non e' json", encoding="utf-8")
            with self.assertRaises(ProfileError):
                Profile.load(path)


class ParticipantIdTests(unittest.TestCase):
    def test_anonymous_codes_are_accepted(self):
        for pid in ("P01", "P12", "P123"):
            self.assertEqual(check_participant_id(pid), pid)

    def test_names_are_rejected(self):
        for pid in ("Mario", "mario.rossi", "P1", "p01", "", "../P01", "P01.json"):
            with self.subTest(pid=pid):
                with self.assertRaises(ProfileError):
                    check_participant_id(pid)

    def test_custom_codes_need_explicit_permission(self):
        with self.assertRaises(ProfileError):
            check_participant_id("test-1")
        self.assertEqual(check_participant_id("test-1", allow_custom=True), "test-1")
        with self.assertRaises(ProfileError):
            check_participant_id("../x", allow_custom=True)

    def test_next_id_skips_used_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            self.assertEqual(next_participant_id(d / "non-esiste"), "P01")
            (d / "P01.json").write_text("{}")
            (d / "P03.json").write_text("{}")
            self.assertEqual(next_participant_id(d), "P02")


def make_features(alpha: float, beta: float, rms: float, hf_ratio: float) -> dsp.Features:
    """Finestra sintetica con indice E = ln(beta/(alpha+theta)) controllabile (theta = 1)."""
    absolute = {"delta": 1.0, "theta": 1.0, "alpha": alpha, "beta": beta, "gamma": 0.1}
    total = sum(absolute.values())
    return dsp.Features(rel={k: v / total for k, v in absolute.items()}, absolute=absolute,
                        total=total, rms=rms, hf_ratio=hf_ratio,
                        engagement=dsp.math.log(beta / (alpha + 1.0)))


class StateClassifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = calibrate("tipica")

    def classifier(self, **kw):
        return StateClassifier(self.profile, **kw)

    def window_with_engagement(self, target: float, rms_factor: float = 1.0) -> dsp.Features:
        # alpha=1, theta=1 -> denominatore 2; beta = 2*exp(target).
        # Ampiezza e rapporto ad alta frequenza "tipici" di questa persona (le soglie
        # anti-disturbo sono apprese per persona, quindi vanno rispettate dalla finestra).
        art = self.profile.artifact
        return make_features(1.0, 2.0 * dsp.math.exp(target), art["rms_median"] * rms_factor,
                             art["hf_median"])

    def test_relaxed_and_focused_windows(self):
        st = self.profile.state
        c = self.classifier(smooth=1)
        self.assertEqual(c.update(self.window_with_engagement(st["relax_mean"])).state, STATE_RELAXED)
        self.assertEqual(c.update(self.window_with_engagement(st["focus_mean"])).state, STATE_FOCUSED)

    def test_threshold_is_neutral(self):
        c = self.classifier(smooth=1)
        r = c.update(self.window_with_engagement(self.profile.state["threshold"]))
        self.assertEqual(r.state, STATE_NEUTRAL)
        self.assertAlmostEqual(r.score, 0.0, places=6)

    def test_artifact_window_is_flagged_and_not_smoothed(self):
        c = self.classifier(smooth=3)
        r = c.update(self.window_with_engagement(0.0, rms_factor=1e3))
        self.assertEqual(r.state, STATE_ARTIFACT)
        self.assertTrue(r.artifact)
        self.assertEqual(c._history, [])

    def test_smoothing_delays_the_switch(self):
        st = self.profile.state
        c = self.classifier(smooth=3)
        for _ in range(3):
            c.update(self.window_with_engagement(st["relax_mean"]))
        first_focus = c.update(self.window_with_engagement(st["focus_mean"]))
        self.assertNotEqual(first_focus.state, STATE_FOCUSED)  # la media e' ancora vicina al riposo

    def test_reset_clears_history(self):
        c = self.classifier()
        c.update(self.window_with_engagement(self.profile.state["relax_mean"]))
        c.reset()
        self.assertEqual(c._history, [])

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):
            self.classifier(smooth=0)
        for bad in (-0.1, 1.0, 2.0):
            with self.assertRaises(ValueError):
                self.classifier(margin=bad)

    def test_all_states_are_known(self):
        for s in (STATE_RELAXED, STATE_FOCUSED, STATE_NEUTRAL, STATE_ARTIFACT):
            self.assertIn(s, ALL_STATES)


if __name__ == "__main__":
    unittest.main()
