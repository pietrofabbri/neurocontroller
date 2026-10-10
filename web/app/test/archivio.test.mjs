import test from 'node:test';
import assert from 'node:assert';
import { ArchivioLocale } from '../js/archivio_locale.mjs';

const mem = () => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, v), m }; };
const partita = (a, b, over = {}) => ({ player_a: a, player_b: b, source: 'simulata', seed: 7, duration_s: 600, depth_m: 12.5, gems: 0, rocks_hit: 1,
  coherent_s: 300, incoherent_s: 100, neutral_s: 150, artifact_s: 50, quality_pct: 91.5, score: 125,
  series: [{ t: 1, depth_m: 0.5, terrain: 'duro', state: 'concentrato', score_b: 0.7, quality: 1, coherence: 0.8, tempo: 100, density: 0.5, softness: 0.5, reason: '' }], ...over });

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
  assert.strictEqual(a.serie(1)[0].state, 'concentrato'); assert.strictEqual(a.serie(1)[0].softness, 0.5); assert.strictEqual(a.serie(1)[0].terrain, 'duro');
  assert.ok(!('series' in a.partite(null)[0]));
  assert.ok(a.csv().split('\n')[0].startsWith('id,played_at,player_a'));
  assert.ok(a.csv().split('\n')[0].includes('a_age_years') && a.csv().split('\n')[0].includes('b_consent'));
  assert.ok(a.csvSerie().startsWith('game_id,t,depth_m,terrain'));
});
test('partite non valide rifiutate', () => {
  const a = new ArchivioLocale(mem()); a.nuovoGiocatore(); a.nuovoGiocatore();
  for (const over of [{ source: 'altro' }, { depth_m: -1 }, { quality_pct: 101 }, { player_a: 'Mario' }, { gems: 'tanti' }, { series: [{ terrain: 'sabbia' }] }, { sensor_format: 'wifi' }, { b_fatigue: 9 }, { b_sleep_h: 30 }, { app_version: '<x>' }, { profile_level: 'ottimo' },
    { series: [{ t: 1, depth_m: 0, terrain: 'duro', state: 'neutro', score_b: 0, quality: 1, tempo: 1, density: 1, softness: 1, reason: 'boh' }] }])
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

test('scheda del partecipante: solo risposte a scelta; consenso esplicito e ritirabile', () => {
  const a = new ArchivioLocale(mem()); a.nuovoGiocatore();
  const p = a.aggiornaGiocatore('P01', { age_years: 17, gender: 'donna', handedness: 'destra', gaming: '1-3h', music_training: 'meno2', education: 'superiori' });
  assert.strictEqual(p.age_years, 17); assert.strictEqual(p.consent, 0);
  for (const bad of [{ age_years: 3 }, { age_years: 120 }, { age_years: 'dieci' }, { gender: 'Mario' }, { nome: 'Mario' }, { diagnosi: 'x' }, { consent: 1 }, { consent: 1, consent_by: 'amico' }, { gaming: 'tanto' }])
    assert.throws(() => a.aggiornaGiocatore('P01', bad), undefined, JSON.stringify(bad));
  const c = a.aggiornaGiocatore('P01', { consent: 1, consent_by: 'genitore_tutore' });
  assert.strictEqual(c.consent, 1); assert.strictEqual(c.consent_by, 'genitore_tutore'); assert.ok(c.consent_at); assert.ok(c.consent_version);
  const r = a.aggiornaGiocatore('P01', { consent: 0 });
  assert.strictEqual(r.consent, 0); assert.strictEqual(r.consent_at, null); assert.strictEqual(r.consent_by, null);
  assert.throws(() => a.aggiornaGiocatore('P09', {}), /sconosciuto/);
});
test('con il sensore vero serve il consenso di A e di B; con il simulato no', () => {
  const a = new ArchivioLocale(mem()); a.nuovoGiocatore(); a.nuovoGiocatore();
  assert.throws(() => a.salvaPartita(partita('P01', 'P02', { source: 'sensore' })), /consenso di P01/);
  a.aggiornaGiocatore('P01', { consent: 1, consent_by: 'persona' });
  assert.throws(() => a.salvaPartita(partita('P01', 'P02', { source: 'sensore' })), /consenso di P02/);
  a.aggiornaGiocatore('P02', { consent: 1, consent_by: 'persona' });
  assert.strictEqual(a.salvaPartita(partita('P01', 'P02', { source: 'sensore', signal_fs_hz: 193.4, sensor_format: 'ascii', sensor_baud: 9600, profile_level: 'affidabile', b_fatigue: 3, b_caffeine_3h: 0 })), 1);
  assert.strictEqual(a.salvaPartita(partita('P01', 'P02')), 2);                 // simulata: nessun vincolo
  assert.strictEqual(a.partite(null)[1].signal_fs_hz, 193.4);
  assert.strictEqual(a.partite(null)[0].signal_fs_hz, null);
});
test('CSV con scheda di A e B; cancellare un giocatore cancella anche la sua scheda', () => {
  const a = new ArchivioLocale(mem()); a.nuovoGiocatore(); a.nuovoGiocatore();
  a.aggiornaGiocatore('P01', { age_years: 18, gender: 'uomo' }); a.aggiornaGiocatore('P02', { age_years: 40 });
  a.salvaPartita(partita('P01', 'P02'));
  const righe = a.csv().trim().split('\n'), h = righe[0].split(','), v = righe[1].split(',');
  assert.strictEqual(v[h.indexOf('a_age_years')], '18'); assert.strictEqual(v[h.indexOf('b_age_years')], '40'); assert.strictEqual(v[h.indexOf('a_gender')], 'uomo');
  a.cancellaGiocatore('P01');
  assert.strictEqual(a.giocatori().length, 1); assert.strictEqual(a.csv().trim().split('\n').length, 1);
});
test('migrazione dal v1 del browser: partite e giocatori restano, i cursori si convertono', () => {
  const s = mem();
  s.setItem('talpa.archivio.v1', JSON.stringify({ players: [{ code: 'P01', created_at: 'x' }, { code: 'P02', created_at: 'x' }], next: 2,
    games: [{ id: 1, played_at: 'x', player_a: 'P01', player_b: 'P02', source: 'simulata', seed: 1, duration_s: 600, depth_m: 10, gems: 0, rocks_hit: 0, coherent_s: 1, incoherent_s: 1, neutral_s: 1, artifact_s: 0, quality_pct: 100, score: 100,
      series: [[1, 0.5, 'soffice', 'rilassato', -0.5, 1, 100, 0.25, 0.5, 0.5]] }] }));
  const a = new ArchivioLocale(s);
  assert.strictEqual(a.partite(null).length, 1); assert.strictEqual(a.giocatori()[0].consent, 0);
  assert.strictEqual(a.serie(1)[0].softness, 0.75); assert.strictEqual(a.serie(1)[0].density, 0.5); assert.strictEqual(a.serie(1)[0].reason, '');
  a.salvaPartita(partita('P01', 'P02')); assert.strictEqual(a.partite(null).length, 2);
});
