"""Test delle sorgenti: simulatore, seriale (con porta finta), riproduzione da file."""
import statistics
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neurocontroller import dsp  # noqa: E402
from neurocontroller.sources import (PERSONAS, CsvReplaySource, SerialSource,  # noqa: E402
                                     SimulatedSource, parse_line)

FS = 250.0


class ParseLineTests(unittest.TestCase):
    def test_valid_lines(self):
        self.assertEqual(parse_line(b"512\r\n"), 512.0)
        self.assertEqual(parse_line(b"  498 \n"), 498.0)
        self.assertEqual(parse_line(b"512,498,300\n", column=1), 498.0)
        self.assertEqual(parse_line(b"1;2;3", column=2), 3.0)
        self.assertEqual(parse_line(b"-3.5"), -3.5)

    def test_invalid_lines(self):
        self.assertIsNone(parse_line(b""))
        self.assertIsNone(parse_line(b"   \r\n"))
        self.assertIsNone(parse_line(b"abc"))
        self.assertIsNone(parse_line(b"512,498", column=5))
        self.assertIsNone(parse_line(b"\xff\xfe"))


class FakeSerial:
    def __init__(self, lines):
        self.lines = list(lines)
        self.flushed = 0
        self.closed = False

    def readline(self):
        return self.lines.pop(0) if self.lines else b""

    def reset_input_buffer(self):
        self.flushed += 1

    def close(self):
        self.closed = True


class SerialSourceTests(unittest.TestCase):
    def make(self, lines, **kw):
        fake = FakeSerial(lines)
        return SerialSource("FAKE", opener=lambda: fake, **kw), fake

    def test_reads_requested_samples_and_skips_garbage(self):
        src, _ = self.make([b"hello\r\n", b"1\n", b"2\n", b"#x\n", b"3\n"])
        self.assertEqual(src.read(3), [1.0, 2.0, 3.0])
        self.assertEqual(src.bad_lines, 2)

    def test_timeout_when_no_data(self):
        src, _ = self.make([b"1\n"])
        with self.assertRaises(TimeoutError):
            src.read(5)

    def test_unrecognised_format_is_reported(self):
        src, _ = self.make([b"\xc7\x7c\x00\x01\n"] * 300)
        with self.assertRaises(ValueError) as ctx:
            src.read(1)
        self.assertIn("formato", str(ctx.exception))

    def test_flush_and_close(self):
        src, fake = self.make([])
        src.flush()
        src.close()
        self.assertEqual(fake.flushed, 1)
        self.assertTrue(fake.closed)

    def test_flags(self):
        src, _ = self.make([])
        self.assertTrue(src.realtime)
        self.assertFalse(src.simulated)


class CsvReplayTests(unittest.TestCase):
    def write(self, text):
        d = tempfile.mkdtemp()
        p = Path(d) / "x.csv"
        p.write_text(text, encoding="utf-8")
        return str(p)

    def test_reads_numbers_skipping_header(self):
        src = CsvReplaySource(self.write("valore\n1\n2\n3\n4\n"), fs=FS)
        self.assertEqual(src.read(2), [1.0, 2.0])
        self.assertEqual(src.read(2), [3.0, 4.0])

    def test_end_of_file(self):
        src = CsvReplaySource(self.write("1\n2\n"), fs=FS)
        with self.assertRaises(EOFError):
            src.read(5)

    def test_empty_file(self):
        with self.assertRaises(ValueError):
            CsvReplaySource(self.write("niente\n"), fs=FS)

    def test_column_selection(self):
        src = CsvReplaySource(self.write("1,10\n2,20\n"), fs=FS, column=1)
        self.assertEqual(src.read(2), [10.0, 20.0])


class SimulatedSourceTests(unittest.TestCase):
    def feats(self, source, seconds=30):
        n = dsp.window_size(source.fs)
        x = source.read(int(seconds * source.fs))
        return [dsp.analyze_window(w, source.fs)[0] for _, w in dsp.sliding_windows(x, n, n // 2)]

    def test_flags_and_description(self):
        s = SimulatedSource()
        self.assertTrue(s.simulated)
        self.assertFalse(s.realtime)
        self.assertIn("SIMULATO", s.description)

    def test_deterministic_with_seed(self):
        a = SimulatedSource(seed=7).read(500)
        b = SimulatedSource(seed=7).read(500)
        c = SimulatedSource(seed=8).read(500)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_values_stay_in_adc_range(self):
        s = SimulatedSource(seed=1)
        s.set_state("jaw")
        x = s.read(3000)
        self.assertGreaterEqual(min(x), 0.0)
        self.assertLessEqual(max(x), 1023.0)

    def test_unknown_state_rejected(self):
        with self.assertRaises(ValueError):
            SimulatedSource().set_state("dormire")

    def test_states_have_the_assumed_signature(self):
        e = {}
        for state in ("closed", "relax", "focus"):
            s = SimulatedSource(FS, PERSONAS["tipica"], seed=2)
            s.set_state(state)
            e[state] = statistics.mean(f.engagement for f in self.feats(s))
        self.assertLess(e["closed"], e["relax"])
        self.assertLess(e["relax"], e["focus"])

    def test_jaw_is_visible_as_high_frequency_noise(self):
        calm = SimulatedSource(FS, seed=3)
        calm.set_state("relax")
        jaw = SimulatedSource(FS, seed=3)
        jaw.set_state("jaw")
        self.assertGreater(statistics.median(f.hf_ratio for f in self.feats(jaw)),
                           20 * statistics.median(f.hf_ratio for f in self.feats(calm)))

    def test_blink_and_eyes_raise_amplitude(self):
        base = SimulatedSource(FS, seed=4)
        base.set_state("relax")
        ref = statistics.median(f.rms for f in self.feats(base))
        for state in ("blink", "eyes"):
            s = SimulatedSource(FS, seed=4)
            s.set_state(state)
            self.assertGreater(statistics.median(f.rms for f in self.feats(s)), 1.8 * ref, state)

    def test_persona_nulla_does_not_react(self):
        means = []
        for state in ("relax", "focus"):
            s = SimulatedSource(FS, PERSONAS["nulla"], seed=5)
            s.set_state(state)
            means.append(statistics.mean(f.engagement for f in self.feats(s)))
        self.assertAlmostEqual(means[0], means[1], places=6)

    def test_script_follows_timeline(self):
        s = SimulatedSource(FS, seed=6, script=[("relax", 4), ("jaw", 4)])
        n = dsp.window_size(FS)
        first = dsp.analyze_window(s.read(n)[:n], FS)[0]  # primi ~2 s: relax
        s.read(int(3 * FS))                                # attraversa il confine
        later = dsp.analyze_window(s.read(n), FS)[0]
        self.assertGreater(later.hf_ratio, 20 * first.hf_ratio)


if __name__ == "__main__":
    unittest.main()
