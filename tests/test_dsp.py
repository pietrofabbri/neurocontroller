"""Test di FFT, spettro, bande e controllo qualita' del segnale."""
import cmath
import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neurocontroller import dsp  # noqa: E402

FS = 250.0
N = dsp.window_size(FS)


def sine(freq, amp=100.0, n=N, fs=FS):
    return [amp * math.sin(2 * math.pi * freq * i / fs) for i in range(n)]


class FftTests(unittest.TestCase):
    def test_matches_naive_dft(self):
        r = random.Random(1)
        x = [r.gauss(0, 1) for _ in range(64)]
        naive = [sum(x[n] * cmath.exp(-2j * math.pi * k * n / 64) for n in range(64)) for k in range(64)]
        fast = dsp.fft(x)
        self.assertLess(max(abs(a - b) for a, b in zip(naive, fast)), 1e-9)

    def test_parseval(self):
        r = random.Random(2)
        x = [r.gauss(0, 1) for _ in range(256)]
        spec = dsp.fft(x)
        self.assertAlmostEqual(sum(v * v for v in x), sum(abs(v) ** 2 for v in spec) / 256, places=6)

    def test_rejects_non_power_of_two(self):
        with self.assertRaises(ValueError):
            dsp.fft([0.0] * 100)
        with self.assertRaises(ValueError):
            dsp.fft([])

    def test_window_size(self):
        self.assertEqual(dsp.window_size(250), 512)
        self.assertEqual(dsp.window_size(256), 512)
        self.assertEqual(dsp.window_size(500), 1024)
        self.assertEqual(dsp.window_size(100), 256)


class SpectrumTests(unittest.TestCase):
    def test_alpha_sine_lands_in_alpha(self):
        feats, freqs, psd = dsp.analyze_window(sine(10.0), FS)
        self.assertGreater(feats.rel["alpha"], 0.95)
        peak = freqs[psd.index(max(psd))]
        self.assertAlmostEqual(peak, 10.0, delta=0.5)

    def test_each_band_sine_lands_in_its_band(self):
        for band, f in (("delta", 2.0), ("theta", 6.0), ("alpha", 11.0), ("beta", 20.0), ("gamma", 36.0)):
            feats, _, _ = dsp.analyze_window(sine(f), FS)
            self.assertGreater(feats.rel[band], 0.9, band)

    def test_rms_of_sine(self):
        feats, _, _ = dsp.analyze_window(sine(10.0, amp=100.0), FS)
        self.assertAlmostEqual(feats.rms, 100 / math.sqrt(2), delta=0.5)

    def test_offset_and_drift_do_not_matter(self):
        base = sine(10.0)
        shifted = [v + 512.0 + 0.3 * i for i, v in enumerate(base)]
        a, _, _ = dsp.analyze_window(base, FS)
        b, _, _ = dsp.analyze_window(shifted, FS)
        self.assertAlmostEqual(a.rel["alpha"], b.rel["alpha"], places=2)
        self.assertAlmostEqual(a.rms, b.rms, delta=0.5)

    def test_relative_powers_sum_to_one(self):
        r = random.Random(3)
        feats, _, _ = dsp.analyze_window([r.gauss(0, 10) for _ in range(N)], FS)
        self.assertAlmostEqual(sum(feats.rel.values()), 1.0, places=6)

    def test_white_noise_follows_band_width(self):
        r = random.Random(4)
        acc = {b: 0.0 for b in dsp.BANDS}
        runs = 40
        for _ in range(runs):
            f, _, _ = dsp.analyze_window([r.gauss(0, 10) for _ in range(N)], FS)
            for b in acc:
                acc[b] += f.rel[b] / runs
        for b, (lo, hi) in dsp.BANDS.items():
            self.assertAlmostEqual(acc[b], (hi - lo) / 41.0, delta=0.03, msg=b)

    def test_engagement_rises_with_beta(self):
        alpha = dsp.analyze_window(sine(10.0), FS)[0].engagement
        beta = dsp.analyze_window(sine(20.0), FS)[0].engagement
        self.assertGreater(beta, alpha + 5)

    def test_hf_ratio_detects_high_frequencies(self):
        calm = dsp.analyze_window(sine(10.0), FS)[0].hf_ratio
        muscle = dsp.analyze_window([a + b for a, b in zip(sine(10.0, 30), sine(80.0, 60))], FS)[0].hf_ratio
        self.assertLess(calm, 0.01)
        self.assertGreater(muscle, 1.0)

    def test_hf_ratio_ignores_mains_hum(self):
        hum = dsp.analyze_window([a + b for a, b in zip(sine(10.0, 30), sine(50.0, 60))], FS)[0].hf_ratio
        self.assertLess(hum, 0.05)

    def test_low_sampling_rate_falls_back_to_gamma(self):
        fs = 100.0
        n = dsp.window_size(fs)
        feats, _, _ = dsp.analyze_window(sine(36.0, n=n, fs=fs), fs)
        self.assertGreater(feats.hf_ratio, 0.5)


class HelpersTests(unittest.TestCase):
    def test_detrend_removes_ramp(self):
        out = dsp.detrend([2.0 * i + 5 for i in range(50)])
        self.assertLess(max(abs(v) for v in out), 1e-9)

    def test_sliding_windows(self):
        # 100 campioni, finestra 40, passo 20: l'ultima finestra (da 60) arriva esattamente a 100
        wins = list(dsp.sliding_windows(list(range(100)), 40, 20))
        self.assertEqual([s for s, _ in wins], [0, 20, 40, 60])
        self.assertTrue(all(len(w) == 40 for _, w in wins))
        # con 99 campioni la finestra da 60 non entra piu'
        short = list(dsp.sliding_windows(list(range(99)), 40, 20))
        self.assertEqual([s for s, _ in short], [0, 20, 40])
        with self.assertRaises(ValueError):
            list(dsp.sliding_windows([1, 2, 3], 0, 1))

    def test_signal_quality_flat(self):
        q = dsp.signal_quality([512.0] * 500, FS)
        self.assertFalse(q["ok"])
        self.assertIn("piatto", q["problems"][0])

    def test_signal_quality_clipped(self):
        q = dsp.signal_quality([0.0 if i % 2 else 1023.0 for i in range(1000)], FS)
        self.assertFalse(q["ok"])
        self.assertTrue(any("ADC" in p for p in q["problems"]))

    def test_signal_quality_mains_hum(self):
        x = [512 + 40 * math.sin(2 * math.pi * 50 * i / FS) for i in range(1024)]
        q = dsp.signal_quality(x, FS)
        self.assertFalse(q["ok"])
        self.assertTrue(any("50 Hz" in p for p in q["problems"]))

    def test_signal_quality_ok(self):
        r = random.Random(5)
        q = dsp.signal_quality([512 + r.gauss(0, 10) for _ in range(1000)], FS)
        self.assertTrue(q["ok"], q["problems"])

    def test_signal_quality_too_short(self):
        self.assertFalse(dsp.signal_quality([1.0], FS)["ok"])


if __name__ == "__main__":
    unittest.main()
