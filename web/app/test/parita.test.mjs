// Parita' con il Python (V-18): stessi numeri sugli stessi segnali. Vettori da tools/genera_vettori_web.py.
import test from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { analyzeWindow } from '../js/dsp.mjs';
import { buildProfile, StateClassifier, pickFactor } from '../js/classifier.mjs';

const V = JSON.parse(readFileSync(new URL('./vettori.json', import.meta.url), 'utf8'));
const close = (a, b, rel = 1e-9, abs = 1e-9) => Math.abs(a - b) <= abs + rel * Math.abs(b);

for (const c of V.finestre) {
  test('finestra ' + c.nome + ': bande, rms, hf, E uguali al Python', () => {
    const f = analyzeWindow(Float64Array.from(c.x), c.fs);
    for (const k of Object.keys(c.atteso.absolute)) {
      assert.ok(close(f.absolute[k], c.atteso.absolute[k]), k + ' ' + f.absolute[k] + ' vs ' + c.atteso.absolute[k]);
      assert.ok(close(f.rel[k], c.atteso.rel[k]), 'rel ' + k);
    }
    assert.ok(close(f.total, c.atteso.total), 'total');
    assert.ok(close(f.rms, c.atteso.rms), 'rms');
    assert.ok(close(f.hfRatio, c.atteso.hf_ratio), 'hf');
    assert.ok(close(f.engagement, c.atteso.engagement), 'E');
  });
}

test('profilo: fattori, soglie e statistiche uguali al Python', () => {
  const C = V.classificatore;
  const p = buildProfile(C.rilassato, C.concentrato);
  const all = C.rilassato.concat(C.concentrato);
  assert.deepStrictEqual(pickFactor(all.map((f) => f.rms), [1.5, 2, 2.5, 3, 4, 5], 0.025).slice(0, 1), [C.fattori.rms[0]]);
  assert.ok(close(p.artifact.rms_thr, C.profilo.artifact.rms_thr));
  assert.ok(close(p.artifact.hf_thr, C.profilo.artifact.hf_thr));
  for (const k of Object.keys(C.profilo.state)) assert.ok(close(p.state[k], C.profilo.state[k]), k);
});

test('classificatore: stessa sequenza di stati e punteggi del Python', () => {
  const C = V.classificatore;
  const clf = new StateClassifier(C.profilo);
  for (const s of C.sequenza) {
    const r = clf.update(s.in);
    assert.strictEqual(r.state, s.state);
    assert.ok(close(r.score, s.score), 'score ' + r.score + ' vs ' + s.score);
  }
});
