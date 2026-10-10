'use strict';
const test = require('node:test');
const assert = require('node:assert');
const C = require('../js/core.js');

const musicaVeloce = { tempo: 1, densita: 1, morbidezza: 0 };
const musicaLenta = { tempo: 0, densita: 0, morbidezza: 1 };

test('coerenza: piena sul bersaglio del terreno, nulla lontano, intermedia sui livelli intermedi', () => {
  for (const t of C.ORDINE_TIPI) {
    const b = C.bersaglioTerreno(t);
    assert.strictEqual(C.coerenza(t, b), 1, t + ' piena sul bersaglio');
    assert.strictEqual(C.coerenza(t, b + 0.7), 0, t + ' nulla lontano dal bersaglio');
    assert.ok(C.coerenza(t, b + 0.2) < 1 && C.coerenza(t, b + 0.2) > 0);
  }
  assert.strictEqual(C.coerenza('compatto', -1), 0, 'rilassato sul compatto non e\' coerente');
  assert.strictEqual(C.coerenza('soffice', 1), 0, 'concentrato sul soffice non e\' coerente');
  assert.ok(C.coerenza('compatto', 0.6) > C.coerenza('compatto', 0.4));
  // sul terreno MEDIO lo stato neutro e' quello giusto (prima non dava mai punti)
  assert.strictEqual(C.coerenza('medio', 0), 1);
  assert.ok(C.coerenza('medio', 0) > C.coerenza('medio', 0.5));
  // i livelli sono ordinati: il bersaglio cresce dal soffice al compatto
  const bs = C.ORDINE_TIPI.map(C.bersaglioTerreno);
  assert.deepStrictEqual(bs.slice().sort((x, y) => x - y), bs);
  assert.strictEqual(new Set(bs).size, 5);
});

test('classificaStato e statoRichiesto', () => {
  assert.strictEqual(C.classificaStato(0.3), 'concentrato');
  assert.strictEqual(C.classificaStato(-0.3), 'rilassato');
  assert.strictEqual(C.classificaStato(0.1), 'neutro');
  assert.strictEqual(C.statoRichiesto('compatto'), 'concentrato');
  assert.strictEqual(C.statoRichiesto('soffice'), 'rilassato');
  assert.match(C.statoRichiesto('morbido'), /rilassato/);
  assert.match(C.statoRichiesto('duro'), /concentrato/);
  assert.match(C.statoRichiesto('medio'), /metà|neutro/);
});

test('velocita: cresce con la coerenza e il turbo la aumenta', () => {
  assert.ok(C.velocita(0, false) > 0, 'la talpa non si ferma del tutto');
  assert.ok(C.velocita(1, false) > C.velocita(0.5, false));
  assert.ok(C.velocita(0.5, true) > C.velocita(0.5, false));
});

test('Mondo: deterministico dal seme, strati contigui, cinque terreni, ostacoli vari nella corsia', () => {
  const a = new C.Mondo(42), b = new C.Mondo(42), c = new C.Mondo(43);
  a.genera(400); b.genera(400);
  assert.deepStrictEqual(a.strati.slice(0, 8), b.strati.slice(0, 8));
  assert.deepStrictEqual(a.rocce.slice(0, 8), b.rocce.slice(0, 8));
  assert.notDeepStrictEqual(a.strati.slice(0, 8), c.strati.slice(0, 8));
  for (let i = 1; i < a.strati.length; i++) {
    assert.strictEqual(a.strati[i].da, a.strati[i - 1].a);
    assert.notStrictEqual(a.strati[i].tipo, a.strati[i - 1].tipo, 'ogni strato cambia terreno');
  }
  assert.strictEqual(a.strati[0].tipo, 'soffice');
  assert.strictEqual(new Set(a.strati.map(s => s.tipo)).size, 5, 'compaiono tutti e cinque i terreni');
  a.strati.forEach(s => assert.ok(s.a - s.da >= 7 && s.a - s.da <= 16));
  a.rocce.forEach(o => { assert.ok(o.x >= -0.9 && o.x <= 0.9, o.tipo + ' x=' + o.x); assert.ok(o.y >= 2); assert.ok(o.id > 0); });
  assert.strictEqual(new Set(a.rocce.map(o => o.id)).size, a.rocce.length, 'id unici');
  const tipi = new Set(a.rocce.map(o => o.tipo));
  for (const t of ['roccia', 'masso', 'mobile', 'muro', 'gemma']) assert.ok(tipi.has(t), 'manca ' + t);
  assert.ok(a.prossimoCambio(0).tra > 0);
  // piu' ostacoli in profondita' che in superficie
  const dens = (da, aa) => a.rocce.filter(o => o.tipo !== 'gemma' && o.y >= da && o.y < aa).length / (aa - da);
  assert.ok(dens(60, 300) > 1.5 * dens(0, 12), 'la densita\' cresce con la profondita\'');
});

test('Mondo: i mobili oscillano, gli altri no; il varco del muro e\' passabile', () => {
  const w = new C.Mondo(7); w.genera(400);
  const mob = w.rocce.find(o => o.tipo === 'mobile');
  const xs = [0, 1, 2, 3, 4, 5, 6, 7].map(t => w.xDi(mob, t));
  assert.ok(Math.max(...xs) - Math.min(...xs) > 0.05, 'si muove');
  xs.forEach(x => assert.ok(x >= -1 && x <= 1));
  const fisso = w.rocce.find(o => o.tipo === 'roccia');
  assert.strictEqual(w.xDi(fisso, 0), w.xDi(fisso, 5));
  // muri: coppie alla stessa profondita' con un varco libero piu' largo della talpa
  const muri = w.rocce.filter(o => o.tipo === 'muro'), perY = {};
  muri.forEach(o => { (perY[o.y] = perY[o.y] || []).push(o); });
  const coppie = Object.values(perY); assert.ok(coppie.length > 3);
  coppie.forEach(c => { assert.strictEqual(c.length, 2); const [l, r] = c.sort((a, b) => a.x - b.x); assert.ok((r.x - r.rx) - (l.x + l.rx) >= 0.3 - 1e-9, 'varco'); });
});

function simula(opz, ingressoFn, secondi) {
  const p = new C.Partita(opz);
  for (let t = 0; t < secondi * 10 && !p.finita; t++) p.passo(0.1, ingressoFn(p));
  return p;
}
// strategia "ideale": B e' sempre sul bersaglio del terreno; A evita gli ostacoli e cerca il varco libero piu' vicino
function ideale(p) {
  return { sterzo: 0, turbo: false, s: C.bersaglioTerreno(p.ultimo.tipo), qualita: 'pulita' };
}
function evita(p) {
  const marg = 0.075 + 0.08, ost = p.mondo.rocceTra(p.profondita - 0.3, p.profondita + 2.4).filter(o => o.tipo !== 'gemma');
  const libero = (x) => Math.abs(x) <= 0.93 && ost.every(o => Math.abs(x - p.mondo.xDi(o, p.t + 1)) > o.rx + marg);
  let meta = p.x;
  if (!libero(p.x)) { for (let d = 0.05; d < 1.9; d += 0.05) { if (libero(p.x + d)) { meta = p.x + d; break; } if (libero(p.x - d)) { meta = p.x - d; break; } } }
  const sterzo = Math.abs(meta - p.x) < 0.02 ? 0 : (meta > p.x ? 1 : -1);
  return Object.assign(ideale(p), { sterzo });
}

test('Partita: la coerenza fa scendere piu\' in profondita' + '\' della non coerenza', () => {
  const buono = simula({ seme: 5, durata: 120 }, p => Object.assign(evita(p)), 120);
  const cattivo = simula({ seme: 5, durata: 120 }, p => ({ sterzo: 0, s: C.bersaglioTerreno(p.ultimo.tipo) > 0 ? -1 : 1, qualita: 'pulita' }), 120);
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
  assert.strictEqual(r.tipo, 'roccia');
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
  const rec = p.record({ giocatoreA: 'P01', giocatoreB: 'P02', sorgente: 'simulata-manuale', musica: { tempo: 0.5, densita: 0.5, morbidezza: 0.5 } });
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
  for (let i = 0; i < 50; i++) m.passo(0.1, { tempo: 0.5, densita: 0.5, morbidezza: 0.5 }, 1);
  assert.ok(m.s > 0.6);
  for (let i = 0; i < 80; i++) m.passo(0.1, { tempo: 0.5, densita: 0.5, morbidezza: 0.5 }, -1);
  assert.ok(m.s < -0.6);
});

test('Mente: la musica di A fa guadagnare punti a una coppia (circuito completo)', () => {
  // A sceglie la musica in base al terreno richiesto; la persona tipica la segue
  function gioca(seguiMusica) {
    const p = new C.Partita({ seme: 21, durata: 180 }), m = new C.Mente('tipica', 5);
    for (let i = 0; i < 1800; i++) {
      const bers = C.bersaglioTerreno(p.mondo.tipoA(p.profondita + 1.5));    // A guarda in avanti
      const musica = seguiMusica ? (bers > 0.3 ? musicaVeloce : musicaLenta) : musicaLenta;
      const s = m.passo(0.1, musica, 0);
      p.passo(0.1, Object.assign(evita(p), { s, qualita: 'pulita' }));
    }
    return p.profondita;
  }
  assert.ok(gioca(true) > gioca(false) * 1.3, 'la musica giusta aiuta');
});

test('statistiche, classifica, CSV e codici', () => {
  const base = { versione: 'x', gemme: 0, data: '2026-10-08T10:00:00.000Z', sorgente: 's', simulata: true, durata: 60, durataPrevista: 60, seme: 1, punti: 0, coerenzaMedia: 0.5, tCoerente: 0, tNeutro: 0, tIncoerente: 0, tSospeso: 0, tTurbo: 0, urti: 1 };
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


test('gemme: si raccolgono toccandole, danno punti, non stordiscono e non si raccolgono due volte', () => {
  const p = new C.Partita({ seme: 12, durata: 300 });
  const g = p.mondo.rocce.find(o => o.tipo === 'gemma');
  p.profondita = g.y - g.ry - 1.5; p.x = g.x;
  const punti0 = p.punti(); let ev = [];
  for (let i = 0; i < 30; i++) ev = ev.concat(p.passo(0.1, { sterzo: 0, s: C.bersaglioTerreno(p.ultimo.tipo), qualita: 'pulita' }));
  assert.strictEqual(p.st.gemme, 1); assert.ok(ev.includes('gemma')); assert.strictEqual(p.stordito, 0);
  assert.ok(p.punti() >= punti0 + C.CFG.puntiPerGemma);
  assert.strictEqual(p.record({ giocatoreA: 'P01', giocatoreB: 'P02' }).gemme, 1);
});

test('ostacolo mobile: colpisce solo dove si trova in quel momento', () => {
  const p = new C.Partita({ seme: 4, durata: 300 });
  const m = p.mondo.rocce.find(o => o.tipo === 'mobile');
  p.profondita = m.y - m.ry - 0.6; p.t = 3;
  p.x = Math.max(-0.95, Math.min(0.95, p.mondo.xDi(m, 3) + 0.9));                  // lontano da dove sta ora
  if (Math.abs(p.x - p.mondo.xDi(m, 3)) < 0.5) p.x = p.mondo.xDi(m, 3) - 0.9;
  for (let i = 0; i < 5; i++) p.passo(0.05, { sterzo: 0, s: 0.9, qualita: 'pulita' });
  assert.ok(!p.st.urtiPerTipo.mobile, 'il mobile non e\' dove era all\'inizio');
});

test('Partita: motivo dello scarto conteggiato (ampiezza, alte frequenze) e tempo dubbio', () => {
  const p = new C.Partita({ seme: 2, durata: 60 });
  for (let i = 0; i < 20; i++) p.passo(0.1, { s: 0, qualita: 'scartata', motivo: 'ampiezza' });
  for (let i = 0; i < 30; i++) p.passo(0.1, { s: 0, qualita: 'scartata', motivo: 'alta_freq' });
  for (let i = 0; i < 10; i++) p.passo(0.1, { s: 0, qualita: 'scartata', motivo: 'entrambi' });
  for (let i = 0; i < 10; i++) p.passo(0.1, { s: 0, qualita: 'dubbia', motivo: 'vicino_soglia' });
  assert.ok(Math.abs(p.st.tAmpiezza - 3) < 1e-6); assert.ok(Math.abs(p.st.tAltaFreq - 4) < 1e-6);
  assert.ok(Math.abs(p.st.tDubbia - 1) < 1e-6); assert.ok(Math.abs(p.st.tSospeso - 7) < 1e-6);
});

test('Deriva dei cursori: deterministica dal seme, spenta se l\'intensita\' e\' 0, resta limitata', () => {
  const a = new C.Deriva(5), b = new C.Deriva(5), z = new C.Deriva(5);
  const sa = [0, 0, 0];
  for (let i = 0; i < 3000; i++) {
    const da = a.passo(0.1), db = b.passo(0.1);
    assert.deepStrictEqual(da, db);
    assert.deepStrictEqual(z.passo(0.1, 0), [0, 0, 0]);
    for (let k = 0; k < 3; k++) sa[k] += da[k];
  }
  // dopo 5 minuti senza correzioni almeno un cursore si e' mosso in modo percepibile
  assert.ok(Math.max(...sa.map(Math.abs)) > 0.15, JSON.stringify(sa));
  // ma in 5 secondi non cambia tutto: A ha il tempo di correggere
  const c = new C.Deriva(9); const m = [0, 0, 0];
  for (let i = 0; i < 50; i++) { const d = c.passo(0.1); for (let k = 0; k < 3; k++) m[k] += d[k]; }
  assert.ok(Math.max(...m.map(Math.abs)) < 0.5);
});

test('Mente: il timbro morbido rilassa, quello secco concentra', () => {
  const base = { tempo: 0.5, densita: 0.5 };
  assert.ok(C.Mente.bersaglioMusica(Object.assign({ morbidezza: 1 }, base)) < 0);
  assert.ok(C.Mente.bersaglioMusica(Object.assign({ morbidezza: 0 }, base)) > 0);
  assert.strictEqual(C.Mente.bersaglioMusica(Object.assign({ morbidezza: 0.5 }, base)), 0);
});
