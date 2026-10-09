// Sorgente da sensore: Web Serial (Chrome/Edge su computer, solo https o localhost; serve un gesto dell'utente).
// Assunzione ereditata dal Python (sources.parse_line): una riga ASCII per campione, "512" oppure "512,498,...".
// NON verificato sul firmware modificato dagli studenti (docs/08, sez. 6): per questo si MISURA tutto.

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
  constructor({ baud = 115200, column = 0, onData, onError, onClose } = {}) {
    this.baud = baud; this.column = column; this.onData = onData; this.onError = onError; this.onClose = onClose;
    this.port = null; this.reader = null; this.simulated = false; this.bad = 0; this.good = 0; this.running = false;
    this.lastLine = '';
  }
  get description() { return 'SENSORE seriale @ ' + this.baud + ' baud'; }
  // Va chiamata da un gesto dell'utente (click): il browser mostra l'elenco delle porte.
  async connect() {
    if (!serialSupported()) throw new Error('Questo browser non supporta la porta seriale: serve Chrome o Edge su computer.');
    this.port = await navigator.serial.requestPort();
    await this.port.open({ baudRate: this.baud });
    this.running = true;
    this._loop();
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
            const tMs = performance.now();
            buf += dec.decode(value, { stream: true });
            const lines = buf.split(/\r?\n/); buf = lines.pop();
            if (buf.length > 4096) buf = '';                     // niente righe: non e' testo
            const out = [];
            for (const l of lines) {
              const v = parseLine(l, this.column);
              if (v === null) { this.bad++; if (l.trim()) this.lastLine = l.slice(0, 40); } else { this.good++; out.push(v); }
            }
            if (out.length && this.onData) this.onData(Float32Array.from(out), tMs);
          }
        } finally { this.reader.releaseLock(); }
        if (!this.running) break;
      }
    } catch (e) { if (this.running && this.onError) this.onError(e); }
    this.running = false;
    if (this.onClose) this.onClose();
  }
  async close() {
    this.running = false;
    try { if (this.reader) await this.reader.cancel(); } catch (e) { /* gia' chiusa */ }
    try { if (this.port) await this.port.close(); } catch (e) { /* gia' chiusa */ }
  }
}
