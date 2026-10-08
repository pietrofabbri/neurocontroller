"""Prove del server locale: API, validazione, privacy (codici anonimi), cancellazione, file statici."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from neurocontroller.server import Store, make_server

STATIC = Path(__file__).resolve().parent.parent / "web" / "app"


def _game(**over):
    g = dict(player_a="P01", player_b="P02", source="simulata", seed=7, duration_s=600.0,
             depth_m=123.4, gems=3, rocks_hit=2, coherent_s=300.0, incoherent_s=100.0,
             neutral_s=150.0, artifact_s=50.0, quality_pct=91.5, score=130.0,
             series=[dict(t=1.0, depth_m=0.5, terrain="compatto", state="concentrato", score_b=0.7,
                          quality=1.0, tempo=100, brightness=0.5, density=0.5, register=0.5)])
    g.update(over)
    return g


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.static = Path(cls.tmp.name) / "app"
        cls.static.mkdir()
        (cls.static / "index.html").write_text("<title>x</title>", encoding="utf-8")
        (cls.static / "a.js").write_text("export const a=1;", encoding="utf-8")
        (Path(cls.tmp.name) / "segreto.txt").write_text("no", encoding="utf-8")
        cls.server, cls.store = make_server(Path(cls.tmp.name) / "db" / "g.sqlite3", cls.static, port=0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def call(self, method, path, body=None, headers=None, raw=False):
        data = None
        hdrs = {"Host": "localhost:%d" % self.port}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        hdrs.update(headers or {})
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=data,
                                     method=method, headers=hdrs)
        try:
            with urllib.request.urlopen(req) as r:
                payload = r.read()
                return r.status, (payload if raw else json.loads(payload.decode("utf-8")))
        except urllib.error.HTTPError as e:
            payload = e.read()
            try:
                return e.code, json.loads(payload.decode("utf-8"))
            except ValueError:
                return e.code, payload

    def test_players_codes_are_anonymous_and_sequential(self):
        s1, p1 = self.call("POST", "/api/players", {})
        s2, p2 = self.call("POST", "/api/players", {})
        self.assertEqual((s1, s2), (201, 201))
        self.assertTrue(p1["code"].startswith("P") and p2["code"] > p1["code"])

    def test_names_are_refused(self):
        for bad in ("Mario", "mario.rossi", "P1", "P0001", "<script>"):
            with self.subTest(code=bad):
                status, _ = self.call("POST", "/api/players", {"code": bad})
                self.assertEqual(status, 400)

    def test_game_roundtrip_leaderboard_series_and_csv(self):
        for code in ("P71", "P72"):
            self.call("POST", "/api/players", {"code": code})
        status, res = self.call("POST", "/api/games", _game(player_a="P71", player_b="P72", score=999.0))
        self.assertEqual(status, 201)
        gid = res["id"]
        _, lst = self.call("GET", "/api/games?player=P71")
        self.assertEqual(lst["games"][0]["id"], gid)
        _, ser = self.call("GET", "/api/games/%d/series" % gid)
        self.assertEqual(ser["series"][0]["state"], "concentrato")
        self.assertIn("register", ser["series"][0])
        _, lb = self.call("GET", "/api/leaderboard?limit=1")
        self.assertEqual(lb["games"][0]["id"], gid)
        status, csv_bytes = self.call("GET", "/api/export.csv", raw=True)
        self.assertEqual(status, 200)
        self.assertIn(b"player_a", csv_bytes.splitlines()[0])

    def test_invalid_games_are_rejected(self):
        self.call("POST", "/api/players", {"code": "P73"})
        self.call("POST", "/api/players", {"code": "P74"})
        base = _game(player_a="P73", player_b="P74")
        cases = [dict(source="altro"), dict(depth_m=-1), dict(quality_pct=101), dict(player_a="Mario"),
                 dict(gems="tanti"), dict(series=[dict(t=0, depth_m=0, terrain="sabbia", state="x",
                                                       score_b=0, quality=0, tempo=0, brightness=0,
                                                       density=0, register=0)])]
        for over in cases:
            with self.subTest(over=list(over)):
                status, _ = self.call("POST", "/api/games", dict(base, **over))
                self.assertEqual(status, 400)
        status, _ = self.call("POST", "/api/games", dict(base, player_b="P99"))
        self.assertEqual(status, 404)

    def test_delete_player_removes_games_and_series(self):
        self.call("POST", "/api/players", {"code": "P81"})
        self.call("POST", "/api/players", {"code": "P82"})
        _, res = self.call("POST", "/api/games", _game(player_a="P81", player_b="P82"))
        status, _ = self.call("DELETE", "/api/players/P81")
        self.assertEqual(status, 200)
        _, ser = self.call("GET", "/api/games/%d/series" % res["id"])
        self.assertEqual(ser["series"], [])
        _, lst = self.call("GET", "/api/games?player=P82")
        self.assertEqual(lst["games"], [])

    def test_post_requires_json_content_type(self):
        req = urllib.request.Request("http://127.0.0.1:%d/api/players" % self.port, data=b"{}", method="POST",
                                     headers={"Host": "localhost:%d" % self.port,
                                              "Content-Type": "text/plain"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 415)

    def test_foreign_host_header_is_refused(self):
        status, _ = self.call("GET", "/api/health", headers={"Host": "evil.example"})
        self.assertEqual(status, 403)

    def test_static_files_and_no_path_traversal(self):
        status, body = self.call("GET", "/", raw=True)
        self.assertEqual((status, b"<title>x" in body), (200, True))
        status, body = self.call("GET", "/a.js", raw=True)
        self.assertEqual(status, 200)
        status, _ = self.call("GET", "/../segreto.txt", raw=True)
        self.assertIn(status, (403, 404))
        status, _ = self.call("GET", "/%2e%2e/segreto.txt", raw=True)
        self.assertIn(status, (403, 404))

    def test_in_memory_store(self):
        st = Store(Path(":memory:"))
        st.create_player("P01")
        st.create_player("P02")
        gid = st.add_game(_game())
        self.assertEqual(st.list_games("P01", 5)[0]["id"], gid)


@unittest.skipUnless((STATIC / "index.html").is_file(), "web/app non ancora presente")
class WebAppFilesTests(unittest.TestCase):
    def test_core_has_no_external_resources(self):
        """V-15: il nucleo funziona offline, senza caricare nulla da altri siti."""
        import re
        pat = re.compile(r"""(?:src|href)\s*=\s*["']https?://|url\(\s*["']?https?://|@import\s+["']?https?://|import\s+.*from\s+["']https?://""")
        for f in STATIC.rglob("*"):
            if f.suffix in (".html", ".js", ".css", ".mjs"):
                with self.subTest(file=f.name):
                    self.assertIsNone(pat.search(f.read_text(encoding="utf-8")),
                                      "%s carica risorse esterne" % f)


if __name__ == "__main__":
    unittest.main()
