"""Test del simulatore UDP: verifica payload e invio su una porta locale effimera.

Esecuzione dalla radice del repository:
    python3 -m unittest discover -s tests -v
"""
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import udp_sim  # noqa: E402


class EncodeTests(unittest.TestCase):
    def test_encode_with_nul_by_default(self):
        self.assertEqual(udp_sim.encode("a"), b"a\x00")
        self.assertEqual(udp_sim.encode("b"), b"b\x00")
        self.assertEqual(udp_sim.encode("g"), b"g\x00")

    def test_encode_without_nul(self):
        self.assertEqual(udp_sim.encode("b", nul=False), b"b")

    def test_invalid_command_rejected(self):
        with self.assertRaises(ValueError):
            udp_sim.encode("x")


class SendTests(unittest.TestCase):
    def setUp(self):
        self.receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.receiver.bind(("127.0.0.1", 0))  # porta effimera
        self.receiver.settimeout(2.0)
        self.port = self.receiver.getsockname()[1]

    def tearDown(self):
        self.receiver.close()

    def test_send_commands_delivers_in_order(self):
        sent = udp_sim.send_commands(
            ["b", "g", "a"], port=self.port, interval=0
        )
        self.assertEqual(sent, 3)
        received = [self.receiver.recvfrom(16)[0] for _ in range(3)]
        self.assertEqual(received, [b"b\x00", b"g\x00", b"a\x00"])

    def test_main_send_mode(self):
        rc = udp_sim.main(
            ["--port", str(self.port), "send", "g", "--count", "2", "--interval", "0"]
        )
        self.assertEqual(rc, 0)
        self.assertEqual(self.receiver.recvfrom(16)[0], b"g\x00")
        self.assertEqual(self.receiver.recvfrom(16)[0], b"g\x00")

    def test_main_no_nul(self):
        udp_sim.main(
            ["--port", str(self.port), "--no-nul", "send", "a", "--interval", "0"]
        )
        self.assertEqual(self.receiver.recvfrom(16)[0], b"a")


if __name__ == "__main__":
    unittest.main()
