// Archivio nel browser: stesso contratto del server locale (web/05-talpa-w0.md, sez. 5), per quando la pagina
// e' pubblicata come sito statico e un server non c'e'. I dati restano nel browser di chi gioca (V-04):
// si perdono se si cancellano i dati del sito; il CSV serve da copia.
// Le regole di validazione sono le stesse di neurocontroller/server.py (schema v2): se ne cambia una, si cambiano entrambe
// (un test controlla che i nomi dei campi coincidano). Dizionario dei dati: web/06-dati-ricerca.md.

const CODE = /^P\d{2,3}$/;
export const SOURCES = ['simulata', 'sensore'];
export const STATES = ['rilassato', 'concentrato', 'neutro', 'artefatto'];
export const TERRAINS = ['soffice', 'morbido', 'medio', 'duro', 'compatto'];
export const REASONS = ['', 'ampiezza', 'alta_freq', 'entrambi', 'vicino_soglia'];
export const SENSOR_FORMATS = ['ascii', 'chords'];
export const PROFILE_LEVELS = ['affidabile', 'debole', 'non affidabile'];
export const CONSENT_VERSION = '2026-10-10';
export const PLAYER_CHOICES = {
  gender: ['donna', 'uomo', 'altro', 'nd'],
  handedness: ['destra', 'sinistra', 'ambidestra', 'nd'],
  gaming: ['mai', '1-3h', '4-10h', 'oltre10h', 'nd'],
  music_training: ['nessuna', 'meno2', '2-5', 'oltre5', 'nd'],
  education: ['medie', 'superiori', 'universita', 'lavoro', 'altro', 'nd'],
  consent_by: ['persona', 'genitore_tutore'],
};
export const PLAYER_FIELDS = ['age_years', 'gender', 'handedness', 'gaming', 'music_training', 'education', 'consent', 'consent_by', 'consent_at', 'consent_version'];
export const SERIES_COLS = ['t', 'depth_m', 'terrain', 'state', 'score_b', 'quality', 'coherence', 'tempo', 'density', 'softness', 'reason'];
export const GAME_REQUIRED = { duration_s: [0, 3600], depth_m: [0, 1e5], coherent_s: [0, 3600], incoherent_s: [0, 3600], neutral_s: [0, 3600],
  artifact_s: [0, 3600], quality_pct: [0, 100], score: [0, 1e7], gems: [0, 1e5], rocks_hit: [0, 1e5], seed: [0, 2 ** 53] };
export const GAME_OPTIONAL = { duration_planned_s: [0, 3600], coherence_mean: [0, 1], turbo_s: [0, 3600], dubious_s: [0, 3600], artifact_amp_s: [0, 3600],
  artifact_hf_s: [0, 3600], tempo_mean: [0, 300], density_mean: [0, 1], softness_mean: [0, 1], percussion_pct: [0, 100], signal_fs_hz: [0, 1e5],
  profile_dprime: [-100, 100], profile_accuracy: [0, 1], b_sleep_h: [0, 24], terrain_changes: [0, 1e5], sensor_baud: [0, 1e7], b_caffeine_3h: [0, 1], b_fatigue: [1, 5] };
const OPTIONAL_INT = ['terrain_changes', 'sensor_baud', 'b_caffeine_3h', 'b_fatigue'];
const OPTIONAL_TEXT = { app_version: 32, calib_protocol: 32 };
export const GAME_COLS = ['id', 'played_at', 'player_a', 'player_b', 'source', 'seed', 'duration_s', 'depth_m', 'gems', 'rocks_hit', 'coherent_s',
  'incoherent_s', 'neutral_s', 'artifact_s', 'quality_pct', 'score', 'app_version', 'duration_planned_s', 'coherence_mean', 'turbo_s', 'dubious_s',
  'artifact_amp_s', 'artifact_hf_s', 'terrain_changes', 'tempo_mean', 'density_mean', 'softness_mean', 'percussion_pct', 'signal_fs_hz', 'sensor_format',
  'sensor_baud', 'profile_level', 'profile_dprime', 'profile_accuracy', 'calib_protocol', 'b_sleep_h', 'b_caffeine_3h', 'b_fatigue'];

const err = (m) => { const e = new Error(m); throw e; };
const ora = () => new Date().toISOString().slice(0, 19) + 'Z';
const q = (v) => { if (v === null || v === undefined) return ''; v = String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
const csvDi = (cols, righe) => [cols.join(',')].concat(righe.map((r) => cols.map((c) => q(r[c])).join(','))).join('\n') + '\n';

export class ArchivioLocale {
  constructor(storage, key = 'talpa.archivio.v2', keyV1 = 'talpa.archivio.v1') { this.st = storage; this.key = key; this.keyV1 = keyV1; this.mem = null; }
  _load() {
    if (this.mem) return this.mem;
    let d = null;
    try { d = JSON.parse(this.st.getItem(this.key) || 'null'); } catch (e) { d = null; }
    if (!(d && Array.isArray(d.players) && Array.isArray(d.games))) {
      let v1 = null;
      try { v1 = JSON.parse(this.st.getItem(this.keyV1) || 'null'); } catch (e) { v1 = null; }
      d = v1 && Array.isArray(v1.players) && Array.isArray(v1.games) ? this._daV1(v1) : { players: [], games: [], next: 1 };
    }
    this.mem = d;
    return d;
  }
  // v1: 4 cursori (con 'chiaro' e 'acuto') e terreni a 2 livelli; si converte senza perdere le partite.
  _daV1(v1) {
    const players = v1.players.map((p) => { const o = { code: p.code, created_at: p.created_at }; for (const f of PLAYER_FIELDS) o[f] = f === 'consent' ? 0 : null; return o; });
    const games = v1.games.map((g) => ({ ...g, series: (g.series || []).map((r) => [r[0], r[1], r[2], r[3], r[4], r[5], 0, r[6], r[8], Math.round((1 - r[7]) * 1000) / 1000, '']) }));
    return { players, games, next: v1.next || games.length + 1 };
  }
  _save() {
    try { this.st.setItem(this.key, JSON.stringify(this.mem)); }
    catch (e) { err('memoria del browser piena: scarica il CSV e cancella qualche giocatore'); }
  }
  giocatori() { return this._load().players.map((p) => ({ ...p })); }
  nuovoGiocatore(code) {
    const d = this._load();
    if (code === undefined || code === null) {
      let n = 1; for (const p of d.players) { const m = /^P(\d+)$/.exec(p.code); if (m) n = Math.max(n, +m[1] + 1); }
      code = 'P' + (n < 10 ? '0' + n : String(n));
    }
    if (typeof code !== 'string' || !CODE.test(code)) err('serve un codice anonimo tipo P01 (niente nomi)');
    if (d.players.some((p) => p.code === code)) err('codice gia\' esistente');
    const p = { code, created_at: ora() }; for (const f of PLAYER_FIELDS) p[f] = f === 'consent' ? 0 : null;
    d.players.push(p); this._save(); return { ...p };
  }
  // Scheda del partecipante: solo risposte a scelta. Il consenso dice anche chi lo da' (persona o genitore/tutore).
  aggiornaGiocatore(code, dati) {
    const d = this._load(), p = d.players.find((x) => x.code === code);
    if (!p) err('giocatore sconosciuto');
    if (!dati || typeof dati !== 'object') err('corpo non valido');
    const ammessi = new Set(['age_years', 'consent', ...Object.keys(PLAYER_CHOICES)]);
    for (const k of Object.keys(dati)) if (!ammessi.has(k)) err('campi non ammessi: ' + k);
    const out = {};
    if ('age_years' in dati) {
      const v = dati.age_years;
      if (v !== null && !(Number.isInteger(v) && v >= 5 && v <= 99)) err('age_years: intero tra 5 e 99');
      out.age_years = v;
    }
    for (const [k, ch] of Object.entries(PLAYER_CHOICES)) {
      if (k in dati) { const v = dati[k]; if (v !== null && !ch.includes(v)) err('campo ' + k + ': uno tra ' + ch.join(', ')); out[k] = v; }
    }
    if ('consent' in dati) {
      if (![0, 1, true, false].includes(dati.consent)) err('consent: 0 o 1');
      out.consent = dati.consent ? 1 : 0;
      if (out.consent) {
        if (!PLAYER_CHOICES.consent_by.includes(dati.consent_by)) err('consent_by: indicare chi da il consenso (persona o genitore_tutore)');
        out.consent_at = ora(); out.consent_version = CONSENT_VERSION;
      } else { out.consent_by = null; out.consent_at = null; out.consent_version = null; }
    }
    Object.assign(p, out); this._save(); return { ...p };
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
      const p = d.players.find((x) => x.code === g[k]);
      if (!p) err('giocatore ' + g[k] + ' sconosciuto');
      if (g.source === 'sensore' && !p.consent) err('manca il consenso di ' + g[k] + ': compilare la scheda del partecipante');
    }
    if (!SOURCES.includes(g.source)) err("campo 'source' non valido");
    const row = { player_a: g.player_a, player_b: g.player_b, source: g.source };
    for (const [k, [lo, hi]] of Object.entries(GAME_REQUIRED)) {
      const v = g[k];
      if (typeof v !== 'number' || !Number.isFinite(v) || v < lo || v > hi) err('campo ' + k + ' mancante o fuori intervallo');
      row[k] = v;
    }
    for (const [k, [lo, hi]] of Object.entries(GAME_OPTIONAL)) {
      const v = g[k];
      if (v === undefined || v === null) { row[k] = null; continue; }
      if (typeof v !== 'number' || !Number.isFinite(v) || v < lo || v > hi || (OPTIONAL_INT.includes(k) && !Number.isInteger(v))) err('campo ' + k + ' fuori intervallo');
      row[k] = v;
    }
    for (const [k, max] of Object.entries(OPTIONAL_TEXT)) {
      const v = g[k];
      if (v === undefined || v === null) { row[k] = null; continue; }
      if (typeof v !== 'string' || !v || v.length > max || !/^[A-Za-z0-9 ._-]+$/.test(v)) err('campo ' + k + ': testo breve');
      row[k] = v;
    }
    row.profile_level = g.profile_level == null ? null : g.profile_level;
    if (row.profile_level !== null && !PROFILE_LEVELS.includes(row.profile_level)) err('profile_level non valido');
    row.sensor_format = g.sensor_format == null ? null : g.sensor_format;
    if (row.sensor_format !== null && !SENSOR_FORMATS.includes(row.sensor_format)) err('sensor_format non valido');
    if (!Array.isArray(g.series) || g.series.length > 2000) err("'series' non valida");
    const series = g.series.map((s) => {
      if (!s || !TERRAINS.includes(s.terrain) || !STATES.includes(s.state)) err('riga di series non valida');
      if (!REASONS.includes(s.reason === undefined ? '' : s.reason)) err('motivo dello scarto non riconosciuto');
      return SERIES_COLS.map((c) => {
        if (c === 'terrain' || c === 'state') return s[c];
        if (c === 'reason') return s.reason === undefined ? '' : s.reason;
        const v = c === 'coherence' && s[c] === undefined ? 0 : s[c];
        if (typeof v !== 'number' || !Number.isFinite(v)) err('riga di series non numerica');
        return v;
      });
    });
    row.id = d.next++; row.played_at = ora(); row.series = series;
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
    return g ? g.series.map((r) => Object.fromEntries(SERIES_COLS.map((c, i) => [c, r[i]]))) : [];
  }
  // Una riga per partita, con la scheda anonima di A e di B (prefissi a_ e b_), come il server.
  csv() {
    const d = this._load(), prof = PLAYER_FIELDS;
    const cols = GAME_COLS.concat(prof.map((f) => 'a_' + f), prof.map((f) => 'b_' + f));
    const righe = d.games.slice().sort((a, b) => a.id - b.id).map((g) => {
      const r = { ...g }, pa = d.players.find((p) => p.code === g.player_a) || {}, pb = d.players.find((p) => p.code === g.player_b) || {};
      for (const f of prof) { r['a_' + f] = pa[f]; r['b_' + f] = pb[f]; }
      return r;
    });
    return csvDi(cols, righe);
  }
  csvSerie() {
    const righe = [];
    for (const g of this._load().games.slice().sort((a, b) => a.id - b.id)) for (const r of g.series) righe.push({ game_id: g.id, ...Object.fromEntries(SERIES_COLS.map((c, i) => [c, r[i]])) });
    return csvDi(['game_id'].concat(SERIES_COLS), righe);
  }
}
