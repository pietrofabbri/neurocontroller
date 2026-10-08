// Web Worker: genera (o riceve) i campioni, li elabora e restituisce STATI, non campioni (V-17).
// Messaggi in ingresso: {type:'avvia', persona, seed} | {type:'mente', u} | {type:'mascella', s} | {type:'ferma'}
// Messaggi in uscita:   {type:'pronto', level, dprime, persona} | {type:'stato', ...} | {type:'onda', campioni}
import { Pipeline, quickProfile } from './pipeline.mjs';
import { SimulatedSource } from './simulata.mjs';

const FS = 250;
let src = null, pipe = null, timer = null, last = 0, acc = 0, ondaBuf = [], ondaT = 0;

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
  } else if (m.type === 'mente' && src) src.setMind(m.u);
  else if (m.type === 'mascella' && src) src.jaw(m.s);
  else if (m.type === 'ferma') { clearInterval(timer); timer = null; }
};
