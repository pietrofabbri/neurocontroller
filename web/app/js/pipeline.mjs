// Catena di elaborazione: campioni -> finestre (512, passo 125) -> caratteristiche -> stato.
// Non sa da dove arrivano i campioni (V-19): li riceve da una Sorgente qualsiasi.
// Gira nel Web Worker (V-17) ma si prova anche in Node.

import { analyzeWindow, windowSize } from './dsp.mjs';
import { buildProfile, StateClassifier, isArtifact } from './classifier.mjs';
import { SimulatedSource } from './simulata.mjs';

export const HOP_FRACTION = 0.25;   // passo = un quarto della finestra (125 su 512), come il Python

// Finestre scorrevoli di caratteristiche, senza classificatore (per calibrare).
export class WindowStream {
  constructor(fs, { windowLen = windowSize(fs), hop = Math.round(windowSize(fs) * HOP_FRACTION) } = {}) {
    this.fs = fs; this.n = windowLen; this.hop = hop; this.buf = new Float64Array(this.n); this.filled = 0; this.since = 0; this.total = 0;
  }
  push(samples) {
    const out = [];
    for (let i = 0; i < samples.length; i++) {
      this.buf.copyWithin(0, 1); this.buf[this.n - 1] = samples[i]; this.total++;
      if (this.filled < this.n) this.filled++;
      if (this.filled === this.n && ++this.since >= this.hop) {
        this.since = 0;
        const f = analyzeWindow(this.buf, this.fs);
        out.push({ rms: f.rms, hfRatio: f.hfRatio, engagement: f.engagement });
      }
    }
    return out;
  }
}

// Soglie di qualita' del profilo (euristiche: neurocontroller/profile.py, Q_USABLE_*, Q_WEAK_*).
export const Q_USABLE_DPRIME = 1.5, Q_USABLE_ACC = 0.80, Q_WEAK_DPRIME = 0.8;
export function balancedAccuracy(relaxE, focusE, thr) {
  const r = relaxE.filter((v) => v < thr).length / relaxE.length, f = focusE.filter((v) => v >= thr).length / focusE.length;
  return (r + f) / 2;
}
export function profileLevel(dprime, acc) {
  return dprime >= Q_USABLE_DPRIME && acc >= Q_USABLE_ACC ? 'affidabile' : dprime >= Q_WEAK_DPRIME ? 'debole' : 'non affidabile';
}
// Profilo + verdetto, da finestre di rilassamento e di concentrazione.
export function profileFromWindows(relax, focus) {
  const p = buildProfile(relax, focus), ok = (f) => !isArtifact(f.rms, f.hfRatio, p.artifact);
  const er = relax.filter(ok).map((f) => f.engagement), ef = focus.filter(ok).map((f) => f.engagement);
  p.accuracy = balancedAccuracy(er, ef, p.state.threshold);
  p.level = profileLevel(p.state.dprime, p.accuracy);
  p.windows = { relax: relax.length, focus: focus.length, relaxClean: er.length, focusClean: ef.length };
  return p;
}

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
        out.push({ t: this.total / this.fs, state: r.state, score: r.score, quality: r.quality, reason: r.reason,
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
  return profileFromWindows(relax, focus);
}
