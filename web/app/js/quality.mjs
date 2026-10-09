// Controllo grossolano del segnale prima di calibrare: porting di neurocontroller/dsp.py, signal_quality.
import { powerSpectrum, bandPower, TOTAL_RANGE, MAINS_RANGE } from './dsp.mjs';

const EPS = 1e-12;

export function signalQuality(samples, fs, adcMin = 0, adcMax = 1023, flatStd = 0.5) {
  const n = samples.length, problems = [];
  if (n < 2) return { ok: false, std: 0, clipFraction: 0, mainsRatio: 0, problems: ['pochissimi campioni ricevuti'] };
  let sum = 0; for (let i = 0; i < n; i++) sum += samples[i];
  const mean = sum / n; let ss = 0, clipped = 0;
  for (let i = 0; i < n; i++) { ss += (samples[i] - mean) ** 2; if (samples[i] <= adcMin || samples[i] >= adcMax) clipped++; }
  const std = Math.sqrt(ss / n), clipFraction = clipped / n;
  let mainsRatio = 0;
  let nwin = 1; while (nwin * 2 <= n) nwin *= 2;
  if (nwin >= 128 && fs / 2 > MAINS_RANGE[1]) {
    const { freqs, psd } = powerSpectrum(Array.from(samples).slice(0, nwin), fs);
    const total = bandPower(freqs, psd, TOTAL_RANGE[0], TOTAL_RANGE[1]);
    const mains = bandPower(freqs, psd, MAINS_RANGE[0], MAINS_RANGE[1]);
    mainsRatio = total > EPS ? mains / total : 0;
  }
  if (std < flatStd) problems.push('segnale piatto: sensore scollegato, non alimentato o porta sbagliata');
  if (clipFraction > 0.02) problems.push('il segnale tocca i limiti dell\'ADC (' + Math.round(100 * clipFraction) + '% dei campioni): guadagno troppo alto o elettrodi non a contatto');
  if (mainsRatio > 1.0) problems.push('forte disturbo a 50 Hz (rete elettrica): allontanarsi da cavi e alimentatori, usare il computer a batteria');
  return { ok: problems.length === 0, std, clipFraction, mainsRatio, problems };
}
