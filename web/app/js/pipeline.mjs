// Catena di elaborazione: campioni -> finestre (512, passo 125) -> caratteristiche -> stato.
// Non sa da dove arrivano i campioni (V-19): li riceve da una Sorgente qualsiasi.
// Gira nel Web Worker (V-17) ma si prova anche in Node.

import { analyzeWindow, windowSize } from './dsp.mjs';
import { buildProfile, StateClassifier } from './classifier.mjs';
import { SimulatedSource } from './simulata.mjs';

export const HOP_FRACTION = 0.25;   // passo = un quarto della finestra (125 su 512), come il Python

export class Pipeline {
  constructor(fs, profile, { windowLen = windowSize(fs), hop = Math.round(windowSize(fs) * HOP_FRACTION) } = {}) {
    this.fs = fs; this.n = windowLen; this.hop = hop;
    this.buf = new Float64Array(this.n); this.filled = 0; this.sinceLast = 0; this.total = 0;
    this.clf = new StateClassifier(profile);
    this.profile = profile;
  }
  // Consegna un blocco di campioni; restituisce l'elenco dei risultati nuovi (zero o piu').
  push(samples) {
    const out = [];
    for (let i = 0; i < samples.length; i++) {
      this.buf.copyWithin(0, 1); this.buf[this.n - 1] = samples[i];
      this.total++; if (this.filled < this.n) this.filled++;
      if (this.filled === this.n && ++this.sinceLast >= this.hop) {
        this.sinceLast = 0;
        const f = analyzeWindow(this.buf, this.fs);
        const r = this.clf.update({ rms: f.rms, hfRatio: f.hfRatio, engagement: f.engagement });
        out.push({ t: this.total / this.fs, state: r.state, score: r.score, quality: r.quality,
                   rms: f.rms, hfRatio: f.hfRatio, E: f.engagement, rel: f.rel });
      }
    }
    return out;
  }
}

// Finestre pulite di una persona simulata a mente fissa u (per calibrare "al volo"; 120 finestre = circa 60 s, come un blocco vero).
export function windowsAt(persona, seed, u, fs, count) {
  const src = new SimulatedSource({ fs, persona, seed });
  src.setMind(u);
  const n = windowSize(fs), hop = Math.round(n * HOP_FRACTION), feats = [];
  const x = src.read(n + hop * (count - 1));
  for (let k = 0; k < count; k++) {
    const f = analyzeWindow(x.subarray(k * hop, k * hop + n), fs);
    feats.push({ rms: f.rms, hfRatio: f.hfRatio, engagement: f.engagement });
  }
  return feats;
}

// Calibrazione rapida SIMULATA (V-10): equivale ai blocchi rilassamento/concentrazione del protocollo.
export function quickProfile(persona, seed, fs = 250, count = 120) {
  const relax = windowsAt(persona, seed * 2 + 1, 0, fs, count);
  const focus = windowsAt(persona, seed * 2 + 2, 1, fs, count);
  const p = buildProfile(relax, focus);
  p.level = p.state.dprime >= 1.5 ? 'affidabile' : p.state.dprime >= 0.8 ? 'debole' : 'non affidabile';
  return p;
}
