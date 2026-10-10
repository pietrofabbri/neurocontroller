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
             series=[dict(t=1.0, depth_m=0.5, terrain="duro", state="concentrato", score_b=0.7,
                          quality=1.0, coherence=0.8, tempo=100, density=0.5, softness=0.5, reason="")])
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
        self.assertIn("softness", ser["series"][0])
        self.assertNotIn("register", ser["series"][0])
        _, lb = self.call("GET", "/api/leaderboard?limit=1")
        self.assertEqual(lb["games"][0]["id"], gid)
        status, csv_bytes = self.call("GET", "/api/export.csv", raw=True)
        self.assertEqual(status, 200)
        header = csv_bytes.splitlines()[0]
        self.assertIn(b"player_a", header)
        self.assertIn(b"a_age_years", header)
        self.assertIn(b"b_consent", header)
        status, csv_series = self.call("GET", "/api/export-series.csv", raw=True)
        self.assertEqual(status, 200)
        self.assertTrue(csv_series.startswith(b"game_id,t,depth_m,terrain"))

    def test_invalid_games_are_rejected(self):
        self.call("POST", "/api/players", {"code": "P73"})
        self.call("POST", "/api/players", {"code": "P74"})
        base = _game(player_a="P73", player_b="P74")
        cases = [dict(source="altro"), dict(depth_m=-1), dict(quality_pct=101), dict(player_a="Mario"),
                 dict(gems="tanti"), dict(series=[dict(t=0, depth_m=0, terrain="sabbia", state="x",
                                                       score_b=0, quality=0, tempo=0,
                                                       density=0, softness=0)]),
                 dict(series=[dict(t=0, depth_m=0, terrain="duro", state="neutro", score_b=0, quality=0,
                                   tempo=0, density=0, softness=0, reason="boh")]),
                 dict(sensor_format="wifi"), dict(b_fatigue=9), dict(b_sleep_h=30), dict(app_version="<x>"),
                 dict(profile_level="ottimo"), dict(b_caffeine_3h=2)]
        for over in cases:
            with self.subTest(over=list(over)):
                status, _ = self.call("POST", "/api/games", dict(base, **over))
                self.assertEqual(status, 400)
        status, _ = self.call("POST", "/api/games", dict(base, player_b="P99"))
        self.assertEqual(status, 404)
        status, _ = self.call("POST", "/api/games", dict(base, nome="Mario"))   # campi sconosciuti: ignorati, mai archiviati
        self.assertEqual(status, 201)
        _, lst = self.call("GET", "/api/games?player=P73")
        self.assertNotIn("nome", lst["games"][0])

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

    def test_player_card_is_choices_only_and_consent_is_explicit(self):
        self.call("POST", "/api/players", {"code": "P61"})
        ok = {"age_years": 17, "gender": "donna", "handedness": "sinistra", "gaming": "4-10h",
              "music_training": "2-5", "education": "superiori"}
        status, p = self.call("PUT", "/api/players/P61", ok)
        self.assertEqual(status, 200)
        self.assertEqual((p["age_years"], p["gender"], p["consent"]), (17, "donna", 0))
        for bad in ({"age_years": 3}, {"age_years": 120}, {"age_years": "dieci"}, {"gender": "Mario"},
                    {"nome": "Mario"}, {"diagnosi": "x"}, {"consent": 1}, {"consent": 1, "consent_by": "amico"},
                    {"gaming": "tanto"}):
            with self.subTest(bad=bad):
                status, _ = self.call("PUT", "/api/players/P61", bad)
                self.assertEqual(status, 400)
        status, p = self.call("PUT", "/api/players/P61", {"consent": 1, "consent_by": "genitore_tutore"})
        self.assertEqual((status, p["consent"], p["consent_by"]), (200, 1, "genitore_tutore"))
        self.assertTrue(p["consent_at"].endswith("Z") and p["consent_version"])
        status, p = self.call("PUT", "/api/players/P61", {"consent": 0})
        self.assertEqual((p["consent"], p["consent_by"], p["consent_at"]), (0, None, None))
        status, _ = self.call("PUT", "/api/players/P98", {})
        self.assertEqual(status, 404)
        _, lst = self.call("GET", "/api/players")
        self.assertIn("age_years", lst["players"][0])
        self.assertIn("consent", lst["players"][0])

    def test_sensor_games_need_consent_of_both_players(self):
        for code in ("P51", "P52"):
            self.call("POST", "/api/players", {"code": code})
        game = _game(player_a="P51", player_b="P52", source="sensore", signal_fs_hz=193.4, sensor_format="ascii",
                     sensor_baud=9600, profile_level="affidabile", profile_dprime=2.1, profile_accuracy=0.9,
                     calib_protocol="web-v1-30s", b_sleep_h=7.5, b_caffeine_3h=0, b_fatigue=2, app_version="W0.2")
        status, body = self.call("POST", "/api/games", game)
        self.assertEqual(status, 409)
        self.assertIn("P51", body["error"])
        self.call("PUT", "/api/players/P51", {"consent": 1, "consent_by": "persona"})
        status, body = self.call("POST", "/api/games", game)
        self.assertEqual(status, 409)
        self.assertIn("P52", body["error"])
        self.call("PUT", "/api/players/P52", {"consent": 1, "consent_by": "genitore_tutore"})
        status, body = self.call("POST", "/api/games", game)
        self.assertEqual(status, 201)
        _, lst = self.call("GET", "/api/games?player=P52")
        g = lst["games"][0]
        self.assertEqual((g["signal_fs_hz"], g["sensor_format"], g["b_fatigue"]), (193.4, "ascii", 2))
        # la partita simulata non ha bisogno di consenso e lascia vuoti i campi tecnici del sensore
        self.call("POST", "/api/players", {"code": "P53"})
        self.call("POST", "/api/players", {"code": "P54"})
        status, _ = self.call("POST", "/api/games", _game(player_a="P53", player_b="P54"))
        self.assertEqual(status, 201)
        _, lst = self.call("GET", "/api/games?player=P54")
        self.assertIsNone(lst["games"][0]["signal_fs_hz"])
        # il CSV porta la scheda di A e di B accanto alla partita
        _, csv_bytes = self.call("GET", "/api/export.csv", raw=True)
        rows = csv_bytes.decode("utf-8").splitlines()
        header = rows[0].split(",")
        self.assertTrue(any("P52" in r for r in rows))
        self.assertEqual(len(header), len(set(header)), "colonne duplicate")

    def test_in_memory_store(self):
        st = Store(Path(":memory:"))
        st.create_player("P01")
        st.create_player("P02")
        gid = st.add_game(_game())
        self.assertEqual(st.list_games("P01", 5)[0]["id"], gid)


V1_SCHEMA = """
CREATE TABLE players (code TEXT PRIMARY KEY, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
CREATE TABLE games (id INTEGER PRIMARY KEY AUTOINCREMENT, played_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
 player_a TEXT NOT NULL REFERENCES players(code) ON DELETE CASCADE, player_b TEXT NOT NULL REFERENCES players(code) ON DELETE CASCADE,
 source TEXT NOT NULL CHECK (source IN ('simulata','sensore')), seed INTEGER NOT NULL, duration_s REAL NOT NULL, depth_m REAL NOT NULL,
 gems INTEGER NOT NULL, rocks_hit INTEGER NOT NULL, coherent_s REAL NOT NULL, incoherent_s REAL NOT NULL, neutral_s REAL NOT NULL,
 artifact_s REAL NOT NULL, quality_pct REAL NOT NULL, score REAL NOT NULL);
CREATE INDEX games_a ON games(player_a); CREATE INDEX games_b ON games(player_b);
CREATE TABLE game_series (game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE, t REAL NOT NULL, depth_m REAL NOT NULL,
 terrain TEXT NOT NULL, state TEXT NOT NULL, score_b REAL NOT NULL, quality REAL NOT NULL, tempo REAL NOT NULL, brightness REAL NOT NULL,
 density REAL NOT NULL, register_ REAL NOT NULL);
CREATE INDEX series_game ON game_series(game_id);
PRAGMA user_version=1;
INSERT INTO players(code) VALUES ('P01'),('P02');
INSERT INTO games(player_a,player_b,source,seed,duration_s,depth_m,gems,rocks_hit,coherent_s,incoherent_s,neutral_s,artifact_s,quality_pct,score)
 VALUES ('P01','P02','sensore',1,600,258.9,0,3,81,145,47,327,45,2589);
INSERT INTO game_series VALUES (1,1.0,0.25,'soffice','rilassato',0.5,1.0,100,0.3,0.5,0.5);
"""


class MigrationTests(unittest.TestCase):
    def _columns(self, store, table):
        with store._tx() as c:
            return [r[1] for r in c.execute("PRAGMA table_info(%s)" % table)]

    def test_v1_database_is_migrated_without_losing_games(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "g.sqlite3"
            conn = sqlite3.connect(str(path))
            conn.executescript(V1_SCHEMA)
            conn.commit()
            conn.close()
            st = Store(path)
            self.assertEqual(st.migrated_from, 1)
            self.assertTrue((Path(tmp) / "g.sqlite3.v1.bak").is_file(), "copia di sicurezza")
            g = st.list_games(None, 5)[0]
            self.assertEqual((g["depth_m"], g["source"], g["app_version"]), (258.9, "sensore", None))
            row = st.series(1)[0]
            self.assertAlmostEqual(row["softness"], 0.7)        # 1 - luminosita'
            self.assertEqual(row["reason"], "")
            self.assertNotIn("register_", row)
            self.assertEqual(st.list_players()[0]["consent"], 0, "i vecchi giocatori non hanno ancora dato il consenso")
            fresh = Store(Path(tmp) / "nuovo.sqlite3")
            self.assertIsNone(fresh.migrated_from)
            for table in ("players", "games", "game_series"):
                self.assertEqual(sorted(self._columns(st, table)), sorted(self._columns(fresh, table)), table)
            Store(path)                                         # riaprirlo non rimigra
            self.assertEqual(len(list(Path(tmp).glob("*.bak"))), 1)


class DataDictionaryTests(unittest.TestCase):
    """Il dizionario dei dati (web/06-dati-ricerca.md) deve descrivere ogni colonna del database e dell'export."""

    DOC = Path(__file__).resolve().parent.parent / "web" / "06-dati-ricerca.md"

    def test_every_column_is_documented(self):
        from neurocontroller import server
        store = Store(Path(":memory:"))
        text = self.DOC.read_text(encoding="utf-8")
        with store._tx() as c:
            for table in ("players", "games", "game_series"):
                for col in [r[1] for r in c.execute("PRAGMA table_info(%s)" % table)]:
                    with self.subTest(table=table, col=col):
                        self.assertIn("`%s`" % col, text, "colonna %s.%s non descritta nel dizionario dei dati" % (table, col))
        for choices in server.PLAYER_CHOICES.values():
            for value in choices:
                self.assertIn(value, text)
        for value in server.REASONS[1:] + server.TERRAINS:
            self.assertIn(value, text)

    def test_browser_archive_uses_the_same_fields_as_the_server(self):
        """Il sito statico e il server devono salvare gli stessi campi (stesso ordine delle colonne dell'export)."""
        import re
        from neurocontroller import server
        js = (STATIC / "js" / "archivio_locale.mjs").read_text(encoding="utf-8")

        def js_list(name):
            m = re.search(r"export const %s = \[(.*?)\];" % name, js, re.S)
            self.assertIsNotNone(m, name)
            return re.findall(r"'([^']*)'", m.group(1))

        store = Store(Path(":memory:"))
        with store._tx() as c:
            games = [r[1] for r in c.execute("PRAGMA table_info(games)")]
            series = [r[1] for r in c.execute("PRAGMA table_info(game_series)") if r[1] != "game_id"]
            players = [r[1] for r in c.execute("PRAGMA table_info(players)") if r[1] not in ("code", "created_at")]
        self.assertEqual(js_list("GAME_COLS"), games)
        self.assertEqual(js_list("SERIES_COLS"), series)
        self.assertEqual(js_list("PLAYER_FIELDS"), players)
        self.assertEqual(js_list("TERRAINS"), list(server.TERRAINS))
        self.assertEqual(js_list("REASONS"), list(server.REASONS))
        self.assertEqual(js_list("STATES"), list(server.STATES))
        self.assertIn("'%s'" % server.CONSENT_VERSION, js)


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
