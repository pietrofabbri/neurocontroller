// Web Worker: genera (o riceve) i campioni, li elabora e restituisce STATI, non campioni (V-17).
// Messaggi in ingresso: {type:'avvia', persona, seed} | {type:'mente', u} | {type:'mascella', s} | {type:'ferma'}
// Messaggi in uscita:   {type:'pronto', level, dprime, persona} | {type:'stato', ...} | {type:'onda', campioni}
import { Pipeline, WindowStream, quickProfile, profileFromWindows } from './pipeline.mjs';
import { SimulatedSource } from './simulata.mjs';

const FS = 250;
let calib = null, calibWin = null, realFs = 250, src = null, pipe = null, timer = null, last = 0, acc = 0, ondaBuf = [], ondaT = 0;

function tick() {
  const now = performance.now();
  acc += Math.min(0.25, (now - last) / 1000) * FS; last = now;   // tempo reale: niente raffiche di campioni
  const n = Math.floor(acc); if (n < 1) return;
  acc -= n;
  const x = src.read(n);
  for (const r of pipe.push(x)) self.postMessage({ type: 'stato', ...r });
  for (let i = 0; i < x.length; i++) ondaBuf.push(x[i]);
  if (now - ondaT > 80) { self.postMessage({ type: 'onda', campioni: Float32Array.from(ondaBuf) }); ondaBuf = []; ondaT = now; }
}

self.onmessage = (e) => {
  const m = e.data;
  if (m.type === 'avvia') {
    clearInterval(timer);
    const profile = quickProfile(m.persona, m.seed >>> 0, FS);
    src = new SimulatedSource({ fs: FS, persona: m.persona, seed: (m.seed >>> 0) + 1000 });
    pipe = new Pipeline(FS, profile);
    self.postMessage({ type: 'pronto', level: profile.level, dprime: profile.state.dprime, persona: m.persona });
    last = performance.now(); acc = 0; ondaBuf = []; ondaT = last;
    timer = setInterval(tick, 20);
  } else if (m.type === 'avvia-sensore') { clearInterval(timer); src = null; }
  else if (m.type === 'mente' && src) src.setMind(m.u);
  else if (m.type === 'mascella' && src) src.jaw(m.s);
  else if (m.type === 'calibra-inizio') {            // sensore vero: raccolta delle finestre per blocco
    clearInterval(timer); src = null; realFs = m.fs; calib = { relax: [], focus: [] }; calibWin = null;
  } else if (m.type === 'blocco') {                   // {ruolo: 'relax' | 'focus' | null}: nuovo blocco, finestre da zero
    calibWin = m.ruolo ? { ruolo: m.ruolo, ws: new WindowStream(realFs) } : null;
  } else if (m.type === 'calibra-fine') {
    try {
      const p = profileFromWindows(calib.relax, calib.focus);
      pipe = new Pipeline(realFs, p);
      self.postMessage({ type: 'profilo', level: p.level, dprime: p.state.dprime, accuracy: p.accuracy, windows: p.windows, artifact: p.artifact, state: p.state });
    } catch (e) { self.postMessage({ type: 'profilo', errore: e.message }); }
  } else if (m.type === 'campioni') {                 // dal sensore (filo principale): Float32Array
    if (calibWin) { for (const f of calibWin.ws.push(m.data)) calib[calibWin.ruolo].push(f); self.postMessage({ type: 'calibra-avanzamento', relax: calib.relax.length, focus: calib.focus.length }); }
    else if (pipe && !src) {
      for (const r of pipe.push(m.data)) self.postMessage({ type: 'stato', ...r });
      self.postMessage({ type: 'onda', campioni: m.data });
    }
  } else if (m.type === 'ferma') { clearInterval(timer); timer = null; }
};
