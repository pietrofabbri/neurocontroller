"""Test del collegamento al gioco (UDP) e della modalita' live."""
import socket
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import udp_sim  # noqa: E402

from neurocontroller import game_link  # noqa: E402
from neurocontroller.calibration import run_calibration  # noqa: E402
from neurocontroller.game_link import GameLink, parse_mapping  # noqa: E402
from neurocontroller.live import LiveError, LiveRunner  # noqa: E402
from neurocontroller.profile import (STATE_ARTIFACT, STATE_FOCUSED, STATE_NEUTRAL,  # noqa: E402
                                     STATE_RELAXED, StateClassifier)
from neurocontroller.sources import PERSONAS, CsvReplaySource, SimulatedSource  # noqa: E402

FS = 250.0


class PayloadParityTests(unittest.TestCase):
    """Il bridge reale e il simulatore devono parlare esattamente come si aspetta il gioco."""

    def test_same_payload_as_udp_sim(self):
        for command in game_link.COMMANDS:
            for nul in (True, False):
                self.assertEqual(game_link.encode(command, nul), udp_sim.encode(command, nul))

    def test_same_command_set_as_udp_sim(self):
        self.assertEqual(tuple(game_link.COMMANDS), tuple(udp_sim.VALID_COMMANDS))

    def test_default_port_matches_the_game(self):
        # obj_player/Create_0.gml: network_create_server_raw(network_socket_udp, 6510, 1)
        create = (ROOT / "game/BLeppo2/objects/obj_player/Create_0.gml").read_text(encoding="utf-8")
        self.assertIn(str(game_link.DEFAULT_PORT), create)
        self.assertEqual(game_link.DEFAULT_PORT, udp_sim.DEFAULT_PORT)

    def test_commands_match_those_handled_by_the_game(self):
        handler = (ROOT / "game/BLeppo2/objects/obj_player/Other_68.gml").read_text(encoding="utf-8")
        for command in game_link.COMMANDS:
            self.assertIn('data == "%s"' % command, handler)

    def test_invalid_command(self):
        with self.assertRaises(ValueError):
            game_link.encode("x")


class MappingTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_mapping("concentrato=b, rilassato=a"),
                         {"concentrato": "b", "rilassato": "a"})
        self.assertEqual(parse_mapping(""), {})

    def test_invalid_entries(self):
        for bad in ("concentrato", "felice=a", "concentrato=z", "=a"):
            with self.subTest(text=bad):
                with self.assertRaises(ValueError):
                    parse_mapping(bad)


class FakeSocket:
    def __init__(self):
        self.sent = []
        self.closed = False

    def sendto(self, payload, addr):
        self.sent.append((payload, addr))

    def close(self):
        self.closed = True


class GameLinkTests(unittest.TestCase):
    def test_default_mapping_sends_for_the_two_states_only(self):
        sock = FakeSocket()
        link = GameLink(sock=sock)
        self.assertEqual(link.send_state(STATE_FOCUSED), "b")
        self.assertEqual(link.send_state(STATE_RELAXED), "a")
        self.assertIsNone(link.send_state(STATE_NEUTRAL))
        self.assertIsNone(link.send_state(STATE_ARTIFACT))  # un disturbo non muove l'auto
        self.assertEqual([p for p, _ in sock.sent], [b"b\x00", b"a\x00"])

    def test_repeat_and_no_nul(self):
        sock = FakeSocket()
        link = GameLink(sock=sock, repeat=3, nul=False)
        link.send_state(STATE_FOCUSED)
        self.assertEqual([p for p, _ in sock.sent], [b"b"] * 3)
        self.assertEqual(link.sent, 3)

    def test_invalid_repeat(self):
        with self.assertRaises(ValueError):
            GameLink(sock=FakeSocket(), repeat=0)

    def test_close(self):
        sock = FakeSocket()
        GameLink(sock=sock).close()
        self.assertTrue(sock.closed)

    def test_real_udp_delivery_on_loopback(self):
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.0)
        link = GameLink("127.0.0.1", receiver.getsockname()[1])
        try:
            link.send_state(STATE_FOCUSED)
            self.assertEqual(receiver.recvfrom(16)[0], b"b\x00")
        finally:
            link.close()
            receiver.close()


class LiveRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile, _ = run_calibration(SimulatedSource(FS, PERSONAS["tipica"], seed=3), "P01", seed=3)

    def runner(self, script, link=None, seed=11, **kw):
        source = SimulatedSource(FS, PERSONAS["tipica"], seed=seed, script=script)
        classifier = StateClassifier(self.profile)
        return LiveRunner(source, classifier, link, **kw), sum(s for _, s in script)

    def test_follows_the_simulated_state(self):
        runner, total = self.runner([("relax", 20), ("focus", 20)])
        updates = runner.run(total)
        late_relax = [u.result.state for u in updates if 10 <= u.t <= 19]
        late_focus = [u.result.state for u in updates if 32 <= u.t <= 39]
        self.assertGreater(late_relax.count(STATE_RELAXED), len(late_relax) // 2)
        self.assertGreater(late_focus.count(STATE_FOCUSED), len(late_focus) // 2)

    def test_jaw_clenching_is_flagged_as_artifact(self):
        runner, total = self.runner([("relax", 12), ("jaw", 8)])
        updates = runner.run(total)
        self.assertIn(STATE_ARTIFACT, [u.result.state for u in updates if u.t > 16])

    def test_commands_reach_the_game_link_and_artifacts_send_nothing(self):
        sock = FakeSocket()
        runner, total = self.runner([("relax", 12), ("focus", 12), ("jaw", 8)], link=GameLink(sock=sock))
        updates = runner.run(total)
        sent = [u.command for u in updates if u.command]
        self.assertEqual(len(sent), len(sock.sent))
        self.assertTrue(set(sent) <= {"a", "b"})
        for u in updates:
            if u.result.state == STATE_ARTIFACT:
                self.assertIsNone(u.command)

    def test_on_update_callback(self):
        seen = []
        runner, total = self.runner([("relax", 8)], on_update=seen.append)
        updates = runner.run(total)
        self.assertEqual(len(seen), len(updates))

    def test_sampling_rate_mismatch_is_refused(self):
        source = SimulatedSource(500.0, seed=1)
        with self.assertRaises(LiveError):
            LiveRunner(source, StateClassifier(self.profile))

    def test_invalid_hop(self):
        source = SimulatedSource(FS, seed=1)
        for bad in (0, -0.5, 1.5):
            with self.assertRaises(ValueError):
                LiveRunner(source, StateClassifier(self.profile), hop_fraction=bad)

    def test_end_of_file_becomes_live_error(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.csv"
            path.write_text("\n".join("512" for _ in range(int(FS * 3))) + "\n", encoding="utf-8")
            runner = LiveRunner(CsvReplaySource(str(path), fs=FS), StateClassifier(self.profile))
            with self.assertRaises(LiveError):
                runner.run(60)


if __name__ == "__main__":
    unittest.main()
