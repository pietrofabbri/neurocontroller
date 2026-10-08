import test from 'node:test';
import assert from 'node:assert';
import { Pipeline, quickProfile } from '../js/pipeline.mjs';
import { SimulatedSource } from '../js/simulata.mjs';

function run(persona, u, seconds, { jawAt = null } = {}) {
  const prof = quickProfile(persona, 5), src = new SimulatedSource({ persona, seed: 77 }), pl = new Pipeline(250, prof);
  src.setMind(u);
  const res = [];
  for (let s = 0; s < seconds; s++) {
    if (jawAt !== null && s === jawAt) src.jaw(4);
    res.push(...pl.push(src.read(250)));
  }
  return res;
}
const frac = (res, st) => res.filter((r) => r.state === st).length / res.length;

test('persona tipica: mente rilassata -> stati rilassati; concentrata -> concentrati', () => {
  const a = run('tipica', 0, 30).slice(8), b = run('tipica', 1, 30).slice(8);
  // il segnale simulato ha una lenta variazione propria (come uno vero): non e' tutto-o-niente
  assert.ok(frac(a, 'rilassato') > 0.5 && frac(a, 'concentrato') < 0.1, 'rilassato ' + frac(a, 'rilassato'));
  assert.ok(frac(b, 'concentrato') > 0.5 && frac(b, 'rilassato') < 0.1, 'concentrato ' + frac(b, 'concentrato'));
});

test('il profilo della persona tipica e\' affidabile, quello della persona nulla no', () => {
  assert.strictEqual(quickProfile('tipica', 5).level, 'affidabile');
  assert.notStrictEqual(quickProfile('nulla', 5).level, 'affidabile');
});

test('mascella serrata: finestre artefatto e nessuno stato concentrato in quel tratto (V-11)', () => {
  const res = run('tipica', 0, 30, { jawAt: 15 }).filter((r) => r.t > 15 && r.t < 21);
  assert.ok(res.some((r) => r.state === 'artefatto'), 'nessun artefatto rilevato');
  assert.ok(res.every((r) => r.state !== 'concentrato'), 'la mascella non deve sembrare concentrazione');
});

test('una finestra nuova ogni mezzo secondo (passo 125 a 250 Hz)', () => {
  const res = run('tipica', 0.5, 10);
  assert.ok(res.length >= 15 && res.length <= 17, 'risultati ' + res.length);
});
