'use strict';
const test = require('node:test');
const assert = require('node:assert');
const C = require('../js/core.js');

const musicaVeloce = { tempo: 1, luminosita: 1, densita: 1 };
const musicaLenta = { tempo: 0, luminosita: 0, densita: 0 };

test('coerenza: nulla nella zona neutra, piena agli estremi, segno giusto per terreno', () => {
  assert.strictEqual(C.coerenza('compatto', 0), 0);
  assert.strictEqual(C.coerenza('compatto', 0.25), 0);
  assert.strictEqual(C.coerenza('compatto', 1), 1);
  assert.strictEqual(C.coerenza('soffice', -1), 1);
  assert.strictEqual(C.coerenza('compatto', -1), 0, 'rilassato sul compatto non e\' coerente');
  assert.strictEqual(C.coerenza('soffice', 1), 0, 'concentrato sul soffice non e\' coerente');
  assert.ok(C.coerenza('compatto', 0.6) > C.coerenza('compatto', 0.4));
});

test('classificaStato e statoRichiesto', () => {
  assert.strictEqual(C.classificaStato(0.3), 'concentrato');
  assert.strictEqual(C.classificaStato(-0.3), 'rilassato');
  assert.strictEqual(C.classificaStato(0.1), 'neutro');
  assert.strictEqual(C.statoRichiesto('compatto'), 'concentrato');
  assert.strictEqual(C.statoRichiesto('soffice'), 'rilassato');
});

test('velocita: cresce con la coerenza e il turbo la aumenta', () => {
  assert.ok(C.velocita(0, false) > 0, 'la talpa non si ferma del tutto');
  assert.ok(C.velocita(1, false) > C.velocita(0.5, false));
  assert.ok(C.velocita(0.5, true) > C.velocita(0.5, false));
});

test('Mondo: deterministico dal seme, strati contigui, rocce nella corsia', () => {
  const a = new C.Mondo(42), b = new C.Mondo(42), c = new C.Mondo(43);
  a.genera(300); b.genera(300);
  assert.deepStrictEqual(a.strati.slice(0, 8), b.strati.slice(0, 8));
  assert.notDeepStrictEqual(a.strati.slice(0, 8), c.strati.slice(0, 8));
  for (let i = 1; i < a.strati.length; i++) assert.strictEqual(a.strati[i].da, a.strati[i - 1].a);
  a.rocce.forEach(o => { assert.ok(o.x >= -0.9 && o.x <= 0.9); assert.ok(o.y >= 3); });
  assert.strictEqual(a.strati[0].tipo, 'soffice');
  const tipi = new Set(a.strati.map(s => s.tipo));
  assert.strictEqual(tipi.size, 2, 'tutti e due i terreni compaiono');
  assert.ok(a.prossimoCambio(0).tra > 0);
});

function simula(opz, ingressoFn, secondi) {
  const p = new C.Partita(opz);
  for (let t = 0; t < secondi * 10 && !p.finita; t++) p.passo(0.1, ingressoFn(p));
  return p;
}
// strategia "ideale": B e' sempre coerente con il terreno; A evita le rocce
function ideale(p) {
  return { sterzo: 0, turbo: false, s: p.ultimo.tipo === 'compatto' ? 1 : -1, qualita: 'pulita' };
}
function evita(p) {
  // sposta la talpa lontano dalla roccia piu' vicina davanti
  const r = p.mondo.rocceTra(p.profondita, p.profondita + 2).sort((a, b) => a.y - b.y)[0];
  let sterzo = 0;
  if (r && Math.abs(p.x - r.x) < r.rx + 0.2) sterzo = p.x >= r.x ? 1 : -1;
  if (p.x > 0.85) sterzo = Math.min(sterzo, 0) || -1;
  if (p.x < -0.85) sterzo = Math.max(sterzo, 0) || 1;
  return Object.assign(ideale(p), { sterzo });
}

test('Partita: la coerenza fa scendere piu\' in profondita' + '\' della non coerenza', () => {
  const buono = simula({ seme: 5, durata: 120 }, p => Object.assign(evita(p)), 120);
  const cattivo = simula({ seme: 5, durata: 120 }, p => ({ sterzo: 0, s: p.ultimo.tipo === 'compatto' ? -1 : 1, qualita: 'pulita' }), 120);
  assert.ok(buono.profondita > 3 * cattivo.profondita, `${buono.profondita} vs ${cattivo.profondita}`);
  assert.ok(buono.st.tCoerente > cattivo.st.tCoerente);
});

test('Partita: segnale non pulito = nessun punto (V-11) e stato artefatto', () => {
  const p = simula({ seme: 5, durata: 30 }, () => ({ sterzo: 0, s: 1, qualita: 'scartata' }), 30);
  assert.strictEqual(p.profondita, 0);
  assert.strictEqual(p.punti(), 0);
  assert.strictEqual(p.ultimo.stato, 'artefatto');
  assert.ok(p.st.tSospeso > 29);
});

test('Partita: la mascella (artefatto) non fa salire il punteggio nemmeno con s alto', () => {
  const p = new C.Partita({ seme: 9, durata: 60 });
  let prima = null;
  for (let i = 0; i < 100; i++) p.passo(0.1, { s: 1, qualita: 'pulita' });
  prima = p.profondita;
  for (let i = 0; i < 100; i++) p.passo(0.1, { s: 1, qualita: 'scartata' });
  assert.strictEqual(p.profondita, prima);
});

test('Partita: finisce una volta sola alla durata, con evento fine e serie al secondo', () => {
  const p = new C.Partita({ seme: 1, durata: 20 });
  let fine = 0;
  for (let i = 0; i < 400; i++) p.passo(0.1, ideale(p)).forEach(e => { if (e === 'fine') fine++; });
  assert.strictEqual(fine, 1);
  assert.ok(p.finita);
  assert.ok(Math.abs(p.t - 20) < 1e-6);
  assert.ok(p.serie.length >= 19 && p.serie.length <= 21);
});

test('Partita: urto contro una roccia ferma la talpa e la sposta di lato', () => {
  const p = new C.Partita({ seme: 3, durata: 300 });
  const r = p.mondo.rocce[0];
  p.profondita = r.y - r.ry - 1.5; p.x = r.x;
  let urti = 0, y0 = p.profondita;
  for (let i = 0; i < 40; i++) p.passo(0.1, { sterzo: 0, s: -1, qualita: 'pulita' }).forEach(e => { if (e === 'urto') urti++; });
  assert.ok(urti >= 1, 'deve colpire la roccia');
  assert.ok(Math.abs(p.x - r.x) >= r.rx, 'viene spinta di lato');
  assert.ok(p.st.tStordito > 0);
});

test('Partita: guidare di lato evita la roccia', () => {
  const p = new C.Partita({ seme: 3, durata: 300 });
  const r = p.mondo.rocce[0];
  p.profondita = r.y - r.ry - 2; p.x = r.x + r.rx + 0.3;   // gia' fuori dalla traiettoria
  for (let i = 0; i < 80; i++) p.passo(0.1, { sterzo: 0, s: 1, qualita: 'pulita' });
  assert.strictEqual(p.st.urti, 0);
});

test('Partita: record valido e archiviabile, senza campi strani', () => {
  const p = simula({ seme: 8, durata: 60 }, ideale, 60);
  const rec = p.record({ giocatoreA: 'P01', giocatoreB: 'P02', sorgente: 'simulata-manuale', musica: { tempo: 0.5, luminosita: 0.5, densita: 0.5 } });
  assert.deepStrictEqual(C.validaRecord(rec), []);
  assert.ok(rec.serie.length > 50);
  assert.strictEqual(C.validaRecord(Object.assign({}, rec, { giocatoreA: 'Mario' })).length, 1);
  assert.ok(C.validaRecord(Object.assign({}, rec, { nome: 'Mario Rossi' })).some(e => /campo non ammesso/.test(e)));
  assert.ok(C.validaRecord(Object.assign({}, rec, { simulata: 'si' })).length >= 1);
  assert.ok(C.validaRecord(null).length >= 1);
});

test('Mente: la persona tipica segue la musica, la nulla no, la debole poco', () => {
  function media(persona, musica) {
    const m = new C.Mente(persona, 11); let somma = 0, n = 0;
    for (let i = 0; i < 6000; i++) { const s = m.passo(0.1, musica, 0); if (i > 1500) { somma += s; n++; } }
    return somma / n;
  }
  assert.ok(media('tipica', musicaVeloce) > 0.5);
  assert.ok(media('tipica', musicaLenta) < -0.5);
  assert.ok(Math.abs(media('nulla', musicaVeloce)) < 0.2);
  const deb = media('debole', musicaVeloce);
  assert.ok(deb > 0.1 && deb < media('tipica', musicaVeloce));
});

test('Mente manuale: i tasti B spostano lo stato in fretta', () => {
  const m = new C.Mente('manuale', 2);
  for (let i = 0; i < 50; i++) m.passo(0.1, { tempo: 0.5, luminosita: 0.5, densita: 0.5 }, 1);
  assert.ok(m.s > 0.6);
  for (let i = 0; i < 80; i++) m.passo(0.1, { tempo: 0.5, luminosita: 0.5, densita: 0.5 }, -1);
  assert.ok(m.s < -0.6);
});

test('Mente: la musica di A fa guadagnare punti a una coppia (circuito completo)', () => {
  // A sceglie la musica in base al terreno richiesto; la persona tipica la segue
  function gioca(seguiMusica) {
    const p = new C.Partita({ seme: 21, durata: 180 }), m = new C.Mente('tipica', 5);
    for (let i = 0; i < 1800; i++) {
      const richiesto = C.statoRichiesto(p.mondo.tipoA(p.profondita + 1.5));    // A guarda in avanti
      const musica = seguiMusica ? (richiesto === 'concentrato' ? musicaVeloce : musicaLenta) : musicaLenta;
      const s = m.passo(0.1, musica, 0);
      p.passo(0.1, Object.assign(evita(p), { s, qualita: 'pulita' }));
    }
    return p.profondita;
  }
  assert.ok(gioca(true) > gioca(false) * 1.3, 'la musica giusta aiuta');
});

test('statistiche, classifica, CSV e codici', () => {
  const base = { versione: 'x', data: '2026-10-08T10:00:00.000Z', sorgente: 's', simulata: true, durata: 60, durataPrevista: 60, seme: 1, punti: 0, coerenzaMedia: 0.5, tCoerente: 0, tNeutro: 0, tIncoerente: 0, tSospeso: 0, tTurbo: 0, urti: 1 };
  const P = [
    Object.assign({}, base, { id: 'g1', giocatoreA: 'P01', giocatoreB: 'P02', profondita: 40 }),
    Object.assign({}, base, { id: 'g2', giocatoreA: 'P01', giocatoreB: 'P02', profondita: 60, data: '2026-10-09T10:00:00.000Z' }),
    Object.assign({}, base, { id: 'g3', giocatoreA: 'P03', giocatoreB: 'P01', profondita: 50, simulata: false })
  ];
  const s = C.statistichePersona(P, 'P01');
  assert.strictEqual(s.partite, 3); assert.strictEqual(s.comeA, 2); assert.strictEqual(s.comeB, 1);
  assert.strictEqual(s.migliore, 60); assert.deepStrictEqual(s.andamento, [40, 50, 60]); assert.strictEqual(s.reali, 1);
  const k = C.classificaCoppie(P, 10);
  assert.strictEqual(k[0].coppia, 'P01+P02'); assert.strictEqual(k[0].profondita, 60);
  assert.strictEqual(C.classificaCoppie(P, 10, true).length, 1);
  const csv = C.aCSV(P);
  assert.strictEqual(csv.split('\n')[0], C.COLONNE_CSV.join(','));
  assert.strictEqual(csv.trim().split('\n').length, 4);
  assert.strictEqual(C.prossimoCodice(P), 'P04');
  assert.strictEqual(C.prossimoCodice([]), 'P01');
  assert.ok(C.codiceValido('P01') && C.codiceValido('P123') && !C.codiceValido('p1') && !C.codiceValido('Mario') && !C.codiceValido('P1'));
});
