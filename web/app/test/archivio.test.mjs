import test from 'node:test';
import assert from 'node:assert';
import { ArchivioLocale } from '../js/archivio_locale.mjs';

const mem = () => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, v), m }; };
const partita = (a, b, over = {}) => ({ player_a: a, player_b: b, source: 'simulata', seed: 7, duration_s: 600, depth_m: 12.5, gems: 0, rocks_hit: 1,
  coherent_s: 300, incoherent_s: 100, neutral_s: 150, artifact_s: 50, quality_pct: 91.5, score: 125,
  series: [{ t: 1, depth_m: 0.5, terrain: 'compatto', state: 'concentrato', score_b: 0.7, quality: 1, tempo: 100, brightness: 0.5, density: 0.5, register: 0.5 }], ...over });

test('codici anonimi progressivi e niente nomi', () => {
  const a = new ArchivioLocale(mem());
  assert.strictEqual(a.nuovoGiocatore().code, 'P01'); assert.strictEqual(a.nuovoGiocatore().code, 'P02');
  for (const bad of ['Mario', 'P1', 'P0001', '<x>']) assert.throws(() => a.nuovoGiocatore(bad));
  assert.throws(() => a.nuovoGiocatore('P01'), /esistente/);
});
test('partita: salvataggio, storico, classifica, serie, CSV', () => {
  const a = new ArchivioLocale(mem()); a.nuovoGiocatore(); a.nuovoGiocatore();
  const id1 = a.salvaPartita(partita('P01', 'P02', { score: 10 })), id2 = a.salvaPartita(partita('P02', 'P01', { score: 99 }));
  assert.deepStrictEqual([id1, id2], [1, 2]);
  assert.strictEqual(a.partite('P01')[0].id, 2); assert.strictEqual(a.classifica(1)[0].id, 2);
  assert.strictEqual(a.serie(1)[0].state, 'concentrato'); assert.strictEqual(a.serie(1)[0].register, 0.5);
  assert.ok(!('series' in a.partite(null)[0]));
  assert.ok(a.csv().split('\n')[0].startsWith('id,played_at,player_a'));
});
test('partite non valide rifiutate', () => {
  const a = new ArchivioLocale(mem()); a.nuovoGiocatore(); a.nuovoGiocatore();
  for (const over of [{ source: 'altro' }, { depth_m: -1 }, { quality_pct: 101 }, { player_a: 'Mario' }, { gems: 'tanti' }, { series: [{ terrain: 'sabbia' }] }])
    assert.throws(() => a.salvaPartita(partita('P01', 'P02', over)));
  assert.throws(() => a.salvaPartita(partita('P01', 'P09')), /sconosciuto/);
});
test('cancellare un giocatore toglie le sue partite; i dati sopravvivono alla ricarica', () => {
  const s = mem(), a = new ArchivioLocale(s); a.nuovoGiocatore(); a.nuovoGiocatore(); a.nuovoGiocatore();
  a.salvaPartita(partita('P01', 'P02')); a.salvaPartita(partita('P02', 'P03'));
  assert.strictEqual(new ArchivioLocale(s).partite(null).length, 2);
  a.cancellaGiocatore('P01');
  assert.deepStrictEqual(new ArchivioLocale(s).partite(null).map((g) => g.id), [2]);
});
test('memoria piena: errore comprensibile', () => {
  const s = mem(); const a = new ArchivioLocale(s); a.nuovoGiocatore();
  s.setItem = () => { throw new Error('quota'); };
  assert.throws(() => a.nuovoGiocatore(), /memoria del browser piena/);
});
