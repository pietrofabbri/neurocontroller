// Motore musicale di A (R-04, R-05): l'unico canale da A verso B.
// Musica generata nel browser con Web Audio, scala pentatonica di La minore.
// Parametri (tutti 0..1 tranne tempo in BPM): tempo, luminosita, densita, registro, pulso.
// Gli effetti sullo stato di B sono IPOTESI da mettere alla prova (web/02-architettura.md, sez. 6).

export const TEMPO_MIN = 60, TEMPO_MAX = 140;
export const PRESET = {
  calmo:    { tempo: 62,  luminosita: 0.15, densita: 0.2,  registro: 0.2, pulso: 1 },
  neutro:   { tempo: 100, luminosita: 0.5,  densita: 0.5,  registro: 0.5, pulso: 1 },
  energico: { tempo: 136, luminosita: 0.9,  densita: 0.85, registro: 0.8, pulso: 1 },
};
const SCALE = [0, 3, 5, 7, 10];               // La minore pentatonica (semitoni dalla tonica)
const A2 = 110;

export const norm = (p) => ({ tempo: (p.tempo - TEMPO_MIN) / (TEMPO_MAX - TEMPO_MIN), luminosita: p.luminosita, densita: p.densita, registro: p.registro });

export class Music {
  constructor() { this.p = { ...PRESET.neutro }; this.ctx = null; this.running = false; this.step = 0; this.next = 0; this.timer = null; this.seed = 1; this.last = null; }
  set(partial) {
    const q = { ...this.p, ...partial };
    q.tempo = Math.min(TEMPO_MAX, Math.max(TEMPO_MIN, q.tempo));
    for (const k of ['luminosita', 'densita', 'registro']) q[k] = Math.min(1, Math.max(0, q[k]));
    this.p = q;
    if (this.filter && this.ctx) this.filter.frequency.setTargetAtTime(this._cutoff(), this.ctx.currentTime, 0.1);
  }
  _cutoff() { return 350 * Math.pow(14, this.p.luminosita); }          // 350 Hz ... ~5 kHz
  _rnd() { this.seed = (this.seed * 1664525 + 1013904223) >>> 0; return this.seed / 4294967296; }
  start(volume = 0.5) {
    if (this.running) return;
    const AC = globalThis.AudioContext || globalThis.webkitAudioContext;
    if (!AC) { this.available = false; return; }
    this.available = true;
    this.ctx = new AC();
    this.master = this.ctx.createGain(); this.master.gain.value = volume;
    this.filter = this.ctx.createBiquadFilter(); this.filter.type = 'lowpass'; this.filter.Q.value = 0.8;
    this.filter.frequency.value = this._cutoff();
    this.filter.connect(this.master); this.master.connect(this.ctx.destination);
    this.ctx.resume && this.ctx.resume();
    this.running = true; this.step = 0; this.next = this.ctx.currentTime + 0.1;
    this.timer = setInterval(() => this._schedule(), 25);
  }
  stop() {
    this.running = false; clearInterval(this.timer);
    if (this.ctx) { try { this.master.gain.setTargetAtTime(0, this.ctx.currentTime, 0.05); setTimeout(() => this.ctx && this.ctx.close(), 300); } catch (e) { /* gia' chiuso */ } }
  }
  setVolume(v) { if (this.master) this.master.gain.value = v; }
  _schedule() {
    const stepDur = 60 / this.p.tempo / 2;                           // crome
    while (this.next < this.ctx.currentTime + 0.12) {
      this._play(this.step, this.next, stepDur);
      this.next += stepDur; this.step++;
    }
  }
  _play(step, when, stepDur) {
    const p = this.p;
    if (p.pulso && step % 2 === 0) this._tone(A2 * (step % 8 === 0 ? 1 : 1.5), when, stepDur * 1.6, 0.16, 'sine');   // pulso regolare grave
    if (this._rnd() < 0.15 + 0.8 * p.densita) {
      const oct = Math.floor(p.registro * 2.99) + 1;                 // ottave sopra La2: 1..3
      const semi = SCALE[Math.floor(this._rnd() * SCALE.length)] + 12 * oct;
      const f = A2 * Math.pow(2, semi / 12);
      this.last = { f, when };
      this._tone(f, when, stepDur * (1.2 + 1.5 * (1 - p.densita)), 0.12, p.luminosita > 0.55 ? 'sawtooth' : 'triangle');
    }
  }
  _tone(f, when, dur, gain, type) {
    const o = this.ctx.createOscillator(), g = this.ctx.createGain();
    o.type = type; o.frequency.value = f;
    g.gain.setValueAtTime(0.0001, when);
    g.gain.exponentialRampToValueAtTime(gain, when + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    o.connect(g); g.connect(this.filter);
    o.start(when); o.stop(when + dur + 0.05);
  }
}
