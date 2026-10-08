// Sorgente simulata: porting di neurocontroller/sources.py (SimulatedSource) con una variabile
// mentale CONTINUA u in [0,1] (0 = rilassato, 1 = concentrato) al posto degli stati a scatti.
// NON e' EEG vero (V-10). Va a tempo reale se la si legge con l'orologio (vedi worker.js).

export const PERSONAS = {
  tipica: { name: 'tipica', reactivity: 0.85, alphaHz: 10.0, gain: 1.0, noise: 2.0, emgGain: 1.0 },
  debole: { name: 'debole', reactivity: 0.3, alphaHz: 10.6, gain: 1.0, noise: 2.0, emgGain: 1.0 },
  nulla: { name: 'nulla', reactivity: 0.0, alphaHz: 9.4, gain: 1.0, noise: 2.0, emgGain: 1.0 },
};
const NEUTRAL = { delta: 6, theta: 4, alpha: 6, beta: 4, gamma: 1 };
const RELAX = { delta: 5.5, theta: 4.5, alpha: 8.5, beta: 3, gamma: 0.8 };
const FOCUS = { delta: 5, theta: 4.5, alpha: 5, beta: 6.5, gamma: 1.4 };
const CENTERS = { delta: [1.8, 2.6, 3.4], theta: [4.8, 6, 7.2], alpha: [0, 0, 0], beta: [16, 21, 27], gamma: [32.5, 36, 39.5] };
const MOD_DEPTH = 0.9;

export function makeRng(seed) {                      // mulberry32 + Box-Muller
  let a = (seed >>> 0) || 1;
  const uni = () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  return { uni, gauss() { const u = Math.max(uni(), 1e-12), v = uni(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); } };
}

export class SimulatedSource {
  constructor({ fs = 250, persona = 'tipica', seed = 1 } = {}) {
    this.fs = fs; this.persona = PERSONAS[persona]; this.rng = makeRng(seed);
    this.simulated = true;
    this.description = 'SIMULATO (persona ' + this.persona.name + '): segnale sintetico, non EEG';
    this.u = 0.5; this.jawLeft = 0; this.i = 0;
    this.phase = {}; this.freq = {};
    for (const [band, cs] of Object.entries(CENTERS)) cs.forEach((c, k) => {
      const centre = band === 'alpha' ? this.persona.alphaHz + [-1.2, 0, 1.2][k] : c;
      this.freq[band + k] = centre; this.phase[band + k] = this.rng.uni() * 2 * Math.PI;
    });
    this.mod = { delta: 1, theta: 1, alpha: 1, beta: 1, gamma: 1 };
    this.driftPhase = this.rng.uni() * 2 * Math.PI; this.prevWhite = 0;
  }
  setMind(u) { this.u = Math.min(1, Math.max(0, u)); }
  jaw(seconds) { this.jawLeft = Math.round(seconds * this.fs); }
  amps() {
    const r = this.persona.reactivity, out = {};
    for (const b of Object.keys(NEUTRAL)) {
      const target = RELAX[b] + this.u * (FOCUS[b] - RELAX[b]);
      out[b] = NEUTRAL[b] + r * (target - NEUTRAL[b]);
    }
    return out;
  }
  read(n) {
    const out = new Float32Array(n), rng = this.rng, p = this.persona, twoPi = 2 * Math.PI;
    let amps = this.amps();
    for (let s = 0; s < n; s++) {
      if (this.i % Math.max(1, Math.floor(this.fs / 2)) === 0) {
        for (const b of Object.keys(this.mod)) this.mod[b] = Math.max(0.2, 0.8 * this.mod[b] + 0.2 * (1 + MOD_DEPTH * rng.gauss()));
      }
      if (this.i % 25 === 0) amps = this.amps();
      const t = this.i / this.fs;
      let v = 0;
      for (const k of Object.keys(this.freq)) {
        const band = k.slice(0, -1), rms = amps[band] * this.mod[band] / Math.sqrt(3);
        v += rms * Math.SQRT2 * Math.sin(this.phase[k] + twoPi * this.freq[k] * t);
      }
      v += rng.gauss() * p.noise + 1.0 * Math.sin(twoPi * 50 * t) + 10 * Math.sin(twoPi * 0.2 * t + this.driftPhase);
      if (this.jawLeft > 0) { const white = rng.gauss() * 25 * p.emgGain; v += white - this.prevWhite; this.prevWhite = white; this.jawLeft--; }
      out[s] = Math.min(1023, Math.max(0, 512 + p.gain * v));
      this.i++;
    }
    return out;
  }
}
