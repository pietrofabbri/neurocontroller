import test from 'node:test';
import assert from 'node:assert';
import { PRESET, indiceFocus, livelloPercussioni, timbro, noteDa, norm, SOGLIA_PERCUSSIONI, TEMPO_MIN, TEMPO_MAX, Music } from '../js/music.mjs';

test('preset: la musica calma non ha percussioni, quella energica si', () => {
  assert.strictEqual(livelloPercussioni(PRESET.calmo), 0);
  assert.ok(livelloPercussioni(PRESET.energico) > 0.5);
  assert.ok(indiceFocus(PRESET.calmo) < SOGLIA_PERCUSSIONI && indiceFocus(PRESET.energico) > SOGLIA_PERCUSSIONI);
});
test('nessuna percussione sotto la soglia, per qualunque combinazione di cursori', () => {
  let n = 0;
  for (let t = TEMPO_MIN; t <= TEMPO_MAX; t += 10) for (let d = 0; d <= 1; d += 0.1) for (let m = 0; m <= 1; m += 0.1) {
    const p = { tempo: t, densita: d, morbidezza: m };
    if (indiceFocus(p) <= SOGLIA_PERCUSSIONI) { assert.strictEqual(livelloPercussioni(p), 0); n++; } else assert.ok(livelloPercussioni(p) > 0);
  }
  assert.ok(n > 100);
});
test('l\'indice di focus cresce con ritmo e densita\' e cala con la morbidezza', () => {
  const b = { tempo: 100, densita: 0.5, morbidezza: 0.5 };
  assert.ok(indiceFocus({ ...b, tempo: 130 }) > indiceFocus(b));
  assert.ok(indiceFocus({ ...b, densita: 0.9 }) > indiceFocus(b));
  assert.ok(indiceFocus({ ...b, morbidezza: 0.1 }) > indiceFocus(b));
  assert.ok(indiceFocus({ tempo: 60, densita: 0, morbidezza: 1 }) === 0);
  assert.ok(Math.abs(indiceFocus({ tempo: 140, densita: 1, morbidezza: 0 }) - 1) < 1e-9);
});
test('timbro: piu\' morbido = piu\' scuro, attacco piu\' lento, piu\' riverbero, meno secco', () => {
  const sec = timbro({ morbidezza: 0 }), mor = timbro({ morbidezza: 1 });
  assert.ok(sec.cutoff > 4 * mor.cutoff); assert.ok(mor.attacco > 10 * sec.attacco);
  assert.ok(mor.riverbero > 5 * sec.riverbero); assert.ok(mor.secco < sec.secco);
  assert.strictEqual(sec.onda, 'sawtooth'); assert.strictEqual(mor.onda, 'sine');
});
test('note: poche e lunghe a bassa densita\', tante e brevi ad alta', () => {
  const rado = noteDa({ densita: 0 }), fitto = noteDa({ densita: 1 });
  assert.ok(fitto.probabilita > 4 * rado.probabilita); assert.ok(rado.durataCrome > 3 * fitto.durataCrome);
  assert.ok(fitto.probabilita <= 1);
});
test('Music.set limita i tre cursori e non ne ammette altri', () => {
  const m = new Music();
  m.set({ tempo: 500, densita: 2, morbidezza: -1, luminosita: 1, registro: 1 });
  assert.strictEqual(m.p.tempo, 140); assert.strictEqual(m.p.densita, 1); assert.strictEqual(m.p.morbidezza, 0);
  assert.deepStrictEqual(Object.keys(norm(m.p)).sort(), ['densita', 'morbidezza', 'tempo']);
  assert.deepStrictEqual(Object.keys(m.p).sort(), ['densita', 'morbidezza', 'tempo'], 'nessun quarto cursore');
});
