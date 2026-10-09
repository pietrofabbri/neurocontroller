"""Prove del lettore del firmware provaBCI (pacchetti binari C7 7C ... 01)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from neurocontroller.sources import ChordsParser, ChordsSerialSource, chords_packet_length  # noqa: E402


def pkt(counter, vals):
    out = bytearray([0xC7, 0x7C, counter & 255])
    for v in vals:
        out += bytes([v >> 8, v & 255])
    out.append(1)
    return bytes(out)


class FakeChordsSerial:
    def __init__(self, chunks, whoru=b"UNO-CLONE\r\n"):
        self.chunks = list(chunks)
        self.whoru = whoru
        self.written = []
        self.closed = False

    def write(self, data):
        self.written.append(data)

    def read(self, size=1):
        if self.written and self.written[-1] == b"WHORU\n" and self.whoru is not None:
            r, self.whoru = self.whoru, None
            return r
        return self.chunks.pop(0) if self.chunks else b""

    def reset_input_buffer(self):
        pass

    def close(self):
        self.closed = True


class ParserTests(unittest.TestCase):
    def test_length(self):
        self.assertEqual(chords_packet_length(6), 16)

    def test_one_packet(self):
        p = ChordsParser(6)
        out = p.push(pkt(7, [512, 1023, 0, 300, 301, 302]))
        self.assertEqual(out, [(7, [512, 1023, 0, 300, 301, 302])])

    def test_split_chunks_and_lost_packets(self):
        stream = pkt(254, [1] * 6) + pkt(1, [2] * 6) + pkt(2, [3] * 6)
        p = ChordsParser(6)
        got = []
        for i in range(0, len(stream), 5):
            got += p.push(stream[i:i + 5])
        self.assertEqual([v[0] for _, v in got], [1, 2, 3])
        self.assertEqual(p.lost, 2)  # mancano 255 e 0

    def test_resync_after_text_and_false_start(self):
        bad = bytearray(pkt(0, [1] * 6))
        bad[15] = 9
        p = ChordsParser(6)
        out = p.push(b"UNO-CLONE\r\n" + b"\xc7\x00\x99" + bytes(bad) + pkt(1, [2] * 6))
        self.assertEqual([v[0] for _, v in out], [2])
        self.assertIn("UNO-CLONE", p.text)


class SourceTests(unittest.TestCase):
    def test_handshake_and_read(self):
        data = b"".join(pkt(i, [100 + i, 0, 0, 0, 0, 0]) for i in range(10))
        fake = FakeChordsSerial([data[:50], data[50:]])
        src = ChordsSerialSource("FAKE", opener=lambda: fake, settle=0)
        self.assertEqual(fake.written, [b"WHORU\n", b"START\n"])
        self.assertEqual(src.board, "UNO-CLONE")
        self.assertEqual(src.read(10), [float(100 + i) for i in range(10)])
        src.close()
        self.assertEqual(fake.written[-1], b"STOP\n")
        self.assertTrue(fake.closed)

    def test_timeout_when_silent(self):
        src = ChordsSerialSource("FAKE", opener=lambda: FakeChordsSerial([]), settle=0)
        with self.assertRaises(TimeoutError):
            src.read(1)

    def test_other_channel_and_bad_channel(self):
        data = pkt(0, [1, 2, 3, 4, 5, 6])
        src = ChordsSerialSource("FAKE", channel=2, opener=lambda: FakeChordsSerial([data]), settle=0)
        self.assertEqual(src.read(1), [3.0])
        with self.assertRaises(ValueError):
            ChordsSerialSource("FAKE", channel=9, opener=lambda: FakeChordsSerial([]), settle=0)

    def test_not_chords_firmware_is_reported(self):
        junk = [b"512\r\n" * 40] * 60
        src = ChordsSerialSource("FAKE", opener=lambda: FakeChordsSerial(junk), settle=0)
        with self.assertRaises(ValueError) as ctx:
            src.read(1)
        self.assertIn("formato", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
