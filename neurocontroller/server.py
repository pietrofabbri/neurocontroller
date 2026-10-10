"""Server locale per la web app (cartella `web/app/`): file statici + API JSON su SQLite.

Solo libreria standard. Pensato per girare **sul computer che si usa per giocare**:

  - ascolta solo su 127.0.0.1 (di default), quindi i dati non sono raggiungibili dalla rete;
  - il database e' un file SQLite nella cartella `data/web/`, ignorata da Git
    (`.gitignore`, `docs/05-sicurezza-privacy-etica.md`);
  - le persone sono codici anonimi `P01`, `P02`... (niente nomi, come nel resto del progetto);
  - ogni persona puo' essere cancellata con tutte le sue partite (`DELETE /api/players/<codice>`);
  - `localhost` e' un "indirizzo sicuro" per il browser: serve alla lettura USB del sensore.

Le API sono volutamente piccole; lo schema e' in `SCHEMA` (versione in `PRAGMA user_version`).

Schema v2 (10/10/2026): scheda del partecipante (eta', genere, mano, esperienza di giochi e di musica,
consenso), condizioni di B nella singola partita (sonno, caffe', stanchezza), metadati tecnici del segnale e
del profilo, dettaglio dei disturbi, 3 cursori della musica. Dizionario completo dei dati: `web/06-dati-ricerca.md`.
Un test controlla che ogni colonna sia descritta li'. Non si raccolgono dati sanitari ne' nomi.
"""
from __future__ import annotations

import csv
import datetime
import io
import json
import mimetypes
import re
import shutil
import sqlite3
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

SCHEMA_VERSION = 2
CODE_PATTERN = re.compile(r"^P\d{2,3}$")
MAX_BODY = 2 * 1024 * 1024
MAX_SERIES_ROWS = 2000
SOURCES = ("simulata", "sensore")
STATES = ("rilassato", "concentrato", "neutro", "artefatto")
TERRAINS = ("soffice", "morbido", "medio", "duro", "compatto")
REASONS = ("", "ampiezza", "alta_freq", "entrambi", "vicino_soglia")
SENSOR_FORMATS = ("ascii", "chords")
# Scheda del partecipante: solo risposte a scelta (niente testo libero, per non far entrare nomi o dati sanitari).
PLAYER_CHOICES = {
    "gender": ("donna", "uomo", "altro", "nd"),
    "handedness": ("destra", "sinistra", "ambidestra", "nd"),
    "gaming": ("mai", "1-3h", "4-10h", "oltre10h", "nd"),            # ore a settimana di videogiochi
    "music_training": ("nessuna", "meno2", "2-5", "oltre5", "nd"),    # anni di studio di uno strumento
    "education": ("medie", "superiori", "universita", "lavoro", "altro", "nd"),
    "consent_by": ("persona", "genitore_tutore"),
}
CONSENT_VERSION = "2026-10-10"

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    code            TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    age_years       INTEGER CHECK (age_years IS NULL OR age_years BETWEEN 5 AND 99),
    gender          TEXT CHECK (gender IS NULL OR gender IN ('donna','uomo','altro','nd')),
    handedness      TEXT CHECK (handedness IS NULL OR handedness IN ('destra','sinistra','ambidestra','nd')),
    gaming          TEXT CHECK (gaming IS NULL OR gaming IN ('mai','1-3h','4-10h','oltre10h','nd')),
    music_training  TEXT CHECK (music_training IS NULL OR music_training IN ('nessuna','meno2','2-5','oltre5','nd')),
    education       TEXT CHECK (education IS NULL OR education IN ('medie','superiori','universita','lavoro','altro','nd')),
    consent         INTEGER NOT NULL DEFAULT 0 CHECK (consent IN (0,1)),
    consent_by      TEXT CHECK (consent_by IS NULL OR consent_by IN ('persona','genitore_tutore')),
    consent_at      TEXT,
    consent_version TEXT
);
CREATE TABLE IF NOT EXISTS games (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    played_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    player_a         TEXT NOT NULL REFERENCES players(code) ON DELETE CASCADE,
    player_b         TEXT NOT NULL REFERENCES players(code) ON DELETE CASCADE,
    source           TEXT NOT NULL CHECK (source IN ('simulata','sensore')),
    seed             INTEGER NOT NULL,
    duration_s       REAL NOT NULL,
    depth_m          REAL NOT NULL,
    gems             INTEGER NOT NULL,
    rocks_hit        INTEGER NOT NULL,
    coherent_s       REAL NOT NULL,
    incoherent_s     REAL NOT NULL,
    neutral_s        REAL NOT NULL,
    artifact_s       REAL NOT NULL,
    quality_pct      REAL NOT NULL,
    score            REAL NOT NULL,
    app_version      TEXT,
    duration_planned_s REAL,
    coherence_mean   REAL,
    turbo_s          REAL,
    dubious_s        REAL,
    artifact_amp_s   REAL,
    artifact_hf_s    REAL,
    terrain_changes  INTEGER,
    tempo_mean       REAL,
    density_mean     REAL,
    softness_mean    REAL,
    percussion_pct   REAL,
    signal_fs_hz     REAL,
    sensor_format    TEXT,
    sensor_baud      INTEGER,
    profile_level    TEXT,
    profile_dprime   REAL,
    profile_accuracy REAL,
    calib_protocol   TEXT,
    b_sleep_h        REAL,
    b_caffeine_3h    INTEGER,
    b_fatigue        INTEGER
);
CREATE INDEX IF NOT EXISTS games_a ON games(player_a);
CREATE INDEX IF NOT EXISTS games_b ON games(player_b);
CREATE TABLE IF NOT EXISTS game_series (
    game_id     INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    t           REAL NOT NULL,
    depth_m     REAL NOT NULL,
    terrain     TEXT NOT NULL,
    state       TEXT NOT NULL,
    score_b     REAL NOT NULL,
    quality     REAL NOT NULL,
    coherence   REAL NOT NULL DEFAULT 0,
    tempo       REAL NOT NULL,
    density     REAL NOT NULL,
    softness    REAL NOT NULL,
    reason      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS series_game ON game_series(game_id);
"""

# Colonne aggiunte dalla v2 a tabelle che esistevano nella v1 (per la migrazione).
_V2_PLAYER_COLS = ("age_years INTEGER", "gender TEXT", "handedness TEXT", "gaming TEXT", "music_training TEXT",
                   "education TEXT", "consent INTEGER NOT NULL DEFAULT 0", "consent_by TEXT", "consent_at TEXT",
                   "consent_version TEXT")
_V2_GAME_COLS = ("app_version TEXT", "duration_planned_s REAL", "coherence_mean REAL", "turbo_s REAL", "dubious_s REAL",
                 "artifact_amp_s REAL", "artifact_hf_s REAL", "terrain_changes INTEGER", "tempo_mean REAL",
                 "density_mean REAL", "softness_mean REAL", "percussion_pct REAL", "signal_fs_hz REAL",
                 "sensor_format TEXT", "sensor_baud INTEGER", "profile_level TEXT", "profile_dprime REAL",
                 "profile_accuracy REAL", "calib_protocol TEXT", "b_sleep_h REAL", "b_caffeine_3h INTEGER",
                 "b_fatigue INTEGER")


def _migrate_v1_to_v2(c: sqlite3.Connection) -> None:
    """Porta un database v1 (4 cursori, terreni a 2 livelli) alla v2 senza perdere le partite."""
    for col in _V2_PLAYER_COLS:
        c.execute("ALTER TABLE players ADD COLUMN %s" % col)
    for col in _V2_GAME_COLS:
        c.execute("ALTER TABLE games ADD COLUMN %s" % col)
    c.execute("ALTER TABLE game_series RENAME TO game_series_v1")
    c.execute("DROP INDEX IF EXISTS series_game")
    c.executescript(SCHEMA)          # crea la nuova game_series (le altre tabelle esistono gia')
    # morbidezza = 1 - luminosita' (il v1 aveva 'chiaro'); il cursore 'registro' non esiste piu'
    c.execute("INSERT INTO game_series(game_id,t,depth_m,terrain,state,score_b,quality,coherence,tempo,density,softness,reason)"
              " SELECT game_id,t,depth_m,terrain,state,score_b,quality,0,tempo,density,1.0-brightness,'' FROM game_series_v1")
    c.execute("DROP TABLE game_series_v1")


SERIES_COLUMNS = ("t", "depth_m", "terrain", "state", "score_b", "quality", "coherence",
                  "tempo", "density", "softness", "reason")
GAME_NUMERIC = {  # campo -> (minimo, massimo)
    "duration_s": (0, 3600), "depth_m": (0, 100000), "coherent_s": (0, 3600),
    "incoherent_s": (0, 3600), "neutral_s": (0, 3600), "artifact_s": (0, 3600),
    "quality_pct": (0, 100), "score": (0, 1e7),
}
GAME_INTEGERS = {"gems": (0, 100000), "rocks_hit": (0, 100000), "seed": (0, 2 ** 53)}
# Campi facoltativi della partita (NULL se mancano): metadati tecnici, musica, condizioni di B.
GAME_OPTIONAL_NUMERIC = {
    "duration_planned_s": (0, 3600), "coherence_mean": (0, 1), "turbo_s": (0, 3600), "dubious_s": (0, 3600),
    "artifact_amp_s": (0, 3600), "artifact_hf_s": (0, 3600), "tempo_mean": (0, 300), "density_mean": (0, 1),
    "softness_mean": (0, 1), "percussion_pct": (0, 100), "signal_fs_hz": (0, 100000), "profile_dprime": (-100, 100),
    "profile_accuracy": (0, 1), "b_sleep_h": (0, 24),
}
GAME_OPTIONAL_INTEGERS = {"terrain_changes": (0, 100000), "sensor_baud": (0, 10000000), "b_caffeine_3h": (0, 1),
                          "b_fatigue": (1, 5)}
GAME_OPTIONAL_TEXT = {"app_version": 32, "calib_protocol": 32, "profile_level": 16}
PROFILE_LEVELS = ("affidabile", "debole", "non affidabile")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# --------------------------------------------------------------------------------------
# Archivio
# --------------------------------------------------------------------------------------

class Store:
    """Accesso al database. Una connessione per chiamata (SQLite e' leggero e cosi' e' thread-safe)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._memory: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        self.migrated_from: Optional[int] = None
        with self._tx() as c:
            version = c.execute("PRAGMA user_version").fetchone()[0]
            exists = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='games'").fetchone()
            if exists and version < 2:
                if str(path) != ":memory:":           # copia di sicurezza prima di toccare lo schema
                    shutil.copy2(str(self.path), str(self.path) + ".v%d.bak" % version)
                _migrate_v1_to_v2(c)
                self.migrated_from = version
            else:
                c.executescript(SCHEMA)
            c.execute("PRAGMA user_version = %d" % SCHEMA_VERSION)

    def _conn(self) -> sqlite3.Connection:
        if str(self.path) == ":memory:":
            if self._memory is None:
                self._memory = sqlite3.connect(":memory:", check_same_thread=False)
            conn = self._memory
        else:
            conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _tx(self):
        conn = self._conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if conn is not self._memory:
                conn.close()

    # ---- giocatori ----
    _PLAYER_FIELDS = ("code", "created_at", "age_years", "gender", "handedness", "gaming", "music_training",
                      "education", "consent", "consent_by", "consent_at", "consent_version")

    def list_players(self) -> List[Dict[str, Any]]:
        with self._lock, self._tx() as c:
            rows = c.execute(
                "SELECT p.*,"
                " (SELECT COUNT(*) FROM games g WHERE g.player_a = p.code OR g.player_b = p.code) AS games,"
                " (SELECT MAX(score) FROM games g WHERE g.player_a = p.code OR g.player_b = p.code) AS best_score"
                " FROM players p ORDER BY p.code").fetchall()
        return [dict(r) for r in rows]

    def create_player(self, code: Optional[str] = None) -> Dict[str, Any]:
        with self._lock, self._tx() as c:
            if code is None:
                used = {int(r[0][1:]) for r in c.execute("SELECT code FROM players")}
                n = 1
                while n in used:
                    n += 1
                code = "P%02d" % n
            elif not CODE_PATTERN.match(code):
                raise ApiError(400, "codice non ammesso: usare un codice anonimo tipo P01, P02... "
                                    "(niente nomi di persone)")
            if c.execute("SELECT 1 FROM players WHERE code = ?", (code,)).fetchone():
                raise ApiError(409, "il codice %s esiste gia'" % code)
            c.execute("INSERT INTO players(code) VALUES (?)", (code,))
            row = c.execute("SELECT * FROM players WHERE code = ?", (code,)).fetchone()
        return dict(row)

    def update_player(self, code: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Aggiorna la scheda del partecipante. Il consenso e' esplicito: serve chi lo da' (persona o genitore/tutore)."""
        fields = _validate_player(data)
        with self._lock, self._tx() as c:
            if not c.execute("SELECT 1 FROM players WHERE code = ?", (code,)).fetchone():
                raise ApiError(404, "giocatore sconosciuto")
            if fields:
                cols = list(fields)
                c.execute("UPDATE players SET %s WHERE code = ?" % ",".join("%s = ?" % k for k in cols),
                          [fields[k] for k in cols] + [code])
            row = c.execute("SELECT * FROM players WHERE code = ?", (code,)).fetchone()
        return dict(row)

    def delete_player(self, code: str) -> int:
        with self._lock, self._tx() as c:
            cur = c.execute("DELETE FROM players WHERE code = ?", (code,))
            return cur.rowcount

    # ---- partite ----
    def add_game(self, data: Dict[str, Any]) -> int:
        game = _validate_game(data)
        series = _validate_series(data.get("series", []))
        with self._lock, self._tx() as c:
            for key in ("player_a", "player_b"):
                row = c.execute("SELECT consent FROM players WHERE code = ?", (game[key],)).fetchone()
                if not row:
                    raise ApiError(404, "giocatore %s sconosciuto" % game[key])
                # con il sensore vero si registrano dati fisiologici: serve il consenso di tutti e due (o di chi ne ha la responsabilita')
                if game["source"] == "sensore" and not row[0]:
                    raise ApiError(409, "manca il consenso di %s: compilare la scheda del partecipante" % game[key])
            cols = list(game)
            cur = c.execute("INSERT INTO games(%s) VALUES (%s)" % (",".join(cols), ",".join("?" * len(cols))),
                            [game[k] for k in cols])
            gid = cur.lastrowid
            c.executemany(
                "INSERT INTO game_series(game_id,%s) VALUES (?,%s)" % (",".join(SERIES_COLUMNS), ",".join("?" * len(SERIES_COLUMNS))),
                [(gid,) + row for row in series])
        return int(gid)

    def list_games(self, player: Optional[str], limit: int) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM games"
        args: List[Any] = []
        if player:
            sql += " WHERE player_a = ? OR player_b = ?"
            args += [player, player]
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._lock, self._tx() as c:
            return [dict(r) for r in c.execute(sql, args).fetchall()]

    def series(self, game_id: int) -> List[Dict[str, Any]]:
        with self._lock, self._tx() as c:
            rows = c.execute("SELECT * FROM game_series WHERE game_id = ? ORDER BY t", (game_id,)).fetchall()
        return [{k: r[k] for k in r.keys() if k != "game_id"} for r in rows]

    def leaderboard(self, limit: int) -> List[Dict[str, Any]]:
        with self._lock, self._tx() as c:
            rows = c.execute("SELECT id, played_at, player_a, player_b, source, depth_m, gems, score"
                             " FROM games ORDER BY score DESC, id ASC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def games_csv(self) -> str:
        """Una riga per partita, con la scheda anonima di A e di B (prefissi a_ e b_). Solo codici, mai nomi."""
        prof = [k for k in self._PLAYER_FIELDS if k not in ("code", "created_at")]
        sel = ["g.*"] + ["pa.%s AS a_%s" % (k, k) for k in prof] + ["pb.%s AS b_%s" % (k, k) for k in prof]
        sql = ("SELECT %s FROM games g JOIN players pa ON pa.code = g.player_a JOIN players pb ON pb.code = g.player_b"
               " ORDER BY g.id" % ", ".join(sel))
        return self._csv(sql)

    def series_csv(self) -> str:
        return self._csv("SELECT * FROM game_series ORDER BY game_id, t")

    def _csv(self, sql: str) -> str:
        with self._lock, self._tx() as c:
            cur = c.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        for r in rows:
            w.writerow([r[k] for k in cols])
        return buf.getvalue()


def _num(data: Dict[str, Any], key: str, lo: float, hi: float) -> float:
    v = data.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
        raise ApiError(400, "campo %r mancante o non numerico" % key)
    if not lo <= v <= hi:
        raise ApiError(400, "campo %r fuori intervallo [%s, %s]" % (key, lo, hi))
    return float(v)


def _validate_player(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ApiError(400, "corpo non valido")
    allowed = {"age_years", "consent"} | set(PLAYER_CHOICES)
    unknown = set(data) - allowed
    if unknown:
        raise ApiError(400, "campi non ammessi: %s" % ", ".join(sorted(unknown)))
    out: Dict[str, Any] = {}
    if "age_years" in data:
        v = data["age_years"]
        if v is not None:
            if isinstance(v, bool) or not isinstance(v, int) or not 5 <= v <= 99:
                raise ApiError(400, "age_years: intero tra 5 e 99")
        out["age_years"] = v
    for key, choices in PLAYER_CHOICES.items():
        if key in data:
            v = data[key]
            if v is not None and v not in choices:
                raise ApiError(400, "campo %r: uno tra %s" % (key, ", ".join(choices)))
            out[key] = v
    if "consent" in data:
        v = data["consent"]
        if v not in (0, 1, True, False):
            raise ApiError(400, "consent: 0 o 1")
        out["consent"] = 1 if v else 0
        if out["consent"]:
            if data.get("consent_by") not in PLAYER_CHOICES["consent_by"]:
                raise ApiError(400, "consent_by: indicare chi da il consenso (persona o genitore_tutore)")
            out["consent_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            out["consent_version"] = CONSENT_VERSION
        else:      # consenso ritirato
            out["consent_by"] = None
            out["consent_at"] = None
            out["consent_version"] = None
    return out


def _validate_game(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ApiError(400, "corpo non valido")
    game: Dict[str, Any] = {}
    for key in ("player_a", "player_b"):
        v = data.get(key)
        if not isinstance(v, str) or not CODE_PATTERN.match(v):
            raise ApiError(400, "campo %r: serve un codice anonimo tipo P01" % key)
        game[key] = v
    if data.get("source") not in SOURCES:
        raise ApiError(400, "campo 'source' deve essere uno tra %s" % ", ".join(SOURCES))
    game["source"] = data["source"]
    for key, (lo, hi) in GAME_INTEGERS.items():
        game[key] = int(_num(data, key, lo, hi))
    for key, (lo, hi) in GAME_NUMERIC.items():
        game[key] = _num(data, key, lo, hi)
    for key, (lo, hi) in GAME_OPTIONAL_NUMERIC.items():
        if data.get(key) is not None:
            game[key] = _num(data, key, lo, hi)
    for key, (lo, hi) in GAME_OPTIONAL_INTEGERS.items():
        if data.get(key) is not None:
            game[key] = int(_num(data, key, lo, hi))
    for key, maxlen in GAME_OPTIONAL_TEXT.items():
        v = data.get(key)
        if v is not None:
            if not isinstance(v, str) or not v or len(v) > maxlen or not re.match(r"^[A-Za-z0-9 ._\-]+$", v):
                raise ApiError(400, "campo %r: testo breve (lettere, numeri, punto, trattino)" % key)
            game[key] = v
    if game.get("profile_level") is not None and game["profile_level"] not in PROFILE_LEVELS:
        raise ApiError(400, "profile_level: uno tra %s" % ", ".join(PROFILE_LEVELS))
    fmt = data.get("sensor_format")
    if fmt is not None:
        if fmt not in SENSOR_FORMATS:
            raise ApiError(400, "sensor_format: uno tra %s" % ", ".join(SENSOR_FORMATS))
        game["sensor_format"] = fmt
    return game


def _validate_series(series: Any) -> List[Tuple[Any, ...]]:
    if not isinstance(series, list) or len(series) > MAX_SERIES_ROWS:
        raise ApiError(400, "'series' deve essere una lista di al piu' %d righe" % MAX_SERIES_ROWS)
    rows: List[Tuple[Any, ...]] = []
    for item in series:
        if not isinstance(item, dict):
            raise ApiError(400, "riga di 'series' non valida")
        if item.get("terrain") not in TERRAINS or item.get("state") not in STATES:
            raise ApiError(400, "riga di 'series': terreno o stato non riconosciuto")
        if item.get("reason", "") not in REASONS:
            raise ApiError(400, "riga di 'series': motivo dello scarto non riconosciuto")
        row: List[Any] = []
        for col in SERIES_COLUMNS:
            if col in ("terrain", "state"):
                row.append(item[col])
            elif col == "reason":
                row.append(item.get("reason", ""))
            elif col == "coherence":
                row.append(_num({"coherence": item.get("coherence", 0)}, "coherence", 0, 1))
            else:
                row.append(_num(item, col, -1e6, 1e6))
        rows.append(tuple(row))
    return rows


# --------------------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------------------

def _make_handler(store: Store, static_dir: Path, allowed_hosts: Tuple[str, ...]):
    static_root = Path(static_dir).resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "neurocontroller"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # silenzioso: niente dati nei log
            pass

        # ---- utilita' ----
        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").strip().lower()
            name = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
            return name in allowed_hosts

        def _send(self, status: int, body: bytes, ctype: str, extra: Optional[Dict[str, str]] = None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, payload: Any):
            self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _body(self) -> Dict[str, Any]:
            ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if ctype != "application/json":
                raise ApiError(415, "serve Content-Type: application/json")
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError(400, "Content-Length non valido")
            if length > MAX_BODY:
                raise ApiError(413, "corpo troppo grande")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                raise ApiError(400, "JSON non valido")
            if not isinstance(data, dict):
                raise ApiError(400, "il corpo deve essere un oggetto JSON")
            return data

        def _dispatch(self, method: str):
            try:
                if not self._host_ok():
                    raise ApiError(403, "host non ammesso")
                url = urlparse(self.path)
                path = unquote(url.path)
                if path.startswith("/api/"):
                    self._api(method, path, parse_qs(url.query))
                elif method in ("GET", "HEAD"):
                    self._static(path)
                else:
                    raise ApiError(405, "metodo non ammesso")
            except ApiError as exc:
                self._json(exc.status, {"error": exc.message})
            except Exception:  # errore nostro: non svelare dettagli
                self._json(500, {"error": "errore interno"})

        # ---- API ----
        def _api(self, method: str, path: str, query: Dict[str, List[str]]):
            parts = [p for p in path.split("/") if p][1:]  # senza "api"
            if parts == ["health"] and method == "GET":
                return self._json(200, {"ok": True, "schema": SCHEMA_VERSION})
            if parts == ["players"]:
                if method == "GET":
                    return self._json(200, {"players": store.list_players()})
                if method == "POST":
                    return self._json(201, store.create_player(self._body().get("code")))
            if len(parts) == 2 and parts[0] == "players" and method == "PUT":
                if not CODE_PATTERN.match(parts[1]):
                    raise ApiError(400, "codice non valido")
                return self._json(200, store.update_player(parts[1], self._body()))
            if len(parts) == 2 and parts[0] == "players" and method == "DELETE":
                if not CODE_PATTERN.match(parts[1]):
                    raise ApiError(400, "codice non valido")
                if not store.delete_player(parts[1]):
                    raise ApiError(404, "giocatore sconosciuto")
                return self._json(200, {"deleted": parts[1]})
            if parts == ["games"]:
                if method == "GET":
                    player = (query.get("player") or [None])[0]
                    if player is not None and not CODE_PATTERN.match(player):
                        raise ApiError(400, "codice non valido")
                    limit = _limit(query, 50)
                    return self._json(200, {"games": store.list_games(player, limit)})
                if method == "POST":
                    return self._json(201, {"id": store.add_game(self._body())})
            if len(parts) == 3 and parts[0] == "games" and parts[2] == "series" and method == "GET":
                if not parts[1].isdigit():
                    raise ApiError(400, "id non valido")
                return self._json(200, {"series": store.series(int(parts[1]))})
            if parts == ["leaderboard"] and method == "GET":
                return self._json(200, {"games": store.leaderboard(_limit(query, 10))})
            if parts == ["export.csv"] and method == "GET":
                return self._send(200, store.games_csv().encode("utf-8"), "text/csv; charset=utf-8",
                                  {"Content-Disposition": 'attachment; filename="partite.csv"'})
            if parts == ["export-series.csv"] and method == "GET":
                return self._send(200, store.series_csv().encode("utf-8"), "text/csv; charset=utf-8",
                                  {"Content-Disposition": 'attachment; filename="serie.csv"'})
            raise ApiError(404, "percorso sconosciuto")

        # ---- file statici ----
        def _static(self, path: str):
            rel = path.lstrip("/") or "index.html"
            target = (static_root / rel).resolve()
            if target.is_dir():
                target = target / "index.html"
            try:
                target.relative_to(static_root)
            except ValueError:
                raise ApiError(403, "percorso non ammesso")
            if not target.is_file():
                raise ApiError(404, "file non trovato")
            ctype = {".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
                     ".css": "text/css; charset=utf-8", ".html": "text/html; charset=utf-8",
                     ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml"}.get(
                target.suffix.lower()) or mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self._send(200, target.read_bytes(), ctype)

        def do_GET(self): self._dispatch("GET")
        def do_HEAD(self): self._dispatch("HEAD")
        def do_POST(self): self._dispatch("POST")
        def do_PUT(self): self._dispatch("PUT")
        def do_DELETE(self): self._dispatch("DELETE")

    return Handler


def _limit(query: Dict[str, List[str]], default: int) -> int:
    raw = (query.get("limit") or [str(default)])[0]
    if not raw.isdigit() or not 1 <= int(raw) <= 500:
        raise ApiError(400, "limit deve essere tra 1 e 500")
    return int(raw)


def make_server(db_path: Path, static_dir: Path, host: str = "127.0.0.1", port: int = 8765
                ) -> Tuple[ThreadingHTTPServer, Store]:
    store = Store(db_path)
    allowed = ("127.0.0.1", "localhost", "[::1]", host.lower())
    server = ThreadingHTTPServer((host, port), _make_handler(store, static_dir, allowed))
    server.daemon_threads = True
    return server, store
