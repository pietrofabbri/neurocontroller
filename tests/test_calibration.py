"""Test della calibrazione guidata: registrazione, controllo del segnale, salvataggio dei file."""
import csv
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neurocontroller import dsp  # noqa: E402
from neurocontroller.calibration import (CSV_COLUMNS, CalibrationError, ConsoleUI,  # noqa: E402
                                         QuietUI, blocks_to_rows, check_signal, default_data_dir,
                                         record_block, report_text, run_calibration, save_session)
from neurocontroller.profile import ProfileError  # noqa: E402
from neurocontroller.protocol import (ROLE_ARTIFACT, ROLE_FOCUS, ROLE_RELAX, Block,  # noqa: E402
                                      default_protocol, scaled)
from neurocontroller.sources import (PERSONAS, CsvReplaySource, SimulatedSource,  # noqa: E402
                                     Source)

FS = 250.0


class ScriptedSource(Source):
    """Sorgente di prova: valori forniti da una funzione, con scala ADC configurabile."""

    def __init__(self, make, fs=FS, adc_max=1023.0):
        self.fs = fs
        self.adc_max = adc_max
        self._make = make
        self._i = 0

    def read(self, n):
        out = [self._make(self._i + k) for k in range(n)]
        self._i += n
        return out


def noisy(center, sd, seed=1):
    rng = random.Random(seed)
    return lambda i: center + rng.gauss(0, sd)


class RecordBlockTests(unittest.TestCase):
    def test_records_exactly_the_block_duration(self):
        block = Block(key="x", title="x", role=ROLE_RELAX, duration=12, instruction="", sim_state="relax",
                      stimulus="x")
        samples = record_block(SimulatedSource(FS, seed=1), block, QuietUI(), random.Random(0))
        self.assertEqual(len(samples), int(12 * FS))

    def test_prompts_are_shown_in_time_order_and_once(self):
        block = next(b for b in default_protocol() if b.role == ROLE_ARTIFACT)
        ui = QuietUI()
        record_block(SimulatedSource(FS, seed=1), block, ui, random.Random(0))
        shown = [line[4:] for line in ui.log if line.startswith("  > ")]
        self.assertEqual(shown, [p.text for p in block.prompts])

    def test_problems_appear_during_multiplication_block(self):
        block = next(b for b in default_protocol() if b.problem_kind)
        ui = QuietUI()
        record_block(SimulatedSource(FS, seed=1), block, ui, random.Random(3))
        problems = [line for line in ui.log if " x " in line]
        self.assertGreaterEqual(len(problems), int(block.duration / block.problem_interval))


class CheckSignalTests(unittest.TestCase):
    def test_simulated_signal_passes(self):
        q = check_signal(SimulatedSource(FS, seed=1), QuietUI())
        self.assertTrue(q["ok"])

    def test_flat_signal_is_rejected(self):
        with self.assertRaises(CalibrationError) as cm:
            check_signal(ScriptedSource(lambda i: 512.0), QuietUI())
        self.assertIn("piatto", str(cm.exception))

    def test_twelve_bit_signal_needs_adc_max(self):
        # Segnale sano a 12 bit (valori attorno a 2048): con il limite di default (1023 =
        # 10 bit) sembrerebbe tutto saturo e la calibrazione verrebbe rifiutata a torto.
        make = noisy(2048.0, 40.0)
        with self.assertRaises(CalibrationError) as cm:
            check_signal(ScriptedSource(make, adc_max=1023.0), QuietUI())
        self.assertIn("ADC", str(cm.exception))
        q = check_signal(ScriptedSource(noisy(2048.0, 40.0), adc_max=4095.0), QuietUI())
        self.assertTrue(q["ok"])


class RunCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile, cls.blocks = run_calibration(SimulatedSource(FS, seed=2), "P07", seed=2)

    def test_every_protocol_block_is_analysed(self):
        self.assertEqual(set(self.blocks), {b.key for b in default_protocol()})
        self.assertTrue(all(b.features for b in self.blocks.values()))

    def test_profile_metadata(self):
        self.assertEqual(self.profile.participant_id, "P07")
        self.assertEqual(self.profile.fs, FS)
        self.assertEqual(self.profile.window, dsp.window_size(FS))
        self.assertTrue(self.profile.simulated)

    def test_raw_samples_not_kept_by_default(self):
        self.assertTrue(all(b.raw is None for b in self.blocks.values()))

    def test_raw_samples_kept_on_request(self):
        _, blocks = run_calibration(SimulatedSource(FS, seed=2), "P07", seed=2, keep_raw=True,
                                    protocol=scaled(default_protocol(), 0.5))
        self.assertTrue(all(b.raw for b in blocks.values()))

    def test_name_as_id_is_rejected_before_recording(self):
        source = mock.Mock(wraps=SimulatedSource(FS, seed=2))
        with self.assertRaises(ProfileError):
            run_calibration(source, "Mario")
        source.read.assert_not_called()

    def test_flat_sensor_stops_the_calibration(self):
        with self.assertRaises(CalibrationError):
            run_calibration(ScriptedSource(lambda i: 512.0), "P01")

    def test_skip_check_allows_start_but_data_are_still_validated(self):
        # senza controllo iniziale il segnale piatto non viene fermato prima,
        # ma il profilo non puo' comunque risultare costruibile/affidabile
        try:
            profile, _ = run_calibration(ScriptedSource(lambda i: 512.0), "P01", skip_check=True)
        except ProfileError:
            return
        self.assertFalse(profile.usable)

    def test_ctrl_c_gives_a_clear_error_and_no_profile(self):
        class Interrupting(SimulatedSource):
            def read(self, n):
                raise KeyboardInterrupt

        with self.assertRaises(CalibrationError) as cm:
            run_calibration(Interrupting(FS, seed=1), "P01", skip_check=True)
        self.assertIn("nessun profilo", str(cm.exception))

    def test_file_too_short_gives_a_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "short.csv"
            path.write_text("\n".join("512" for _ in range(500)) + "\n", encoding="utf-8")
            with self.assertRaises(CalibrationError):
                run_calibration(CsvReplaySource(str(path), fs=FS), "P01", skip_check=True)


class SaveSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile, cls.blocks = run_calibration(SimulatedSource(FS, seed=2), "P07", seed=2,
                                                  keep_raw=True)

    def test_files_are_written_where_expected(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = save_session(self.profile, self.blocks, Path(tmp))
            self.assertTrue(paths["profile"].is_file())
            self.assertEqual(paths["profile"].parent.name, "profiles")
            self.assertTrue(paths["blocks_csv"].is_file())
            self.assertEqual(paths["blocks_csv"].parent.name, "sessions")
            self.assertFalse((Path(tmp) / "raw").exists())  # nessun grezzo se non richiesto

    def test_raw_files_only_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = save_session(self.profile, self.blocks, Path(tmp), save_raw=True)
            raws = [p for k, p in paths.items() if k.startswith("raw_")]
            self.assertEqual(len(raws), len(self.blocks))
            first = raws[0].read_text(encoding="utf-8").splitlines()
            self.assertTrue(all(float(v) is not None for v in first[:10]))

    def test_csv_follows_the_documented_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = save_session(self.profile, self.blocks, Path(tmp))
            with paths["blocks_csv"].open(newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        self.assertEqual(list(rows[0].keys()), CSV_COLUMNS)
        bands = {r["band"] for r in rows}
        self.assertEqual(bands, set(dsp.BANDS))
        self.assertEqual(len(rows), len(self.blocks) * len(dsp.BANDS))

    def test_csv_has_only_anonymous_id_and_marks_simulated(self):
        rows = blocks_to_rows(self.profile, self.blocks)
        self.assertTrue(all(r["participant_id"] == "P07" for r in rows))
        self.assertTrue(all("SIMULATO" in r["notes"] for r in rows))

    def test_peak_lies_inside_its_band(self):
        for r in blocks_to_rows(self.profile, self.blocks):
            lo, hi = dsp.BANDS[r["band"]]
            self.assertTrue(lo <= float(r["peak_hz"]) < hi, r)

    def test_alpha_peak_is_higher_with_eyes_closed(self):
        rows = blocks_to_rows(self.profile, self.blocks)
        rel = {r["stimulus"]: float(r["mean_rel_power"]) for r in rows if r["band"] == "alpha"}
        self.assertGreater(rel["occhi_chiusi"], rel["calcolo_sottrazioni"])


class ReportAndDirTests(unittest.TestCase):
    def test_report_shows_level_and_simulation_notice(self):
        profile, _ = run_calibration(SimulatedSource(FS, PERSONAS["nulla"], seed=2), "P01", seed=2)
        text = report_text(profile)
        self.assertIn("NON AFFIDABILE", text)
        self.assertIn("SIMULATO", text)

    def test_default_data_dir_from_environment(self):
        with mock.patch.dict(os.environ, {"NEUROCONTROLLER_DATA": "/tmp/xyz"}):
            self.assertEqual(default_data_dir(), Path("/tmp/xyz"))
        env = dict(os.environ)
        env.pop("NEUROCONTROLLER_DATA", None)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(default_data_dir().name, "data")


class ConsoleUITests(unittest.TestCase):
    def test_waits_for_enter_unless_auto_start(self):
        calls = []
        ui = ConsoleUI(input_fn=lambda p: calls.append(p) or "", print_fn=lambda s: None)
        ui.wait_ready()
        self.assertEqual(len(calls), 1)
        ui = ConsoleUI(auto_start=True, input_fn=lambda p: calls.append(p) or "", print_fn=lambda s: None)
        ui.wait_ready()
        self.assertEqual(len(calls), 1)

    def test_quiet_prompts_hide_instructions(self):
        lines = []
        ConsoleUI(quiet_prompts=True, print_fn=lines.append).prompt("STRINGI")
        ConsoleUI(quiet_prompts=False, print_fn=lines.append).prompt("STRINGI")
        self.assertEqual(len(lines), 1)

    def test_countdown_sleeps_only_when_asked(self):
        slept = []
        ui = ConsoleUI(print_fn=lambda s: None, sleep_fn=slept.append)
        ui.countdown(3, sleep=False)
        self.assertEqual(slept, [])
        ui.countdown(3, sleep=True)
        self.assertEqual(slept, [1.0, 1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
