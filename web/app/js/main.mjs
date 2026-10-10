// Schermate e ciclo di gioco della talpa. Il nucleo di gioco e' in core.js (senza DOM, provato con Node).
import { Music, PRESET, norm, indiceFocus, livelloPercussioni } from './music.mjs';
import * as api from './api.mjs';
import { drawWorld, drawScope } from './view.mjs';
import { FlussoSensore, sensoreDisponibile } from './sensore.mjs';

const core = window.NC.core;
const $ = (id) => document.getElementById(id);
const clamp = core.clamp;
const NOMI_TERRENO = { soffice: 'SOFFICE', morbido: 'MORBIDO', medio: 'MEDIO', duro: 'DURO', compatto: 'COMPATTO' };
const MOTIVI = { ampiezza: 'ampiezza (movimento, ciglia, contatto che balla)', alta_freq: 'alte frequenze (tensione muscolare: fronte, mascella, collo)', entrambi: 'ampiezza e muscoli', vicino_soglia: 'vicino al limite' };
const NOMI_STATO = { rilassato: 'RILASSATO', concentrato: 'CONCENTRATO', neutro: 'in mezzo (neutro)', artefatto: 'disturbo (nessun punto)' };

const S = {
  schermata: 'home', fase: 'idle', players: [], game: null, mente: null, worker: null, music: new Music(),
  persona: 'tipica', durata: 300, A: null, B: null, keys: new Set(), ultimoStato: null, onda: [],
  serie: [], serieT: 0, menteT: 0, prev: 0, raf: 0, uMente: 0.5, riga: null, pronto: null, deriva: null, percN: 0, percTot: 0,
};
window.__S = S;   // utile per le prove automatiche

/* ------------------------------------------------------------------ schermate */
function mostra(nome) {
  S.schermata = nome;
  for (const id of ['home', 'gioco', 'fine', 'sensore']) $(id).hidden = id !== nome;
}
const msgHome = (t, cls = '') => { const m = $('home-msg'); m.textContent = t; m.className = 'msg ' + cls; };

/* ------------------------------------------------------------------ home */
function riempiSelect(sel, codes, scelto) {
  sel.innerHTML = '';
  if (!codes.length) { const o = document.createElement('option'); o.value = ''; o.textContent = '(premi + nuovo)'; sel.appendChild(o); }
  for (const c of codes) { const o = document.createElement('option'); o.value = o.textContent = c; sel.appendChild(o); }
  if (scelto && codes.includes(scelto)) sel.value = scelto;
}
async function aggiornaHome() {
  try {
    const modo = await api.rileva();
    $('modo').hidden = modo === 'server';
    $('modo').textContent = modo === 'server' ? '' : modo === 'browser'
      ? 'Sito senza server: le partite si salvano solo in questo browser (su questo computer). Se cancelli i dati del sito si perdono: scarica ogni tanto il CSV.'
      : 'Il browser non permette di salvare: le partite durano solo finché la pagina resta aperta.';
    S.players = (await api.giocatori()).map((p) => p.code);
    riempiSelect($('selA'), S.players, $('selA').value || S.players[0]);
    riempiSelect($('selB'), S.players, $('selB').value || S.players[1]);
    riempiSelect($('selDel'), S.players);
    const cl = await api.classifica(8);
    $('classifica').innerHTML = cl.length ? '' : '<li class="muted">Ancora nessuna partita.</li>';
    for (const g of cl) {
      const li = document.createElement('li');
      li.innerHTML = '<span><b></b> A ' + g.player_a + ' + B ' + g.player_b + (g.source === 'simulata' ? ' <span class="sim">simulato</span>' : '') + '</span>';
      li.querySelector('b').textContent = g.depth_m.toFixed(1) + ' m';
      $('classifica').appendChild(li);
    }
    await aggiornaStorico();
    msgHome('');
  } catch (e) {
    msgHome('Non riesco a leggere l\'archivio (' + e.message + ').', 'err');
  }
}
async function aggiornaStorico() {
  const chi = $('selA').value || null;
  $('storico-chi').textContent = chi ? '(di ' + chi + ')' : '';
  const gs = await api.partite(chi, 6);
  $('storico').innerHTML = gs.length ? '' : '<li class="muted">Nessuna partita.</li>';
  for (const g of gs) {
    const li = document.createElement('li');
    li.textContent = '#' + g.id + ' · ' + g.played_at.slice(0, 16).replace('T', ' ') + ' · A ' + g.player_a + ' / B ' + g.player_b + ' · ' + g.depth_m.toFixed(1) + ' m' + (g.source === 'simulata' ? ' · simulato' : '');
    $('storico').appendChild(li);
  }
}
async function nuovo(selId) {
  try { const p = await api.nuovoGiocatore(); await aggiornaHome(); $(selId).value = p.code; await aggiornaStorico(); msgHome('Creato il codice ' + p.code + '. Niente nomi: serve solo il codice.', 'ok'); }
  catch (e) { msgHome(e.message, 'err'); }
}
$('newA').onclick = () => nuovo('selA');
$('newB').onclick = () => nuovo('selB');
$('csv').onclick = async (e) => {
  if (api.modoAttuale() === 'server') return;           // il server fornisce il file da solo
  e.preventDefault();
  const url = URL.createObjectURL(new Blob([await api.csvTesto()], { type: 'text/csv' }));
  const a = document.createElement('a'); a.href = url; a.download = 'partite-talpa.csv'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 2000);
};
$('csv-serie').onclick = async (e) => {
  if (api.modoAttuale() === 'server') return;
  e.preventDefault();
  const url = URL.createObjectURL(new Blob([await api.csvSerieTesto()], { type: 'text/csv' }));
  const a = document.createElement('a'); a.href = url; a.download = 'serie-talpa.csv'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 2000);
};
$('selA').onchange = () => aggiornaStorico().catch(() => {});
$('del').onclick = async () => {
  const c = $('selDel').value; if (!c) return;
  if (!window.confirm('Cancellare ' + c + ' e tutte le partite in cui compare? Non si può annullare.')) return;
  try { await api.cancellaGiocatore(c); await aggiornaHome(); msgHome(c + ' cancellato.', 'ok'); } catch (e) { msgHome(e.message, 'err'); }
};

/* ------------------------------------------------------------------ scheda del partecipante e consenso */
async function consensoMancante() {
  const giocatori = await api.giocatori();
  for (const c of [S.A, S.B]) { const p = giocatori.find((x) => x.code === c); if (!p || !p.consent) return c; }
  return null;
}
let schedaCodice = null;
async function apriScheda(codice) {
  if (!codice) { msgHome('Scegli prima un giocatore.', 'err'); return; }
  const p = (await api.giocatori()).find((x) => x.code === codice);
  if (!p) { msgHome('Giocatore sconosciuto.', 'err'); return; }
  schedaCodice = codice;
  $('sc-codice').textContent = codice;
  $('sc-eta').value = p.age_years == null ? '' : p.age_years;
  $('sc-genere').value = p.gender || ''; $('sc-mano').value = p.handedness || ''; $('sc-gaming').value = p.gaming || '';
  $('sc-musica').value = p.music_training || ''; $('sc-studio').value = p.education || '';
  $('sc-consenso').checked = !!p.consent; $('sc-da').value = p.consent_by || 'persona';
  $('sc-stato').textContent = p.consent ? 'Consenso registrato il ' + (p.consent_at || '').slice(0, 10) + ' (' + (p.consent_by === 'genitore_tutore' ? 'genitore o tutore' : 'la persona') + ').' : 'Consenso non ancora registrato.';
  $('sc-msg').textContent = ''; $('sc-msg').className = 'msg';
  $('scheda').showModal();
}
$('schedaA').onclick = () => apriScheda($('selA').value);
$('schedaB').onclick = () => apriScheda($('selB').value);
$('sc-annulla').onclick = () => $('scheda').close();
$('sc-form').onsubmit = async (e) => {
  e.preventDefault();
  const v = (id) => $(id).value || null;
  const eta = $('sc-eta').value === '' ? null : Number($('sc-eta').value);
  const dati = { age_years: eta, gender: v('sc-genere'), handedness: v('sc-mano'), gaming: v('sc-gaming'), music_training: v('sc-musica'), education: v('sc-studio'),
    consent: $('sc-consenso').checked ? 1 : 0 };
  if (dati.consent) dati.consent_by = $('sc-da').value;
  try { await api.aggiornaGiocatore(schedaCodice, dati); $('scheda').close(); msgHome('Scheda di ' + schedaCodice + ' salvata.', 'ok'); }
  catch (err) { $('sc-msg').className = 'msg err'; $('sc-msg').textContent = err.message; }
};

$('avvia').onclick = async () => {
  try {
    while (S.players.length < 2) { await api.nuovoGiocatore(); S.players = (await api.giocatori()).map((p) => p.code); }
    await aggiornaHome();
    S.A = $('selA').value; S.B = $('selB').value;
    if (!S.A || !S.B || S.A === S.B) { msgHome('Servono due giocatori diversi: A guida, B è la mente che scava.', 'err'); return; }
    S.persona = $('sorgente').value; S.durata = +$('durata').value;
    if (S.persona === 'sensore') {
      const manca = await consensoMancante();
      if (manca) { msgHome('Per il sensore serve il consenso di ' + manca + ': apro la scheda.', 'err'); apriScheda(manca); return; }
    }
    if (S.persona === 'sensore') { if (!S.flusso) S.flusso = new FlussoSensore($, { onGioca: (f) => avviaPartita(), onEsci: () => { S.flusso = null; mostra('home'); aggiornaHome(); } }); S.flusso.apri(); mostra('sensore'); return; }
    avviaPartita();
  } catch (e) { msgHome(e.message, 'err'); }
};

/* ------------------------------------------------------------------ musica (controlli di A) */
// Tre cursori soltanto: ritmo, quante note (quantita' e lunghezza), morbidezza del suono (timbro, riverbero).
const CURSORI = ['tempo', 'densita', 'morbidezza'];
const ETICHETTE = { tempo: (v) => Math.round(v) + ' bpm', densita: pct, morbidezza: pct };
function pct(v) { return Math.round(v * 100) + '%'; }
function aggiornaSlider() {
  const p = S.music.p;
  for (const k of CURSORI) { $('r-' + k).value = p[k]; $('v-' + k).textContent = ETICHETTE[k](p[k]); }
  $('v-perc').textContent = livelloPercussioni(p) > 0 ? 'presenti' : 'assenti';
}
for (const k of CURSORI) $('r-' + k).oninput = (e) => { S.music.set({ [k]: +e.target.value }); aggiornaSlider(); e.target.blur(); };
$('vol').oninput = (e) => S.music.setVolume(+e.target.value);

/* ------------------------------------------------------------------ partita */
function avviaPartita() {
  const seme = (Math.random() * 2 ** 31) | 0;
  const sim = S.persona !== 'sensore';
  const personaSegnale = S.persona === 'manuale' ? 'tipica' : S.persona;
  S.game = new core.Partita({ durata: S.durata, seme });
  S.mente = sim ? new core.Mente(S.persona, seme + 3) : null;
  S.serie = []; S.serieT = 0; S.menteT = 0; S.ultimoStato = null; S.onda = []; S.uMente = 0.5; S.pronto = null; S.riga = null;
  S.deriva = new core.Deriva(seme); S.percN = 0; S.percTot = 0;
  S.fase = 'attesa'; S.keys.clear();
  $('badge-sim').hidden = !sim;
  $('keys-b').hidden = !sim;
  S.music.set(PRESET.neutro); aggiornaSlider();   // si parte a meta': poi i cursori scivolano e A deve guidarli
  S.music.start(+$('vol').value);
  mostra('gioco'); if (document.activeElement) document.activeElement.blur();
  if (sim) {
    overlay('Preparo B…<br><small>calibrazione rapida del segnale simulato</small>');
    S.worker = new Worker(new URL('./worker.mjs', import.meta.url), { type: 'module' });
    S.worker.onmessage = onWorker;
    S.worker.onerror = (e) => overlay('Errore nell\'elaborazione del segnale: ' + (e.message || 'sconosciuto'));
    S.worker.postMessage({ type: 'avvia', persona: personaSegnale, seed: seme });
  } else {
    overlay('Sto leggendo il sensore di B…<br><small>profilo calibrato in questa sessione</small>');
    S.worker = S.flusso.worker; S.worker.onmessage = onWorker; S.flusso.fase = 'gioco';
  }
  S.prev = performance.now();
  cancelAnimationFrame(S.raf); S.raf = requestAnimationFrame(ciclo);
}
function lampo(tipo) {
  const c = $('mondo'); c.classList.remove('flash-urto', 'flash-gemma'); void c.offsetWidth; c.classList.add('flash-' + tipo);
  setTimeout(() => c.classList.remove('flash-' + tipo), 250);
}
function overlay(html) { const o = $('overlay'); if (html) { o.innerHTML = html; o.hidden = false; } else o.hidden = true; }

function onWorker(e) {
  const m = e.data;
  if (m.type === 'pronto') {
    S.pronto = m;
    if (m.level === 'non affidabile') overlay('B simulato: <b>poco reattivo</b><br><small>il profilo non separa bene rilassato e concentrato (d′ ' + m.dprime.toFixed(1) + ')</small>');
  } else if (m.type === 'stato') {
    S.ultimoStato = m;
    if (S.fase === 'attesa') { S.fase = 'corsa'; overlay('Via!'); setTimeout(() => { if (S.fase === 'corsa') overlay(''); }, 900); }
  } else if (m.type === 'onda') {
    for (const v of m.campioni) S.onda.push(v);
    if (S.onda.length > 750) S.onda.splice(0, S.onda.length - 750);
    if ($('cofano').open) drawScope($('scope').getContext('2d'), 240, 110, S.onda, S.ultimoStato);
  }
}

function ciclo(now) {
  if (S.schermata !== 'gioco') return;
  const dt = Math.min(0.1, (now - S.prev) / 1000); S.prev = now;
  const g = S.game;
  if (S.fase === 'corsa') {
    const manuale = (S.keys.has('KeyX') ? 1 : 0) - (S.keys.has('KeyZ') ? 1 : 0);
    if (S.mente) {
      const s = S.mente.passo(dt, norm(S.music.p), manuale);
      S.menteT += dt;
      if (S.menteT >= 0.1) { S.menteT = 0; S.uMente = (s + 1) / 2; S.worker.postMessage({ type: 'mente', u: S.uMente }); }
    }
    // i cursori di A scivolano da soli: tenere la musica giusta per B richiede attenzione continua
    const dv = S.deriva.passo(dt), pm = S.music.p;
    S.music.set({ tempo: pm.tempo + dv[0] * 80, densita: pm.densita + dv[1], morbidezza: pm.morbidezza + dv[2] });
    aggiornaSlider();
    const st = S.ultimoStato;
    const inp = {
      sterzo: (S.keys.has('ArrowRight') ? 1 : 0) - (S.keys.has('ArrowLeft') ? 1 : 0),
      turbo: S.keys.has('Space') || S.keys.has('ArrowDown'),
      s: st ? clamp(st.score, -1, 1) : 0,
      qualita: st ? st.quality : 'scartata',
      motivo: st ? (st.reason || '') : '',
    };
    const ev = g.passo(dt, inp);
    S.serieT += dt;
    if (S.serieT >= 1) {
      S.serieT -= 1;
      const p = S.music.p, u = g.ultimo;
      S.serie.push({ t: +g.t.toFixed(1), depth_m: +g.profondita.toFixed(2), terrain: u.tipo, state: u.stato,
        score_b: +inp.s.toFixed(3), quality: { pulita: 1, dubbia: 0.5, scartata: 0 }[inp.qualita], coherence: +u.c.toFixed(3),
        tempo: +p.tempo.toFixed(1), density: +p.densita.toFixed(3), softness: +p.morbidezza.toFixed(3),
        reason: inp.qualita === 'pulita' ? '' : (inp.motivo || (inp.qualita === 'dubbia' ? 'vicino_soglia' : '')) });
      S.percTot++; if (livelloPercussioni(p) > 0) S.percN++;
    }
    if (ev.includes('urto')) lampo('urto'); else if (ev.includes('gemma')) lampo('gemma');
    if (ev.includes('fine')) { finePartita(); return; }
  }
  disegna(now);
  S.raf = requestAnimationFrame(ciclo);
}

function disegna(now) {
  const g = S.game, u = g.ultimo, st = S.ultimoStato;
  drawWorld($('mondo').getContext('2d'), 720, 560, g, now);
  const rest = Math.max(0, g.durata - g.t), mm = Math.floor(rest / 60), ss = Math.floor(rest % 60);
  $('h-tempo').textContent = mm + ':' + (ss < 10 ? '0' : '') + ss;
  $('h-prof').textContent = g.profondita.toFixed(1) + ' m';
  $('h-punti').textContent = g.punti();
  const tipo = g.mondo.tipoA(g.profondita + 0.3);
  $('h-terreno').textContent = NOMI_TERRENO[tipo] || tipo.toUpperCase();
  $('h-livello').textContent = '(livello ' + (core.ORDINE_TIPI.indexOf(tipo) + 1) + ' di 5: 1 soffice … 5 compatto)';
  $('h-richiesto').textContent = core.statoRichiesto(tipo).toUpperCase();
  const pc = g.mondo.prossimoCambio(g.profondita);
  $('h-prossimo').textContent = pc ? 'Tra ' + Math.max(0, Math.round(pc.tra)) + ' m: terreno ' + pc.tipo : '';
  $('h-gemme').textContent = g.st.gemme;
  $('h-stato').textContent = st ? NOMI_STATO[st.state] : '…';
  $('m-score').style.left = (st ? (clamp(st.score, -1, 1) + 1) * 50 : 50) + '%';
  $('h-qualita').textContent = !st ? '…' : st.quality === 'pulita' ? 'pulito' : st.quality === 'dubbia' ? 'dubbio (nessun punto)'
    : 'disturbato (nessun punto)' + (st.reason && MOTIVI[st.reason] ? ': ' + MOTIVI[st.reason] : '');
  $('h-coerenza').textContent = Math.round(u.c * 100) + '%';
  $('m-coer').style.width = u.c * 100 + '%';
  if (st) { $('c-E').textContent = st.E.toFixed(2); $('c-rms').textContent = st.rms.toFixed(1); $('c-hf').textContent = (st.hfRatio * 100).toFixed(1) + '%'; }
}

/* ------------------------------------------------------------------ fine e salvataggio */
function finePartita() {
  S.fase = 'fine';
  S.music.stop();
  if (S.persona === 'sensore') { if (S.flusso) S.flusso.fase = 'profilo'; S.worker = null; }
  else if (S.worker) { S.worker.postMessage({ type: 'ferma' }); S.worker.terminate(); S.worker = null; }
  const g = S.game, st = g.st, sim = S.persona !== 'sensore';
  const durata = Math.max(g.t, 1e-9);
  const ser = S.serie, media = (k) => (ser.length ? ser.reduce((a, r) => a + r[k], 0) / ser.length : null);
  const fl = S.flusso, prof = sim ? S.pronto : (fl && fl.profilo);
  const num = (id) => { const v = $(id).value; return v === '' ? null : Number(v); };
  S.riga = {
    player_a: S.A, player_b: S.B, source: sim ? 'simulata' : 'sensore', seed: g.seme,
    duration_s: +g.t.toFixed(1), depth_m: +g.profondita.toFixed(2), gems: st.gemme, rocks_hit: st.urti,
    coherent_s: +st.tCoerente.toFixed(1), incoherent_s: +st.tIncoerente.toFixed(1), neutral_s: +st.tNeutro.toFixed(1),
    artifact_s: +st.tSospeso.toFixed(1), quality_pct: +(100 * (1 - st.tSospeso / durata)).toFixed(1),
    score: g.punti(), series: S.serie,
    // metadati per la ricerca (web/06-dati-ricerca.md)
    app_version: core.CFG.versione, duration_planned_s: g.durata, coherence_mean: +(st.sommaC / (st.tAttivo || 1)).toFixed(3),
    turbo_s: +st.tTurbo.toFixed(1), dubious_s: +st.tDubbia.toFixed(1), artifact_amp_s: +st.tAmpiezza.toFixed(1), artifact_hf_s: +st.tAltaFreq.toFixed(1),
    terrain_changes: st.cambiTerreno,
    tempo_mean: ser.length ? +media('tempo').toFixed(1) : null, density_mean: ser.length ? +media('density').toFixed(3) : null, softness_mean: ser.length ? +media('softness').toFixed(3) : null,
    percussion_pct: S.percTot ? +(100 * S.percN / S.percTot).toFixed(1) : null,
    signal_fs_hz: sim ? 250 : (fl ? +fl.fs.toFixed(1) : null),
    sensor_format: sim || !fl || !fl.src ? null : fl.src.protocol, sensor_baud: sim || !fl || !fl.src ? null : fl.src.baud,
    profile_level: prof && prof.level ? prof.level : null, profile_dprime: prof && typeof prof.dprime === 'number' ? +prof.dprime.toFixed(3) : null,
    profile_accuracy: prof && typeof prof.accuracy === 'number' ? +prof.accuracy.toFixed(3) : null,
    calib_protocol: sim ? 'simulata-rapida' : 'web-v1-30s',
    b_sleep_h: num('c-sonno'), b_caffeine_3h: num('c-caffe'), b_fatigue: num('c-stanchezza'),
  };
  mostra('fine');
  $('f-titolo').textContent = 'Partita finita · A ' + S.A + ' + B ' + S.B + (sim ? ' (segnale simulato)' : '');
  $('f-prof').textContent = g.profondita.toFixed(1) + ' m';
  $('f-punti').textContent = g.punti();
  $('f-coer').textContent = Math.round(100 * st.sommaC / (st.tAttivo || 1)) + '%';
  $('f-urti').textContent = st.urti; $('f-gemme').textContent = st.gemme;
  $('f-raw').hidden = sim || !(S.flusso && S.flusso.raw && S.flusso.raw.length);
  $('f-dettagli').textContent = 'Tempo coerente ' + Math.round(st.tCoerente) + ' s · in mezzo ' + Math.round(st.tNeutro) + ' s · non coerente ' + Math.round(st.tIncoerente) +
    ' s · segnale non valido (nessun punto) ' + Math.round(st.tSospeso) + ' s' +
    (st.tSospeso > 5 ? ' (per ampiezza: ' + Math.round(st.tAmpiezza) + ' s · per alte frequenze/muscoli: ' + Math.round(st.tAltaFreq) + ' s · dubbio: ' + Math.round(st.tDubbia) + ' s)' : '') +
    '. Nel grafico: la linea è la profondità; sotto, verde = B coerente con il terreno, grigio = in parte, rosso = non coerente, nero = disturbo.';
  disegnaRiepilogo();
  salva();
}
async function salva() {
  const m = $('f-salvataggio'); m.className = 'msg'; m.textContent = 'Salvo nel database…'; $('f-riprova').hidden = true;
  try { const id = await api.salvaPartita(S.riga); m.className = 'msg ok'; m.textContent = (api.modoAttuale() === 'server' ? 'Salvata nel database locale come partita #' : 'Salvata in questo browser come partita #') + id + '.'; }
  catch (e) { m.className = 'msg err'; m.textContent = 'Non sono riuscito a salvare: ' + e.message; $('f-riprova').hidden = false; }
}
$('f-riprova').onclick = salva;
$('f-raw').onclick = () => { if (S.flusso) { S.flusso.scarica(); $('f-salvataggio').textContent += ' · Segnale grezzo scaricato (file locale: non metterlo nel repository).'; } };
$('f-ancora').onclick = () => avviaPartita();
$('f-home').onclick = () => { if (S.flusso) { S.flusso.chiudi(); S.flusso = null; } mostra('home'); aggiornaHome(); };

function disegnaRiepilogo() {
  const c = $('riepilogo').getContext('2d'), W = 720, H = 180, s = S.serie;
  c.clearRect(0, 0, W, H); c.fillStyle = '#10161c'; c.fillRect(0, 0, W, H);
  if (s.length < 2) return;
  const maxD = Math.max(1, ...s.map((r) => r.depth_m)), tMax = s[s.length - 1].t || 1, bw = W / s.length;
  s.forEach((r, i) => {
    const col = r.state === 'artefatto' ? '#000' : r.coherence >= 0.5 ? '#34d399' : r.coherence >= 0.2 ? '#6b7280' : '#f87171';
    c.fillStyle = col; c.fillRect(i * bw, H - 22, Math.ceil(bw), 14);
  });
  c.strokeStyle = '#f2b84b'; c.lineWidth = 2; c.beginPath();
  s.forEach((r, i) => { const x = r.t / tMax * (W - 4) + 2, y = 8 + (H - 40) * (r.depth_m / maxD); if (i) c.lineTo(x, y); else c.moveTo(x, y); });
  c.stroke(); c.fillStyle = '#9db0c0'; c.font = '12px system-ui'; c.fillText(maxD.toFixed(0) + ' m', 6, H - 28);
}

/* ------------------------------------------------------------------ tastiera */
const CONTROLLATI = new Set(['ArrowLeft', 'ArrowRight', 'ArrowDown', 'ArrowUp', 'Space']);
window.addEventListener('keydown', (e) => {
  if (S.schermata !== 'gioco') return;
  if (CONTROLLATI.has(e.code)) e.preventDefault();
  S.keys.add(e.code);
  if (e.code === 'Escape') { annulla(); return; }
  const p = S.music.p, d = { KeyQ: ['tempo', 6], KeyA: ['tempo', -6], KeyW: ['densita', .05], KeyS: ['densita', -.05],
    KeyE: ['morbidezza', .05], KeyD: ['morbidezza', -.05] }[e.code];
  if (d) { S.music.set({ [d[0]]: p[d[0]] + d[1] }); aggiornaSlider(); }
  if (e.code === 'KeyJ' && S.worker && S.persona !== 'sensore') S.worker.postMessage({ type: 'mascella', s: 3 });
});
window.addEventListener('keyup', (e) => S.keys.delete(e.code));
window.addEventListener('blur', () => S.keys.clear());
function annulla() {
  S.fase = 'idle'; S.music.stop();
  if (S.persona === 'sensore') { if (S.flusso) { S.flusso.chiudi(); S.flusso = null; } S.worker = null; }
  else if (S.worker) { S.worker.terminate(); S.worker = null; }
  mostra('home'); msgHome('Partita interrotta: non è stata salvata.'); aggiornaHome();
}

aggiornaHome();
if (sensoreDisponibile()) { const o = $('opt-sensore'); o.disabled = false; o.textContent = 'Sensore EEG (USB): Arduino + elettrodi'; }
