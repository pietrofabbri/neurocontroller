// Motore musicale di A (R-04, R-05): l'unico canale da A verso B. Web Audio, nessun file audio.
//
// A ha TRE cursori (massimo, per scelta del 10/10/2026), tutti 0..1 tranne il ritmo in battiti al minuto:
//   tempo       ritmo in bpm (60..140)
//   densita     quantita' e lunghezza delle note: poche note lunghe  <->  tante note brevi
//   morbidezza  timbro: secco, chiaro, vicino (0)  <->  morbido, scuro, avvolto dal riverbero (1).
//               Muove insieme: taglio del filtro, attacco della nota, forma d'onda, miscela secco/riverbero.
// Percussioni: NON ci sono quando la musica e' da rilassamento. Entrano solo quando l'indice di "focus"
// (ritmo + densita' + secchezza) supera una soglia, e crescono con esso.
//
// Gli effetti sullo stato di B sono IPOTESI da mettere alla prova (web/02-architettura.md, sez. 6): la
// letteratura sulla musica e sul rilassamento (tempo lento, poche note, timbri morbidi) e' un'indicazione,
// non una garanzia, e qui non e' verificata su EEG.

export const TEMPO_MIN = 60, TEMPO_MAX = 140;
export const SOGLIA_PERCUSSIONI = 0.5;   // sotto questo indice di focus: nessuna percussione
export const SOGLIA_HAT = 0.68;          // sopra: entra anche il piatto (hi-hat)
export const PRESET = {                  // usati solo per l'avvio della partita, non sono pulsanti
  calmo:    { tempo: 62,  densita: 0.2,  morbidezza: 0.85 },
  neutro:   { tempo: 100, densita: 0.5,  morbidezza: 0.5 },
  energico: { tempo: 136, densita: 0.85, morbidezza: 0.1 },
};
const SCALE = [0, 3, 5, 7, 10];               // La minore pentatonica (semitoni dalla tonica)
const A2 = 110;
const clamp = (x, lo, hi) => (x < lo ? lo : x > hi ? hi : x);

export const norm = (p) => ({ tempo: (p.tempo - TEMPO_MIN) / (TEMPO_MAX - TEMPO_MIN), densita: p.densita, morbidezza: p.morbidezza });

/** Indice di "focus" della musica, 0 (da rilassamento) .. 1 (da concentrazione). Pesi: ritmo 45%, densita' 35%, secchezza 20%. */
export function indiceFocus(p) {
  const n = norm(p);
  return clamp(0.45 * n.tempo + 0.35 * n.densita + 0.20 * (1 - n.morbidezza), 0, 1);
}
/** Intensita' delle percussioni 0..1 (0 = nessuna percussione). */
export function livelloPercussioni(p) {
  const f = indiceFocus(p);
  return f <= SOGLIA_PERCUSSIONI ? 0 : clamp((f - SOGLIA_PERCUSSIONI) / (0.9 - SOGLIA_PERCUSSIONI), 0, 1);
}
/** Parametri di suono derivati dai cursori (esportati per i test). */
export function timbro(p) {
  const m = p.morbidezza;
  return {
    cutoff: 400 * Math.pow(12, 1 - m),              // 400 Hz (morbido) ... ~4,8 kHz (secco)
    attacco: 0.006 + 0.22 * m * m,                  // s
    onda: m > 0.6 ? 'sine' : m > 0.3 ? 'triangle' : 'sawtooth',
    riverbero: 0.06 + 0.72 * m,                     // quota di segnale mandata al riverbero
    secco: 1 - 0.4 * m,
  };
}
/** Probabilita' di una nota ad ogni croma e sua durata in crome (poche note lunghe <-> molte brevi). */
export function noteDa(p) {
  return { probabilita: 0.12 + 0.85 * p.densita, durataCrome: 4.2 - 3.4 * p.densita };
}

export class Music {
  constructor() { this.p = { ...PRESET.neutro }; this.ctx = null; this.running = false; this.step = 0; this.next = 0; this.timer = null; this.seed = 1; this.last = null; }
  set(partial) {
    const q = { ...this.p };
    for (const k of ['tempo', 'densita', 'morbidezza']) if (partial && partial[k] !== undefined) q[k] = partial[k];   // solo i tre cursori
    q.tempo = clamp(q.tempo, TEMPO_MIN, TEMPO_MAX);
    for (const k of ['densita', 'morbidezza']) q[k] = clamp(q[k], 0, 1);
    this.p = q;
    this._applica();
  }
  _applica() {
    if (!this.ctx || !this.filter) return;
    const t = this.ctx.currentTime, tb = timbro(this.p), f = indiceFocus(this.p);
    this.filter.frequency.setTargetAtTime(tb.cutoff, t, 0.15);
    this.wet.gain.setTargetAtTime(tb.riverbero, t, 0.2);
    this.dry.gain.setTargetAtTime(tb.secco, t, 0.2);
    // il tappeto sonoro (pad) c'e' solo nella musica calma e scompare verso il focus
    const calma = 1 - clamp((f - 0.3) / 0.35, 0, 1);
    this.pad.gain.setTargetAtTime(0.16 * calma, t, 0.6);
  }
  _rnd() { this.seed = (this.seed * 1664525 + 1013904223) >>> 0; return this.seed / 4294967296; }
  _impulso(secondi) {
    const sr = this.ctx.sampleRate, len = Math.floor(sr * secondi), buf = this.ctx.createBuffer(2, len, sr);
    for (let c = 0; c < 2; c++) { const d = buf.getChannelData(c); for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3); }
    return buf;
  }
  start(volume = 0.5) {
    if (this.running) return;
    const AC = globalThis.AudioContext || globalThis.webkitAudioContext;
    if (!AC) { this.available = false; return; }
    this.available = true;
    this.ctx = new AC();
    const c = this.ctx;
    this.master = c.createGain(); this.master.gain.value = volume; this.master.connect(c.destination);
    this.filter = c.createBiquadFilter(); this.filter.type = 'lowpass'; this.filter.Q.value = 0.7; this.filter.frequency.value = timbro(this.p).cutoff;
    this.dry = c.createGain(); this.wet = c.createGain();
    this.verb = c.createConvolver(); this.verb.buffer = this._impulso(2.6);
    this.filter.connect(this.dry); this.dry.connect(this.master);
    this.filter.connect(this.verb); this.verb.connect(this.wet); this.wet.connect(this.master);
    this.perc = c.createGain(); this.perc.gain.value = 0.9; this.perc.connect(this.master);     // le percussioni non passano dal filtro
    // buffer di rumore per i piatti
    const nb = c.createBuffer(1, c.sampleRate, c.sampleRate), nd = nb.getChannelData(0); for (let i = 0; i < nd.length; i++) nd[i] = Math.random() * 2 - 1;
    this.rumore = nb;
    // tappeto (pad): quinta vuota La-Mi con una terza sopra, onde sinusoidali lunghe
    this.pad = c.createGain(); this.pad.gain.value = 0; this.pad.connect(this.filter);
    this.padOsc = [A2, A2 * 1.5, A2 * 2, A2 * 2.5].map((f, i) => {
      const o = c.createOscillator(), g = c.createGain(); o.type = 'sine'; o.frequency.value = f; o.detune.value = (i - 1.5) * 4;
      g.gain.value = [0.5, 0.35, 0.3, 0.15][i]; o.connect(g); g.connect(this.pad); o.start(); return o;
    });
    c.resume && c.resume();
    this.running = true; this.step = 0; this.next = c.currentTime + 0.1;
    this._applica();
    this.timer = setInterval(() => this._schedule(), 25);
  }
  stop() {
    this.running = false; clearInterval(this.timer);
    if (this.ctx) {
      try { this.master.gain.setTargetAtTime(0, this.ctx.currentTime, 0.05); setTimeout(() => { try { this.padOsc.forEach((o) => o.stop()); this.ctx && this.ctx.close(); } catch (e) { /* gia' chiuso */ } }, 300); } catch (e) { /* gia' chiuso */ }
    }
  }
  setVolume(v) { if (this.master) this.master.gain.value = v; }
  _schedule() {
    const stepDur = 60 / this.p.tempo / 2;                           // crome
    while (this.next < this.ctx.currentTime + 0.12) {
      this._play(this.step, this.next, stepDur);
      this.next += stepDur; this.step++;
    }
  }
  _play(step, when, stepDur) {
    const p = this.p, tb = timbro(p), nt = noteDa(p), pl = livelloPercussioni(p);
    // percussioni: solo oltre la soglia di focus
    if (pl > 0) {
      if (step % 2 === 0) this._cassa(when, 0.35 + 0.55 * pl);
      if (pl > (SOGLIA_HAT - SOGLIA_PERCUSSIONI) / (0.9 - SOGLIA_PERCUSSIONI) && step % 2 === 1) this._piatto(when, 0.1 + 0.18 * pl);
    }
    // note della melodia: poche e lunghe (rilassamento) <-> tante e brevi (focus)
    if (this._rnd() < nt.probabilita) {
      const ottave = p.densita < 0.35 ? 1 : p.densita < 0.7 ? 2 : 3;
      const semi = SCALE[Math.floor(this._rnd() * SCALE.length)] + 12 * ottave;
      const f = A2 * Math.pow(2, semi / 12);
      this.last = { f, when };
      this._nota(f, when, stepDur * nt.durataCrome, 0.12, tb);
    }
  }
  _nota(f, when, dur, gain, tb) {
    const o = this.ctx.createOscillator(), g = this.ctx.createGain();
    o.type = tb.onda; o.frequency.value = f;
    g.gain.setValueAtTime(0.0001, when);
    g.gain.exponentialRampToValueAtTime(gain, when + tb.attacco);
    g.gain.exponentialRampToValueAtTime(0.0001, when + Math.max(dur, tb.attacco + 0.05));
    o.connect(g); g.connect(this.filter);
    o.start(when); o.stop(when + Math.max(dur, tb.attacco + 0.05) + 0.05);
  }
  _cassa(when, gain) {
    const o = this.ctx.createOscillator(), g = this.ctx.createGain();
    o.type = 'sine'; o.frequency.setValueAtTime(150, when); o.frequency.exponentialRampToValueAtTime(45, when + 0.12);
    g.gain.setValueAtTime(gain, when); g.gain.exponentialRampToValueAtTime(0.0001, when + 0.22);
    o.connect(g); g.connect(this.perc); o.start(when); o.stop(when + 0.25);
  }
  _piatto(when, gain) {
    const s = this.ctx.createBufferSource(), hp = this.ctx.createBiquadFilter(), g = this.ctx.createGain();
    s.buffer = this.rumore; hp.type = 'highpass'; hp.frequency.value = 7000;
    g.gain.setValueAtTime(gain, when); g.gain.exponentialRampToValueAtTime(0.0001, when + 0.06);
    s.connect(hp); hp.connect(g); g.connect(this.perc); s.start(when); s.stop(when + 0.08);
  }
}
