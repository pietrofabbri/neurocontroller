// Parita' con il Python per la lettura delle righe seriali e il controllo del segnale (V-18).
import test from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { parseLine, RateMeter } from '../js/serial.mjs';
import { signalQuality } from '../js/quality.mjs';

const V = JSON.parse(readFileSync(new URL('./vettori.json', import.meta.url), 'utf8'));

test('parseLine: stesse righe lette come il Python (parse_line)', () => {
  for (const c of V.righe) assert.strictEqual(parseLine(c.riga, c.col), c.atteso, JSON.stringify(c.riga) + ' col ' + c.col);
});
test('parseLine: righe non numeriche o infinite scartate', () => {
  for (const r of ['inf', 'nan', '-inf', '0x10', 'Infinity']) assert.strictEqual(parseLine(r), null, r);
});
for (const c of V.qualita) {
  test('signalQuality ' + c.nome + ': stesso verdetto e numeri del Python', () => {
    const q = signalQuality(c.x, c.fs);
    assert.strictEqual(q.ok, c.ok); assert.strictEqual(q.problems.length, c.problemi);
    assert.ok(Math.abs(q.std - c.std) < 1e-6 * Math.max(1, c.std), 'std');
    assert.ok(Math.abs(q.clipFraction - c.clip) < 1e-12, 'clip');
    assert.ok(Math.abs(q.mainsRatio - c.mains) < 1e-6 * Math.max(1, c.mains) + 1e-9, 'mains ' + q.mainsRatio + ' vs ' + c.mains);
  });
}
test('RateMeter: 250 campioni/s da blocchi di 10 ogni 40 ms', () => {
  const r = new RateMeter(); for (let i = 0; i < 100; i++) r.add(10, i * 40);
  assert.ok(Math.abs(r.fs - 250) < 1e-9, String(r.fs));
});
