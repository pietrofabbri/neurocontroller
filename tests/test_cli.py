"""Test della riga di comando: i comandi che userebbe una persona vera, con dati in cartelle temporanee."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neurocontroller import cli  # noqa: E402
from neurocontroller.sources import list_serial_ports, pick_port  # noqa: E402


def run(argv, input_fn=lambda prompt: ""):
    lines = []
    rc = cli.main(argv, out=lines.append, input_fn=input_fn)
    return rc, "\n".join(lines)


class CalibrateCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def calibrate(self, *extra):
        return run(["calibrate", "--source", "simulated", "--yes", "--data-dir", self.data, *extra])

    def test_typical_person_gets_a_usable_profile_and_files(self):
        rc, text = self.calibrate("--id", "P01")
        self.assertEqual(rc, 0)
        self.assertIn("USABILE", text)
        self.assertIn("SIMULATO", text)
        self.assertTrue((Path(self.data) / "profiles" / "P01.json").is_file())
        self.assertEqual(len(list((Path(self.data) / "sessions").glob("P01_*_blocchi.csv"))), 1)
        self.assertFalse((Path(self.data) / "raw").exists())

    def test_next_free_id_is_used_when_omitted(self):
        self.calibrate()
        self.calibrate()
        names = sorted(p.name for p in (Path(self.data) / "profiles").glob("*.json"))
        self.assertEqual(names, ["P01.json", "P02.json"])

    def test_existing_profile_is_not_overwritten_silently(self):
        self.calibrate("--id", "P01")
        before = (Path(self.data) / "profiles" / "P01.json").read_text(encoding="utf-8")
        rc, text = self.calibrate("--id", "P01", "--seed", "5")
        self.assertEqual(rc, 2)
        self.assertIn("--overwrite", text)
        self.assertEqual((Path(self.data) / "profiles" / "P01.json").read_text(encoding="utf-8"), before)
        rc, _ = self.calibrate("--id", "P01", "--seed", "5", "--overwrite")
        self.assertEqual(rc, 0)

    def test_a_name_is_refused_as_id(self):
        rc, text = self.calibrate("--id", "Mario")
        self.assertEqual(rc, 2)
        self.assertIn("anonimo", text)
        self.assertFalse((Path(self.data) / "profiles").exists())

    def test_raw_samples_only_with_flag(self):
        self.calibrate("--id", "P01", "--save-raw")
        self.assertTrue(list((Path(self.data) / "raw").glob("P01_*.csv")))

    def test_unresponsive_person_is_declared_unreliable(self):
        rc, text = self.calibrate("--id", "P01", "--persona", "nulla")
        self.assertEqual(rc, 0)
        self.assertIn("NON AFFIDABILE", text)
        self.assertIn("rifiutera", text)

    def test_waits_for_enter_without_yes(self):
        asked = []
        rc, _ = run(["calibrate", "--source", "simulated", "--data-dir", self.data, "--id", "P01"],
                    input_fn=lambda p: asked.append(p) or "")
        self.assertEqual(rc, 0)
        self.assertEqual(len(asked), 6)  # un INVIO per blocco


class LiveCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = cls.tmp.name
        run(["calibrate", "--source", "simulated", "--yes", "--data-dir", cls.data, "--id", "P01"])
        run(["calibrate", "--source", "simulated", "--yes", "--data-dir", cls.data, "--id", "P02",
             "--persona", "nulla"])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def live(self, *extra):
        return run(["live", "--source", "simulated", "--data-dir", self.data, *extra])

    def test_live_with_a_usable_profile(self):
        rc, text = self.live("--profile", "P01", "--script", "relax:8,focus:8")
        self.assertEqual(rc, 0)
        self.assertIn("rilassato", text)
        self.assertIn("SIMULATO", text)

    def test_live_refuses_an_unreliable_profile(self):
        rc, text = self.live("--profile", "P02", "--script", "relax:8")
        self.assertEqual(rc, 2)
        self.assertIn("NON AFFIDABILE", text)
        self.assertIn("--force", text)

    def test_force_overrides_the_refusal(self):
        rc, _ = self.live("--profile", "P02", "--script", "relax:8", "--force")
        self.assertEqual(rc, 0)

    def test_missing_profile(self):
        rc, text = self.live("--profile", "P09")
        self.assertEqual(rc, 2)
        self.assertIn("non trovato", text)

    def test_bad_script(self):
        rc, text = self.live("--profile", "P01", "--script", "relax")
        self.assertEqual(rc, 2)
        self.assertIn("stato:secondi", text)

    def test_udp_flag_sends_to_the_game(self):
        import socket
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.0)
        try:
            rc, text = self.live("--profile", "P01", "--script", "relax:8,focus:8", "--udp",
                                 "--udp-port", str(receiver.getsockname()[1]))
            self.assertEqual(rc, 0)
            self.assertIn("PROVVISORIA", text)
            payload = receiver.recvfrom(16)[0]
            self.assertIn(payload, (b"a\x00", b"b\x00"))
        finally:
            receiver.close()

    def test_profiles_listing(self):
        rc, text = run(["profiles", "--data-dir", self.data])
        self.assertEqual(rc, 0)
        self.assertIn("P01", text)
        self.assertIn("usabile", text)
        self.assertIn("non affidabile", text)
        self.assertIn("SIMULATO", text)

    def test_profiles_listing_when_empty(self):
        with tempfile.TemporaryDirectory() as empty:
            rc, text = run(["profiles", "--data-dir", empty])
        self.assertEqual(rc, 0)
        self.assertIn("Nessun profilo", text)


class DemoAndCheckTests(unittest.TestCase):
    def test_demo_runs_end_to_end_and_leaves_no_files(self):
        before = set(Path(".").iterdir())
        rc, text = run(["demo", "--duration-scale", "0.3"])
        self.assertEqual(rc, 0)
        self.assertIn("SIMULATO", text)
        self.assertIn("riconoscimento in tempo reale", text)
        self.assertEqual(set(Path(".").iterdir()), before)

    def test_check_simulated(self):
        rc, text = run(["check", "--source", "simulated"])
        self.assertEqual(rc, 0)
        self.assertIn("Controllo del segnale: ok", text)

    def test_check_without_a_serial_port_explains_what_to_do(self):
        with mock.patch.object(cli, "list_serial_ports", return_value=[]):
            rc, text = run(["check"])
        self.assertEqual(rc, 2)
        self.assertIn("nessuna porta seriale", text)
        self.assertIn("--source simulated", text)

    def test_replay_without_file_is_an_error(self):
        rc, text = run(["check", "--source", "replay"])
        self.assertEqual(rc, 2)
        self.assertIn("--replay-file", text)

    def test_replay_with_missing_file_is_an_error_not_a_traceback(self):
        rc, text = run(["check", "--source", "replay", "--replay-file", "/non/esiste.csv"])
        self.assertEqual(rc, 2)
        self.assertIn("impossibile leggere", text)


class PortTests(unittest.TestCase):
    def test_pick_port_only_when_unambiguous(self):
        self.assertEqual(pick_port([("/dev/ttyACM0", "Arduino")]), "/dev/ttyACM0")
        self.assertIsNone(pick_port([]))
        self.assertIsNone(pick_port([("COM3", "a"), ("COM4", "b")]))

    def test_ports_command_with_no_port(self):
        with mock.patch.object(cli, "list_serial_ports", return_value=[]):
            rc, text = run(["ports"])
        self.assertEqual(rc, 1)
        self.assertIn("Nessuna porta", text)

    def test_ports_command_lists_ports(self):
        with mock.patch.object(cli, "list_serial_ports", return_value=[("COM3", "Arduino Uno")]):
            rc, text = run(["ports"])
        self.assertEqual(rc, 0)
        self.assertIn("COM3", text)
        self.assertIn("Una sola porta", text)

    def test_several_ports_require_a_choice(self):
        with mock.patch.object(cli, "list_serial_ports", return_value=[("COM3", "a"), ("COM4", "b")]):
            rc, text = run(["check"])
        self.assertEqual(rc, 2)
        self.assertIn("COM3", text)
        self.assertIn("--serial-port", text)

    def test_list_serial_ports_without_pyserial_is_empty(self):
        with mock.patch.dict(sys.modules, {"serial": None, "serial.tools": None,
                                           "serial.tools.list_ports": None}):
            self.assertEqual(list_serial_ports(), [])


if __name__ == "__main__":
    unittest.main()
