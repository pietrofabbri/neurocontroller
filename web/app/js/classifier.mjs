// Profilo e classificatore dello stato: porting di neurocontroller/profile.py
// (stesse soglie e stessa media mobile; V-18).

export const STATE_RELAXED = 'rilassato';
export const STATE_FOCUSED = 'concentrato';
export const STATE_NEUTRAL = 'neutro';
export const STATE_ARTIFACT = 'artefatto';

export const RMS_FACTORS = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0];
export const HF_FACTORS = [2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 20.0];
export const MAX_FALSE_ALARM = 0.05;
export const DUBBIA_FRACTION = 0.8;   // proposta (03-pulizia-del-segnale.md, 4.6): da tarare

// Vicino alla soglia? Dubbia se oltre il 80% del tratto tra il valore tipico (mediana) e la soglia di scarto.
export function nearThreshold(value, thr, med) {
  const base = med === undefined ? 0 : med;
  return value > base + DUBBIA_FRACTION * (thr - base);
}

function median(v) {
  const s = Array.from(v).sort((a, b) => a - b), n = s.length;
  return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
}
function meanStd(v) {
  const m = v.reduce((a, b) => a + b, 0) / v.length;
  return [m, Math.sqrt(v.reduce((a, b) => a + (b - m) ** 2, 0) / v.length)];
}

// Il fattore piu' piccolo per cui mediana*fattore scarta non piu' di maxFpr dei valori.
export function pickFactor(values, factors, maxFpr) {
  const med = Math.max(median(values), 1e-12);
  for (const f of factors) {
    const thr = med * f;
    if (values.filter((v) => v > thr).length / values.length <= maxFpr) return [f, thr, med];
  }
  const f = factors[factors.length - 1];
  return [f, med * f, med];
}

export function isArtifact(rms, hfRatio, artifact) {
  return rms > artifact.rms_thr || hfRatio > artifact.hf_thr;
}

// Perche' una finestra e' stata scartata: '' (non scartata), 'ampiezza' (movimento, ciglia, contatto che balla),
// 'alta_freq' (troppa energia sopra i 42 Hz: tensione muscolare di fronte, mascella, collo) o 'entrambi'.
export function artifactReason(rms, hfRatio, artifact) {
  const a = rms > artifact.rms_thr, h = hfRatio > artifact.hf_thr;
  return a && h ? 'entrambi' : a ? 'ampiezza' : h ? 'alta_freq' : '';
}

export function decision(muR, sdR, muF, sdF) {
  sdR = Math.max(sdR, 1e-6); sdF = Math.max(sdF, 1e-6);
  const threshold = (muR * sdF + muF * sdR) / (sdR + sdF);
  const pooled = Math.sqrt((sdR ** 2 + sdF ** 2) / 2);
  return [threshold, (muF - muR) / pooled];
}

// Costruisce il profilo da finestre pulite di rilassamento e di concentrazione.
export function buildProfile(relaxFeatures, focusFeatures) {
  const clean = relaxFeatures.concat(focusFeatures);
  if (clean.length < 8) throw new Error('troppo pochi dati per il profilo');
  const [rmsF, rmsThr, rmsMed] = pickFactor(clean.map((f) => f.rms), RMS_FACTORS, MAX_FALSE_ALARM / 2);
  const [hfF, hfThr, hfMed] = pickFactor(clean.map((f) => f.hfRatio), HF_FACTORS, MAX_FALSE_ALARM / 2);
  const artifact = { rms_factor: rmsF, rms_thr: rmsThr, rms_median: rmsMed, hf_factor: hfF, hf_thr: hfThr, hf_median: hfMed };
  const ok = (f) => !isArtifact(f.rms, f.hfRatio, artifact);
  const er = relaxFeatures.filter(ok).map((f) => f.engagement);
  const ef = focusFeatures.filter(ok).map((f) => f.engagement);
  if (er.length < 8 || ef.length < 8) throw new Error('troppe finestre scartate come disturbo');
  const [muR, sdR] = meanStd(er), [muF, sdF] = meanStd(ef);
  const [threshold, dprime] = decision(muR, sdR, muF, sdF);
  return { artifact, state: { relax_mean: muR, relax_std: sdR, focus_mean: muF, focus_std: sdF, threshold, dprime } };
}

export class StateClassifier {
  constructor(profile, margin = 0.25, smooth = 3) {
    this.profile = profile; this.margin = margin; this.smooth = smooth;
    this.thr = profile.state.threshold;
    this.halfGap = Math.max((profile.state.focus_mean - profile.state.relax_mean) / 2, 1e-6);
    this.history = [];
  }
  reset() { this.history = []; }
  // quality: 'pulita' | 'dubbia' | 'scartata' (03-pulizia-del-segnale.md)
  update(f) {
    const a = this.profile.artifact;
    if (isArtifact(f.rms, f.hfRatio, a)) return { state: STATE_ARTIFACT, score: 0, quality: 'scartata', reason: artifactReason(f.rms, f.hfRatio, a), engagement: f.engagement };
    const score = (f.engagement - this.thr) / this.halfGap;
    this.history.push(score);
    if (this.history.length > this.smooth) this.history.shift();
    const avg = this.history.reduce((x, y) => x + y, 0) / this.history.length;
    const state = avg > this.margin ? STATE_FOCUSED : avg < -this.margin ? STATE_RELAXED : STATE_NEUTRAL;
    const quality = (nearThreshold(f.rms, a.rms_thr, a.rms_median) || nearThreshold(f.hfRatio, a.hf_thr, a.hf_median)) ? 'dubbia' : 'pulita';
    return { state, score: avg, quality, reason: quality === 'dubbia' ? 'vicino_soglia' : '', engagement: f.engagement };
  }
}
