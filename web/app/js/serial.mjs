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
  // protocollo 'chords' (binario, come il firmware provaBCI) oppure 'ascii' (una riga per campione)
  constructor({ protocol = 'chords', baud = 115200, channel = 0, channels = 6, onData, onError, onClose } = {}) {
    this.protocol = protocol; this.baud = baud; this.channel = channel; this.column = channel;
    this.onData = onData; this.onError = onError; this.onClose = onClose;
    this.port = null; this.reader = null; this.writer = null; this.simulated = false; this.running = false;
    this.bad = 0; this.good = 0; this.lastLine = ''; this.bytes = 0; this.board = null;
    this.parser = new ChordsParser(channels);
  }
  get description() { return 'SENSORE seriale @ ' + this.baud + ' baud (' + this.protocol + ')'; }
  get stats() { return { bytes: this.bytes, packets: this.parser.packets, lost: this.parser.lost, skipped: this.parser.skipped, text: this.parser.text, board: this.board }; }
  async send(text) {
    if (!this.port || !this.port.writable) return;
    if (!this.writer) this.writer = this.port.writable.getWriter();
    await this.writer.write(new TextEncoder().encode(text));
  }
  // Va chiamata da un gesto dell'utente (click): il browser mostra l'elenco delle porte.
  async connect() {
    if (!serialSupported()) throw new Error('Questo browser non supporta la porta seriale: serve Chrome o Edge su computer.');
    this.port = await navigator.serial.requestPort();
    await this.port.open({ baudRate: this.baud });
    this.running = true;
    this._loop();
    if (this.protocol === 'chords') {
      await new Promise((r) => setTimeout(r, 2200));            // l'Arduino si riavvia quando si apre la porta
      this.parser.text = '';
      await this.send('WHORU\n');
      await new Promise((r) => setTimeout(r, 700));
      const m = /([A-Z0-9-]{4,})/.exec(this.parser.text.replace(/\s+/g, ' ').toUpperCase());
      if (m && BOARDS[m[1]]) { this.board = m[1]; this.parser.channels = BOARDS[m[1]]; }
      await this.send('START\n');
    }
  }
  async _loop() {
    const dec = new TextDecoder('ascii'); let buf = '';
    try {
      while (this.running && this.port.readable) {
        this.reader = this.port.readable.getReader();
        try {
          for (;;) {
            const { value, done } = await this.reader.read();
            if (done) break;
            const tMs = performance.now(); this.bytes += value.length;
            if (this.protocol === 'chords') {
              const pk = this.parser.push(value);
              if (pk.length && this.onData) {
                const all = []; for (let c = 0; c < this.parser.channels; c++) all.push(Float32Array.from(pk, (p) => p.values[c]));
                this.good += pk.length;
                this.onData(all[Math.min(this.channel, all.length - 1)], tMs, all);
              }
              continue;
            }
            buf += dec.decode(value, { stream: true });
            const lines = buf.split(/\r?\n/); buf = lines.pop();
            if (buf.length > 4096) buf = '';
            const out = [];
            for (const l of lines) {
              const v = parseLine(l, this.column);
              if (v === null) { this.bad++; if (l.trim()) this.lastLine = l.slice(0, 40); } else { this.good++; out.push(v); }
            }
            if (out.length && this.onData) this.onData(Float32Array.from(out), tMs, [Float32Array.from(out)]);
          }
        } finally { this.reader.releaseLock(); }
        if (!this.running) break;
      }
    } catch (e) { if (this.running && this.onError) this.onError(e); }
    this.running = false;
    if (this.onClose) this.onClose();
  }
  async close() {
    try { if (this.protocol === 'chords') await this.send('STOP\n'); } catch (e) { /* porta gia' chiusa */ }
    this.running = false;
    try { if (this.writer) { this.writer.releaseLock(); this.writer = null; } } catch (e) { /* ok */ }
    try { if (this.reader) await this.reader.cancel(); } catch (e) { /* gia' chiusa */ }
    try { if (this.port) await this.port.close(); } catch (e) { /* gia' chiusa */ }
  }
}
