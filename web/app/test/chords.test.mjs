import test from 'node:test';
import assert from 'node:assert';
import { ChordsParser, packetLength, BOARDS } from '../js/chords.mjs';

function pkt(counter, vals) {
  const n = vals.length, p = new Uint8Array(packetLength(n)); p[0] = 0xC7; p[1] = 0x7C; p[2] = counter & 255;
  vals.forEach((v, c) => { p[3 + 2 * c] = v >> 8; p[4 + 2 * c] = v & 255; }); p[p.length - 1] = 1; return p;
}
const cat = (...a) => { const o = new Uint8Array(a.reduce((x, y) => x + y.length, 0)); let i = 0; for (const b of a) { o.set(b, i); i += b.length; } return o; };

test('lunghezza e schede come nel firmware', () => { assert.strictEqual(packetLength(6), 16); assert.strictEqual(BOARDS['UNO-CLONE'], 6); });
test('un pacchetto: contatore e sei canali a 10 bit', () => {
  const pr = new ChordsParser(6), out = pr.push(pkt(7, [512, 1023, 0, 300, 301, 302]));
  assert.strictEqual(out.length, 1); assert.strictEqual(out[0].counter, 7); assert.deepStrictEqual(Array.from(out[0].values), [512, 1023, 0, 300, 301, 302]);
});
test('pacchetti spezzati in pezzi qualunque', () => {
  const stream = cat(pkt(0, [1, 2, 3, 4, 5, 6]), pkt(1, [7, 8, 9, 10, 11, 12]), pkt(2, [13, 14, 15, 16, 17, 18])), pr = new ChordsParser(6), got = [];
  for (let i = 0; i < stream.length; i += 5) got.push(...pr.push(stream.slice(i, i + 5)));
  assert.deepStrictEqual(got.map((p) => p.values[0]), [1, 7, 13]); assert.strictEqual(pr.lost, 0);
});
test('pacchetti persi contati, anche al giro del contatore', () => {
  const pr = new ChordsParser(6);
  pr.push(cat(pkt(254, [0, 0, 0, 0, 0, 0]), pkt(1, [0, 0, 0, 0, 0, 0]), pkt(2, [0, 0, 0, 0, 0, 0])));
  assert.strictEqual(pr.lost, 2);       // mancano 255 e 0
});
test('testo e rumore prima dei pacchetti: si risincronizza e conserva il testo', () => {
  const pr = new ChordsParser(6), t = new TextEncoder().encode('UNO-CLONE\r\n'), out = pr.push(cat(t, new Uint8Array([0xC7, 0x00, 0x99]), pkt(0, [5, 5, 5, 5, 5, 5])));
  assert.strictEqual(out.length, 1); assert.ok(pr.text.includes('UNO-CLONE'));
});
test('falso inizio (C7 7C senza byte finale giusto) scartato', () => {
  const bad = pkt(0, [1, 1, 1, 1, 1, 1]); bad[15] = 9;
  const pr = new ChordsParser(6), out = pr.push(cat(bad, pkt(1, [2, 2, 2, 2, 2, 2])));
  assert.deepStrictEqual(out.map((p) => p.values[0]), [2]);
});

import { readFileSync } from 'node:fs';
test('parita\' con il Python (ChordsParser): stessi pacchetti, persi e scartati', () => {
  const V = JSON.parse(readFileSync(new URL('./vettori.json', import.meta.url), 'utf8')).chords;
  const bytes = Uint8Array.from(V.hex.match(/../g).map((h) => parseInt(h, 16)));
  const pr = new ChordsParser(6), out = pr.push(bytes);
  assert.deepStrictEqual(out.map((p) => [p.counter, Array.from(p.values)]), V.pacchetti);
  assert.strictEqual(pr.lost, V.persi); assert.strictEqual(pr.skipped, V.scartati);
});
