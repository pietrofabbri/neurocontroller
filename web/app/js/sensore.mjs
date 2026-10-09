// Flusso del sensore vero: collegamento -> controllo del segnale -> calibrazione -> gioco o vista dal vivo.
// Segue web/03-pulizia-del-segnale.md (L1) e il protocollo v1 di neurocontroller/protocol.py.
// NIENTE e' verificato su EEG vero: tutto viene misurato e mostrato. Dati grezzi solo in memoria (V-05),
// scaricabili solo con un clic dell'utente.
import { SerialSource, RateMeter, serialSupported } from './serial.mjs';
import { signalQuality } from './quality.mjs';
import { drawScope } from './view.mjs';

const COMUNE = 'Resta fermo/a, non parlare, non serrare la mascella. Tieni lo sguardo sul punto fisso (il segno + sullo schermo).';
export const BLOCCHI = [
  { key: 'relax_1', ruolo: 'relax', titolo: 'Rilassamento a occhi aperti (1)', durata: 60, istr: COMUNE + ' Respira lentamente: 4 secondi per inspirare, 6 per espirare. Lascia andare i pensieri.' },
  { key: 'focus_1', ruolo: 'focus', titolo: 'Calcolo mentale: sottrazioni (1)', durata: 60, istr: COMUNE + ' Parti da 1000 e sottrai 7 di seguito, a mente (993, 986, 979…). Se sbagli, riparti da dove ricordi. NON dire i numeri ad alta voce.' },
  { key: 'relax_2', ruolo: 'relax', titolo: 'Rilassamento a occhi aperti (2)', durata: 60, istr: COMUNE + ' Come prima: respiro lento, 4 secondi dentro e 6 fuori.' },
  { key: 'focus_2', ruolo: 'focus', titolo: 'Calcolo mentale: moltiplicazioni (2)', durata: 60, problemi: true, istr: COMUNE + ' Compariranno delle moltiplicazioni: calcolale a mente, senza dire il risultato. Non importa se non fai in tempo.' },
];
const TRIM = 5, PAUSA = 6, CHECK_S = 6;
// SOLO PER LE PROVE AUTOMATICHE: ?calib=12 accorcia i blocchi (con il sensore vero non si usa).
const CALIB_PROVA = +(new URLSearchParams(typeof location !== 'undefined' ? location.search : '').get('calib') || 0);
const durataBlocco = (b) => (CALIB_PROVA >= 10 ? CALIB_PROVA : b.durata);

export function sensoreDisponibile() { return serialSupported(); }

export class FlussoSensore {
  constructor($, { onGioca, onEsci }) {
    this.$ = $; this.onGioca = onGioca; this.onEsci = onEsci;
    this.src = null; this.worker = null; this.fase = 'inizio'; this.raw = []; this.rate = new RateMeter();
    this.checkBuf = []; this.fs = 250; this.adcMax = 1023; this.profilo = null; this.timer = null; this.ultimoStato = null; this.onda = []; this.ultimoDato = 0;
    const el = $;
    el('s-ok').onchange = () => { el('s-collega').disabled = !el('s-ok').checked || !serialSupported(); };
    el('s-collega').onclick = () => this.collega();
    el('s-calibra').onclick = () => this.calibra();
    el('s-gioca').onclick = () => { this.fase = 'gioco'; this.onGioca(this); };
    el('s-live').onclick = () => this.vistaLive();
    el('s-scarica').onclick = () => this.scarica();
    el('s-esci').onclick = () => { this.chiudi(); this.onEsci(); };
  }
  msg(t, cls = '') { const m = this.$('s-msg'); m.textContent = t; m.className = 'msg ' + cls; }
  mostraBatteria() {
    const b = this.$('s-batt'); b.textContent = '';
    if (navigator.getBattery) navigator.getBattery().then((bt) => {
      b.textContent = bt.charging ? '⚠ Il computer risulta COLLEGATO al caricatore: scollegalo.' : 'Batteria: ' + Math.round(bt.level * 100) + '%, non in carica. ✓';
      this.carica = bt.charging;
    }).catch(() => {});
  }
  apri() {
    this.$('s-ok').checked = false; this.$('s-collega').disabled = true; this.msg('');
    for (const id of ['s-check', 's-calib', 's-esito', 's-scope', 's-calibra', 's-gioca', 's-live', 's-scarica']) this.$(id).hidden = true;
    this.$('s-conn').textContent = serialSupported() ? '' : 'Questo browser non supporta la porta seriale: usa Chrome o Edge sul computer.';
    this.mostraBatteria();
  }
  async collega() {
    if (this.carica) { this.msg('Scollega il caricatore prima di collegare il sensore.', 'err'); return; }
    try {
      this.worker = new Worker(new URL('./worker.mjs', import.meta.url), { type: 'module' });
      this.worker.onmessage = (e) => this.daWorker(e.data);
      this.src = new SerialSource({ onData: (a, t) => this.dati(a, t), onError: (e) => this.msg('Errore della porta: ' + e.message, 'err'),
        onClose: () => { if (this.fase !== 'chiuso') this.msg('La porta seriale si è chiusa (cavo scollegato?).', 'err'); } });
      await this.src.connect();
    } catch (e) { this.msg(e.name === 'NotFoundError' ? 'Nessuna porta scelta.' : 'Non riesco ad aprire la porta: ' + e.message, 'err'); return; }
    this.fase = 'check'; this.checkBuf = []; this.rate = new RateMeter(); this.raw = []; this.tCheck = performance.now();
    this.$('s-collega').disabled = true; this.$('s-check').hidden = false;
    this.$('s-check').innerHTML = 'Controllo del segnale: stai <b>fermo/a, occhi aperti, a riposo</b> per ' + CHECK_S + ' secondi…';
    this.timer = setInterval(() => this.tickCheck(), 500);
  }
  dati(arr, tMs) {
    this.raw.push(arr); this.ultimoDato = tMs;
    if (this.fase === 'check') { this.rate.add(arr.length, tMs); for (const v of arr) this.checkBuf.push(v); }
    else if (this.worker && (this.fase === 'calib' || this.fase === 'gioco' || this.fase === 'live')) this.worker.postMessage({ type: 'campioni', data: arr });
    const c = this.$('s-conn'); c.textContent = 'Righe valide: ' + this.src.good + ' · scartate: ' + this.src.bad;
  }
  tickCheck() {
    const el = this.$('s-check');
    if (this.src.good === 0 && performance.now() - this.tCheck > 3000) {
      el.innerHTML = '<span class="sem bad">nessun dato</span> Non arrivano righe leggibili' + (this.src.lastLine ? ' (ultima riga ricevuta: «' + this.src.lastLine.replace(/</g, '&lt;') + '»)' : '') +
        '. Controlla baud (qui 115200), porta e che l\'Arduino stia inviando.';
      return;
    }
    if (performance.now() - this.tCheck < CHECK_S * 1000) return;
    clearInterval(this.timer);
    const x = this.checkBuf, fsM = this.rate.fs;
    let mx = -Infinity; for (const v of x) if (v > mx) mx = v;
    this.adcMax = mx > 16383 ? 65535 : mx > 4095 ? 16383 : mx > 1023 ? 4095 : 1023;
    const q = signalQuality(x, fsM || 250, 0, this.adcMax);
    const dev = fsM ? Math.abs(fsM - 250) / 250 : 1;
    const probs = q.problems.slice();
    if (!fsM || fsM < 60) probs.push('frequenza di campionamento misurata troppo bassa (' + Math.round(fsM) + ' campioni/s)');
    else if (dev > 0.10) probs.push('frequenza misurata ' + Math.round(fsM) + ' campioni/s, diversa dai 250 attesi: la uso così com\'è, ma verifica il firmware');
    const grave = !q.ok || !fsM || fsM < 60;
    this.fs = fsM >= 60 ? fsM : 250;
    el.innerHTML = '<span class="sem ' + (grave ? 'bad' : probs.length ? 'warn' : 'ok') + '">' + (grave ? 'da sistemare' : probs.length ? 'attenzione' : 'segnale ok') + '</span> ' +
      'frequenza misurata <b>' + Math.round(fsM) + '</b> campioni/s · variazione (dev. standard) <b>' + q.std.toFixed(1) + '</b> · sul fondo scala ' + Math.round(100 * q.clipFraction) + '% · rete 50 Hz ' + q.mainsRatio.toFixed(2) +
      (probs.length ? '<ul>' + probs.map((p) => '<li>' + p + '</li>').join('') + '</ul>' : '') +
      '<div class="muted">Controllo grossolano: dice se ha senso procedere, non che sia EEG.</div>';
    this.fase = 'pronto-calib';
    this.$('s-calibra').hidden = false; this.$('s-calibra').disabled = grave;
    this.$('s-scarica').hidden = false;
    this.$('s-live').hidden = false; this.worker.postMessage({ type: 'calibra-inizio', fs: this.fs });
    this.msg(grave ? 'Risolvi i problemi qui sopra e ricollega, poi riprova.' : 'Puoi procedere con la calibrazione.');
  }
  calibra() {
    this.fase = 'calib'; this.idx = -1; this.$('s-calibra').hidden = true; this.$('s-live').hidden = true; this.$('s-calib').hidden = false;
    this.worker.postMessage({ type: 'calibra-inizio', fs: this.fs });
    this.prossimoBlocco();
  }
  prossimoBlocco() {
    this.idx++;
    if (this.idx >= BLOCCHI.length) return this.finisciCalibrazione();
    const b = BLOCCHI[this.idx];
    this.$('s-blocco').textContent = 'Blocco ' + (this.idx + 1) + ' di ' + BLOCCHI.length + ' · ' + b.titolo;
    this.$('s-istr').textContent = b.istr; this.$('s-punto').textContent = '·';
    this.worker.postMessage({ type: 'blocco', ruolo: null });
    this.t0 = performance.now(); this.stadio = 'pausa'; this.ultimoProb = 0;
    clearInterval(this.timer); this.timer = setInterval(() => this.tickCalib(), 200);
  }
  tickCalib() {
    const b = BLOCCHI[this.idx], t = (performance.now() - this.t0) / 1000;
    if (performance.now() - this.ultimoDato > 3000) { this.$('s-tempo').textContent = '⚠ Non arrivano più dati dal sensore.'; return; }
    if (this.stadio === 'pausa') {
      this.$('s-tempo').textContent = 'Preparati… si parte tra ' + Math.max(0, Math.ceil(PAUSA - t)) + ' s'; this.$('s-barra').style.width = '0%';
      if (t >= PAUSA) { this.stadio = 'blocco'; this.t0 = performance.now(); this.worker.postMessage({ type: 'blocco', ruolo: null }); this.trimmed = false; }
      return;
    }
    if (!this.trimmed && t >= TRIM) { this.trimmed = true; this.worker.postMessage({ type: 'blocco', ruolo: b.ruolo }); }
    this.$('s-barra').style.width = Math.min(100, 100 * t / durataBlocco(b)) + '%';
    this.$('s-tempo').textContent = (this.trimmed ? 'Registro… ' : 'Assestamento… ') + Math.max(0, Math.ceil(durataBlocco(b) - t)) + ' s';
    if (b.problemi) { if (t - this.ultimoProb >= 7) { this.ultimoProb = t; const a = 13 + Math.floor(Math.random() * 35), c = 3 + Math.floor(Math.random() * 7); this.$('s-punto').textContent = a + ' × ' + c; } }
    else this.$('s-punto').textContent = '+';
    if (t >= durataBlocco(b)) { this.worker.postMessage({ type: 'blocco', ruolo: null }); this.prossimoBlocco(); }
  }
  finisciCalibrazione() {
    clearInterval(this.timer); this.$('s-calib').hidden = true; this.$('s-punto').textContent = '+';
    this.worker.postMessage({ type: 'calibra-fine' });
    this.msg('Calcolo il profilo…');
  }
  daWorker(m) {
    if (m.type === 'profilo') {
      this.profilo = m; const el = this.$('s-esito'); el.hidden = false;
      if (m.errore) { el.innerHTML = '<span class="sem bad">calibrazione non riuscita</span> ' + m.errore + '. Ripeti il collegamento e controlla contatto e disturbi.'; this.msg(''); this.fase = 'pronto-calib'; this.$('s-calibra').hidden = false; return; }
      const buono = m.level === 'affidabile';
      el.innerHTML = '<span class="sem ' + (buono ? 'ok' : m.level === 'debole' ? 'warn' : 'bad') + '">profilo ' + m.level + '</span> ' +
        'separazione rilassato/concentrato d′ = <b>' + m.dprime.toFixed(2) + '</b> · accuratezza bilanciata <b>' + Math.round(100 * m.accuracy) + '%</b> · finestre pulite ' + m.windows.relaxClean + '/' + m.windows.relax + ' (rilassato), ' + m.windows.focusClean + '/' + m.windows.focus + ' (concentrato).' +
        (buono ? '<div class="muted">Soglie euristiche, mai validate su più persone: lo stato resta una stima.</div>'
          : '<div>Con questo profilo la partita con il sensore <b>non è consentita</b>: in questo caso non si distingue in modo affidabile il rilassamento dalla concentrazione. Puoi scaricare la registrazione per analizzarla, guardare la vista dal vivo, o riprovare (contatto, mascella, rete).</div>');
      this.fase = 'profilo'; this.msg('');
      this.$('s-gioca').hidden = !buono; this.$('s-live').hidden = false; this.$('s-calibra').hidden = false; this.$('s-calibra').textContent = 'Ripeti la calibrazione';
      this.$('s-scarica').hidden = false;
    } else if (m.type === 'stato') { this.ultimoStato = m; if (this.fase === 'live') this.aggiornaLive(); }
    else if (m.type === 'onda') { for (const v of m.campioni) this.onda.push(v); if (this.onda.length > 750) this.onda.splice(0, this.onda.length - 750); if (this.fase === 'live') drawScope(this.$('s-scope').getContext('2d'), 480, 110, this.onda, this.ultimoStato); }
  }
  vistaLive() {
    if (!this.profilo || this.profilo.errore) {
      this.msg('Prima serve una calibrazione: la vista dal vivo usa il tuo profilo.', 'err'); return;
    }
    this.fase = this.fase === 'live' ? 'profilo' : 'live';
    this.$('s-scope').hidden = this.fase !== 'live'; this.$('s-live').textContent = this.fase === 'live' ? 'Chiudi la vista dal vivo' : 'Vista dal vivo (senza gioco)';
    if (this.fase !== 'live') this.msg('');
  }
  aggiornaLive() {
    const s = this.ultimoStato; this.msg('Stato (stima): ' + s.state + ' · punteggio ' + s.score.toFixed(2) + ' · qualità ' + s.quality + ' · rumore ' + s.rms.toFixed(1));
  }
  scarica() {
    const tot = this.raw.reduce((a, c) => a + c.length, 0);
    if (!tot) { this.msg('Nessun dato da scaricare.', 'err'); return; }
    const righe = []; for (const c of this.raw) for (const v of c) righe.push(v);
    const blob = new Blob([righe.join('\n') + '\n'], { type: 'text/csv' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'registrazione-sensore.csv'; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    this.msg('Scaricati ' + tot + ' campioni (un valore per riga, frequenza misurata ' + Math.round(this.fs) + ' campioni/s). Non metterli nel repository (dati fisiologici).', 'ok');
  }
  chiudi() {
    this.fase = 'chiuso'; clearInterval(this.timer);
    if (this.src) this.src.close();
    if (this.worker) { this.worker.terminate(); this.worker = null; }
    this.src = null; this.raw = []; this.profilo = null;
  }
}
