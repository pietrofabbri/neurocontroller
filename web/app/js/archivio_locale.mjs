// Archivio nel browser: stesso contratto del server locale (web/05-talpa-w0.md, sez. 5), per quando la pagina
// e' pubblicata come sito statico e un server non c'e'. I dati restano nel browser di chi gioca (V-04):
// si perdono se si cancellano i dati del sito; il CSV serve da copia.

const CODE = /^P\d{2,3}$/;
const SOURCES = ['simulata', 'sensore'];
const STATES = ['rilassato', 'concentrato', 'neutro', 'artefatto'];
const TERRAINS = ['compatto', 'soffice'];
const COLS = ['t', 'depth_m', 'terrain', 'state', 'score_b', 'quality', 'tempo', 'brightness', 'density', 'register'];
const NUM = { duration_s: [0, 3600], depth_m: [0, 1e5], coherent_s: [0, 3600], incoherent_s: [0, 3600], neutral_s: [0, 3600],
  artifact_s: [0, 3600], quality_pct: [0, 100], score: [0, 1e7], gems: [0, 1e5], rocks_hit: [0, 1e5], seed: [0, 2 ** 53] };
const CSV_COLS = ['id', 'played_at', 'player_a', 'player_b', 'source', 'seed', 'duration_s', 'depth_m', 'gems', 'rocks_hit',
  'coherent_s', 'incoherent_s', 'neutral_s', 'artifact_s', 'quality_pct', 'score'];

const err = (m) => { const e = new Error(m); throw e; };

export class ArchivioLocale {
  constructor(storage, key = 'talpa.archivio.v1') { this.st = storage; this.key = key; this.mem = null; }
  _load() {
    if (this.mem) return this.mem;
    let d = null;
    try { d = JSON.parse(this.st.getItem(this.key) || 'null'); } catch (e) { d = null; }
    this.mem = d && Array.isArray(d.players) && Array.isArray(d.games) ? d : { players: [], games: [], next: 1 };
    return this.mem;
  }
  _save() {
    try { this.st.setItem(this.key, JSON.stringify(this.mem)); }
    catch (e) { err('memoria del browser piena: scarica il CSV e cancella qualche giocatore'); }
  }
  giocatori() { return this._load().players.map((p) => ({ code: p.code, created_at: p.created_at })); }
  nuovoGiocatore(code) {
    const d = this._load();
    if (code === undefined || code === null) {
      let n = 1; for (const p of d.players) { const m = /^P(\d+)$/.exec(p.code); if (m) n = Math.max(n, +m[1] + 1); }
      code = 'P' + (n < 10 ? '0' + n : String(n));
    }
    if (typeof code !== 'string' || !CODE.test(code)) err('serve un codice anonimo tipo P01 (niente nomi)');
    if (d.players.some((p) => p.code === code)) err('codice gia\' esistente');
    const p = { code, created_at: new Date().toISOString().slice(0, 19) + 'Z' };
    d.players.push(p); this._save(); return p;
  }
  cancellaGiocatore(code) {
    const d = this._load();
    if (!CODE.test(code || '') || !d.players.some((p) => p.code === code)) err('giocatore sconosciuto');
    d.players = d.players.filter((p) => p.code !== code);
    d.games = d.games.filter((g) => g.player_a !== code && g.player_b !== code);
    this._save(); return { deleted: code };
  }
  salvaPartita(g) {
    const d = this._load();
    if (!g || typeof g !== 'object') err('corpo non valido');
    for (const k of ['player_a', 'player_b']) {
      if (typeof g[k] !== 'string' || !CODE.test(g[k])) err('campo ' + k + ': serve un codice anonimo tipo P01');
      if (!d.players.some((p) => p.code === g[k])) err('giocatore ' + g[k] + ' sconosciuto');
    }
    if (!SOURCES.includes(g.source)) err("campo 'source' non valido");
    const row = { player_a: g.player_a, player_b: g.player_b, source: g.source };
    for (const [k, [lo, hi]] of Object.entries(NUM)) {
      const v = g[k];
      if (typeof v !== 'number' || !Number.isFinite(v) || v < lo || v > hi) err('campo ' + k + ' mancante o fuori intervallo');
      row[k] = v;
    }
    if (!Array.isArray(g.series) || g.series.length > 2000) err("'series' non valida");
    const series = g.series.map((s) => {
      if (!s || !TERRAINS.includes(s.terrain) || !STATES.includes(s.state)) err('riga di series non valida');
      return COLS.map((c) => { const v = s[c]; if (c === 'terrain' || c === 'state') return v; if (typeof v !== 'number' || !Number.isFinite(v)) err('riga di series non numerica'); return v; });
    });
    row.id = d.next++; row.played_at = new Date().toISOString().slice(0, 19) + 'Z'; row.series = series;
    d.games.push(row); this._save(); return row.id;
  }
  _plain(g) { const { series, ...r } = g; return r; }
  partite(player, limit = 50) {
    return this._load().games.filter((g) => !player || g.player_a === player || g.player_b === player)
      .sort((a, b) => b.id - a.id).slice(0, limit).map((g) => this._plain(g));
  }
  classifica(limit = 10) {
    return this._load().games.slice().sort((a, b) => b.score - a.score || a.id - b.id).slice(0, limit).map((g) => this._plain(g));
  }
  serie(id) {
    const g = this._load().games.find((x) => x.id === id);
    return g ? g.series.map((r) => Object.fromEntries(COLS.map((c, i) => [c, r[i]]))) : [];
  }
  csv() {
    const q = (v) => { v = String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
    const rows = this._load().games.slice().sort((a, b) => a.id - b.id).map((g) => CSV_COLS.map((c) => q(g[c])).join(','));
    return [CSV_COLS.join(',')].concat(rows).join('\n') + '\n';
  }
}
