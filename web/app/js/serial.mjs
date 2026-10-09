// Sorgente da sensore: Web Serial (Chrome/Edge su computer, solo https o localhost; serve un gesto dell'utente).
// Protocollo principale: 'chords' = pacchetti binari del firmware provaBCI (vedi chords.mjs). Il protocollo
// 'ascii' (una riga per campione, come il Python sources.parse_line) resta come alternativa.
// Si MISURA tutto (frequenza, pacchetti persi, canali): nulla e' dato per scontato.

import { ChordsParser, BOARDS } from './chords.mjs';

const SPLIT = /[,;\t ]+/;

// Stessa regola di neurocontroller/sources.py: parse_line. Restituisce un numero o null.
export function parseLine(text, column = 0) {
  const t = text.replace(/[^\x00-\x7f]/g, '').trim();
  if (!t) return null;
  const parts = t.split(SPLIT).filter((p) => p.length);
  if (column >= parts.length) return null;
  const s = parts[column];
  // float() di Python accetta "512", "-3.5", "1e3", " inf", "nan": qui solo numeri finiti
  if (!/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(s)) return null;
  const v = Number(s);
  return Number.isFinite(v) ? v : null;
}

export const serialSupported = () => typeof navigator !== 'undefined' && 'serial' in navigator;

// Stima della frequenza di campionamento dai tempi di arrivo (orologio monotono), come "neurocontroller check".
export class RateMeter {
  constructor() { this.t0 = null; this.t1 = null; this.n = 0; }
  // il primo blocco fissa il tempo zero e non conta: restano n campioni su (t1 - t0)
  add(count, tMs) { if (this.t0 === null) { this.t0 = tMs; return; } this.t1 = tMs; this.n += count; }
  get fs() { return this.t1 !== null && this.t1 > this.t0 ? this.n / ((this.t1 - this.t0) / 1000) : 0; }
}

export class SerialSource {
  // protocol: 'auto' (prova 9600 e 115200, riconosce da solo il formato), 'chords' (pacchetti binari del firmware
  // provaBCI, 115200) oppure 'ascii' (una riga di testo per campione, come il Python sources.parse_line).
  constructor({ protocol = 'auto', baud = 0, channel = 0, channels = 6, onData, onError, onClose } = {}) {
    this.protocol = protocol; this.baud = baud || (protocol === 'chords' ? 115200 : 9600); this.fixedBaud = baud;
    this.channel = channel; this.channels = channels;
    this.onData = onData; this.onError = onError; this.onClose = onClose;
    this.port = null; this.reader = null; this.writer = null; this.simulated = false; this.running = false; this.loopP = null;
    this.bad = 0; this.good = 0; this.lastLine = ''; this.bytes = 0; this.board = null; this.tried = [];
    this._fresh();
  }
  _fresh() { this.parser = new ChordsParser(this.channels); this.abuf = ''; this.aGood = 0; this.aBad = 0; this.dec = new TextDecoder('ascii'); }
  get description() { return 'SENSORE seriale @ ' + this.baud + ' baud (' + this.protocol + ')'; }
  get stats() { return { bytes: this.bytes, packets: this.parser.packets, lost: this.parser.lost, skipped: this.parser.skipped, text: this.parser.text, board: this.board, protocol: this.protocol, baud: this.baud, tried: this.tried }; }
  async send(text) {
    if (!this.port || !this.port.writable) return;
    if (!this.writer) this.writer = this.port.writable.getWriter();
    await this.writer.write(new TextEncoder().encode(text));
  }
  async _open(baud) {
    this._fresh(); this.baud = baud; this.bytes = 0;
    await this.port.open({ baudRate: baud });
    this.running = true; this.loopP = this._loop();
  }
  async _shut() {
    this.running = false;
    try { if (this.writer) { this.writer.releaseLock(); this.writer = null; } } catch (e) { /* ok */ }
    try { if (this.reader) await this.reader.cancel(); } catch (e) { /* gia' chiusa */ }
    try { if (this.loopP) await this.loopP; } catch (e) { /* ok */ }
    try { if (this.port) await this.port.close(); } catch (e) { /* gia' chiusa */ }
  }
  // Va chiamata da un gesto dell'utente (click): il browser mostra l'elenco delle porte.
  async connect() {
    if (!serialSupported()) throw new Error('Questo browser non supporta la porta seriale: serve Chrome o Edge su computer.');
    this.port = await navigator.serial.requestPort();
    const bauds = this.fixedBaud ? [this.fixedBaud] : (this.protocol === 'chords' ? [115200] : [9600, 115200]);
    const want = this.protocol;
    for (let k = 0; k < bauds.length; k++) {
      this.protocol = 'auto'; await this._open(bauds[k]);
      await new Promise((r) => setTimeout(r, 2200));                 // l'Arduino si riavvia quando si apre la porta
      this.parser.text = '';
      if (want !== 'ascii') { await this.send('WHORU\n'); await new Promise((r) => setTimeout(r, 600)); }
      const m = /([A-Z0-9-]{4,})/.exec(this.parser.text.replace(/\s+/g, ' ').toUpperCase());
      if (m && BOARDS[m[1]]) { this.board = m[1]; this.parser.channels = BOARDS[m[1]]; }
      if (want !== 'ascii') await this.send('START\n');
      await new Promise((r) => setTimeout(r, 1800));
      const kind = this.parser.packets >= 3 ? 'chords' : (this.aGood >= 10 && this.aGood >= 4 * this.aBad ? 'ascii' : null);
      this.tried.push(bauds[k] + ' baud: ' + this.bytes + ' byte, ' + this.parser.packets + ' pacchetti, ' + this.aGood + ' righe numeriche');
      if (kind && (want === 'auto' || want === kind)) { this.protocol = kind; return; }
      if (k < bauds.length - 1) await this._shut();
    }
    this.protocol = want === 'auto' ? 'chords' : want;                 // nessun formato riconosciuto: la pagina mostra la diagnosi
  }
  async _loop() {
    try {
      while (this.running && this.port.readable) {
        this.reader = this.port.readable.getReader();
        try {
          for (;;) {
            const { value, done } = await this.reader.read();
            if (done) break;
            const tMs = performance.now(); this.bytes += value.length;
            const pk = this.parser.push(value);
            this.abuf += this.dec.decode(value, { stream: true });
            const lines = this.abuf.split(/\r?\n/); this.abuf = lines.pop(); if (this.abuf.length > 4096) this.abuf = '';
            const out = [];
            for (const l of lines) {
              const v = parseLine(l, this.channel);
              if (v === null) { this.aBad++; if (l.trim() && this.protocol === 'ascii') { this.bad++; this.lastLine = l.slice(0, 40); } }
              else { this.aGood++; out.push(v); }
            }
            if (this.protocol === 'chords' && pk.length && this.onData) {
              const all = []; for (let c = 0; c < this.parser.channels; c++) all.push(Float32Array.from(pk, (p) => p.values[c]));
              this.good += pk.length; this.onData(all[Math.min(this.channel, all.length - 1)], tMs, all);
            } else if (this.protocol === 'ascii' && out.length && this.onData) {
              this.good += out.length; this.onData(Float32Array.from(out), tMs, [Float32Array.from(out)]);
            }
          }
        } finally { try { this.reader.releaseLock(); } catch (e) { /* ok */ } }
        if (!this.running) break;
      }
    } catch (e) { if (this.running && this.onError) this.onError(e); }
    const wasRunning = this.running; this.running = false;
    if (wasRunning && this.onClose) this.onClose();
  }
  async close() {
    try { if (this.protocol === 'chords') await this.send('STOP\n'); } catch (e) { /* porta gia' chiusa */ }
    await this._shut();
  }
}
