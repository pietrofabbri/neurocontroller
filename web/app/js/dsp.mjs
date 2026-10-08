// Elaborazione del segnale: porting di neurocontroller/dsp.py (V-18: stessi numeri del Python).
// Solo JavaScript standard, nessuna dipendenza. Vale in un Worker e in Node (prove).

export const BANDS = {
  delta: [1, 4], theta: [4, 8], alpha: [8, 14], beta: [14, 30], gamma: [30, 42],
};
export const BAND_NAMES = Object.keys(BANDS);
export const TOTAL_RANGE = [1, 42];
export const MAINS_RANGE = [48, 52];
const EPS = 1e-12;

export function nextPow2(n) { let p = 1; while (p < n) p <<= 1; return p; }
export function windowSize(fs, seconds = 2) { return nextPow2(Math.ceil(seconds * fs)); }

const HANN = new Map();
function hann(n) {
  let w = HANN.get(n);
  if (!w) {
    w = new Float64Array(n);
    for (let k = 0; k < n; k++) w[k] = 0.5 - 0.5 * Math.cos(2 * Math.PI * k / (n - 1));
    HANN.set(n, w);
  }
  return w;
}

// FFT radix-2 iterativa (n potenza di 2). Restituisce {re, im}.
export function fft(x) {
  const n = x.length;
  if (n & (n - 1)) throw new Error('la lunghezza deve essere una potenza di 2');
  const re = new Float64Array(n), im = new Float64Array(n);
  const bits = Math.log2(n) | 0;
  for (let i = 0; i < n; i++) {
    let r = 0, v = i;
    for (let b = 0; b < bits; b++) { r = (r << 1) | (v & 1); v >>= 1; }
    re[r] = x[i];
  }
  for (let size = 2; size <= n; size <<= 1) {
    const half = size >> 1, step = -2 * Math.PI / size;
    for (let start = 0; start < n; start += size) {
      for (let k = 0; k < half; k++) {
        const wr = Math.cos(step * k), wi = Math.sin(step * k);
        const a = start + k, b = a + half;
        const tr = re[b] * wr - im[b] * wi, ti = re[b] * wi + im[b] * wr;
        re[b] = re[a] - tr; im[b] = im[a] - ti;
        re[a] += tr; im[a] += ti;
      }
    }
  }
  return { re, im };
}

// Toglie media e andamento lineare (deriva lenta).
export function detrend(x) {
  const n = x.length, out = new Float64Array(n);
  if (n < 2) { for (let i = 0; i < n; i++) out[i] = x[i]; return out; }
  const meanI = (n - 1) / 2;
  let meanX = 0;
  for (let i = 0; i < n; i++) meanX += x[i];
  meanX /= n;
  let num = 0, den = 0;
  for (let i = 0; i < n; i++) { num += (i - meanI) * (x[i] - meanX); den += (i - meanI) ** 2; }
  const slope = den ? num / den : 0;
  for (let i = 0; i < n; i++) out[i] = x[i] - meanX - slope * (i - meanI);
  return out;
}

// Spettro di potenza a un lato (finestra di Hann). Restituisce {freqs, psd, rms}.
export function powerSpectrum(window, fs) {
  const n = window.length, x = detrend(window);
  let s = 0;
  for (let i = 0; i < n; i++) s += x[i] * x[i];
  const rms = Math.sqrt(s / n), w = hann(n), xw = new Float64Array(n);
  let wsum = 0;
  for (let i = 0; i < n; i++) { xw[i] = x[i] * w[i]; wsum += w[i] * w[i]; }
  const { re, im } = fft(xw), scale = 1 / (fs * wsum), half = n >> 1;
  const psd = new Float64Array(half + 1), freqs = new Float64Array(half + 1);
  for (let k = 0; k <= half; k++) {
    let p = (re[k] * re[k] + im[k] * im[k]) * scale;
    if (k > 0 && k < half) p *= 2;
    psd[k] = p; freqs[k] = k * fs / n;
  }
  return { freqs, psd, rms };
}

export function bandPower(freqs, psd, lo, hi, exclude = [0, 0]) {
  if (freqs.length < 2) return 0;
  const df = freqs[1] - freqs[0];
  let total = 0;
  for (let i = 0; i < freqs.length; i++) {
    const f = freqs[i];
    if (f >= lo && f < hi && !(f >= exclude[0] && f < exclude[1])) total += psd[i];
  }
  return total * df;
}

// Caratteristiche di una finestra: potenze per banda, rms, rapporto ad alta frequenza, indice E.
export function analyzeWindow(window, fs) {
  const { freqs, psd, rms } = powerSpectrum(window, fs);
  const absolute = {};
  for (const name of BAND_NAMES) absolute[name] = bandPower(freqs, psd, BANDS[name][0], BANDS[name][1]);
  const total = bandPower(freqs, psd, TOTAL_RANGE[0], TOTAL_RANGE[1]);
  const rel = {};
  for (const name of BAND_NAMES) rel[name] = total > EPS ? absolute[name] / total : 0;
  const nyq = fs / 2;
  const hf = nyq >= 60 ? bandPower(freqs, psd, TOTAL_RANGE[1], nyq, MAINS_RANGE) : absolute.gamma;
  const hfRatio = total > EPS ? hf / total : 0;
  const engagement = Math.log((absolute.beta + EPS) / (absolute.alpha + absolute.theta + EPS));
  return { rel, absolute, total, rms, hfRatio, engagement };
}
