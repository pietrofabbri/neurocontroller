/* Nucleo del gioco della talpa: logica pura, senza DOM, senza audio, senza rete.
 *
 * Gira nel browser (script classico, spazio dei nomi NC) e in Node (module.exports), cosi'
 * si prova con test automatici. Vedi web/01-decisioni-e-vincoli.md (vincoli V-xx) e
 * docs/02-richieste-originali.md (R-01...R-09).
 *
 * Meccanica centrale (R-06, R-07): la talpa scava; il terreno cambia a caso tra SOFFICE e
 * COMPATTO; il giocatore B e' efficace sul compatto se CONCENTRATO e sul soffice se RILASSATO;
 * piu' lo stato di B e' coerente con il terreno, piu' la talpa va in profondita'. Il giocatore A
 * guida la talpa e le fa evitare le rocce (R-06) e comanda la musica (R-03, R-05).
 */
(function (root) {
  'use strict';

  var NC = root.NC = root.NC || {};

  /* ---------- Costanti (tutte modificabili qui, in un posto solo) ---------- */
  var CFG = {
    versione: 'W0.2',
    durataPartita: 300,        // secondi: 5 minuti (dimezzata rispetto ai 10 minuti di R-01, richiesta del 10/10/2026)
    durataProva: 60,           // partita di prova
    margineStato: 0.25,        // come StateClassifier del Python: entro +-0,25 lo stato e' "neutro"
    velBase: 0.25,             // m/s anche senza coerenza (la talpa non si ferma del tutto)
    velExtra: 2.35,            // m/s in piu' con coerenza piena
    moltTurbo: 1.5,            // scavo veloce: piu' profondita', piu' rischio
    velSterzo: 0.9,            // unita' di corsia al secondo
    stordimento: 1.4,          // s fermi dopo un urto contro una roccia
    moltStordTurbo: 2.0,       // lo stordimento dura di piu' in turbo
    puntiPerMetro: 10,
    puntiPerGemma: 80,         // una gemma vale 8 metri: rischiare per prenderla conviene, ma non troppo
    derivaMusica: 0.03,        // intensita' della deriva casuale dei 3 cursori di A (0 = spenta): A deve tenere il passo
    pesoMusicaDeriva: 3,       // secondi di memoria della velocita' di deriva
    larghezzaTalpa: 0.075,     // mezza larghezza, in unita' di corsia (la corsia va da -1 a +1)
    campionamentoSerie: 1.0    // secondi tra un punto e l'altro della serie salvata
  };

  /* Terreni a cinque livelli: dal piu' soffice (B rilassato) al piu' compatto (B concentrato).
   * I livelli intermedi chiedono a B uno stato intermedio (punteggio di B vicino al valore indicato). */
  var TIPO = { SOFFICE: 'soffice', MORBIDO: 'morbido', MEDIO: 'medio', DURO: 'duro', COMPATTO: 'compatto' };
  var ORDINE_TIPI = [TIPO.SOFFICE, TIPO.MORBIDO, TIPO.MEDIO, TIPO.DURO, TIPO.COMPATTO];
  var LIVELLO = { soffice: -1, morbido: -0.5, medio: 0, duro: 0.5, compatto: 1 };
  var RICHIESTO = { soffice: 'rilassato', morbido: 'un po\' rilassato', medio: 'a metà (neutro)', duro: 'un po\' concentrato', compatto: 'concentrato' };
  var OSTACOLO = { ROCCIA: 'roccia', MASSO: 'masso', MOBILE: 'mobile', MURO: 'muro', GEMMA: 'gemma' };
  var STATO = { RILASSATO: 'rilassato', CONCENTRATO: 'concentrato', NEUTRO: 'neutro', ARTEFATTO: 'artefatto' };
  var QUALITA = { PULITA: 'pulita', DUBBIA: 'dubbia', SCARTATA: 'scartata' };

  /* ---------- Numeri casuali con seme (per prove ripetibili) ---------- */
  function rng(seme) {
    var a = (seme >>> 0) || 1;
    function next() {                       // mulberry32
      a = (a + 0x6D2B79F5) >>> 0;
      var t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    }
    next.gauss = function () {
      var u = 0, v = 0;
      while (u === 0) u = next();
      v = next();
      return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
    };
    return next;
  }

  function clamp(x, lo, hi) { return x < lo ? lo : (x > hi ? hi : x); }

  /* ---------- Stato mentale e coerenza ---------- */

  /** Da punteggio continuo s in [-1,+1] (come il Python: -1 tipico del riposo, +1 del calcolo) a stato. */
  function classificaStato(s, margine) {
    var m = margine == null ? CFG.margineStato : margine;
    if (s > m) return STATO.CONCENTRATO;
    if (s < -m) return STATO.RILASSATO;
    return STATO.NEUTRO;
  }

  /** Stato richiesto da un terreno (R-07), in parole. */
  function statoRichiesto(tipo) { return RICHIESTO[tipo] || RICHIESTO.medio; }

  /** Punteggio di B che rende piena la coerenza per un terreno (agli estremi 0,9: il +-1 pieno e' raro). */
  var BERSAGLIO_ESTREMO = 0.9, LARGHEZZA_COERENZA = 0.6;
  function bersaglioTerreno(tipo) { return (LIVELLO[tipo] == null ? 0 : LIVELLO[tipo]) * BERSAGLIO_ESTREMO; }

  /** Coerenza in [0,1] tra il punteggio s di B e il terreno: piena sul bersaglio, nulla a 0,6 di distanza.
   *  Sui terreni intermedi il bersaglio e' intermedio, quindi lo stato "neutro" puo' essere quello giusto. */
  function coerenza(tipo, s) {
    return clamp(1 - Math.abs(s - bersaglioTerreno(tipo)) / LARGHEZZA_COERENZA, 0, 1);
  }

  /** Velocita' di discesa (m/s). */
  function velocita(c, turbo) {
    return (CFG.velBase + CFG.velExtra * c) * (turbo ? CFG.moltTurbo : 1);
  }

  /* ---------- Il mondo: strati di terreno e ostacoli, generati dal seme ---------- */
  function Mondo(seme) {
    this.seme = seme >>> 0;
    this.strati = [];          // { da, a, tipo }
    this.rocce = [];           // ostacoli e gemme: { id, tipo, x, y, rx, ry, [amp, freq, fase] } (y in metri di profondita')
    this._r = rng(this.seme);
    this._fine = 0;            // profondita' fino a cui e' stato generato
    this._idx = 0;             // indice nel terreno (0 = soffice ... 4 = compatto): si parte dal soffice
    this._prossimoId = 1;
    this.genera(60);
  }
  /** Prossimo livello di terreno: passi di 1 (spesso), 2 o piu' (qualche volta), mai lo stesso due volte. */
  Mondo.prototype._nuovoIndice = function () {
    var r = this._r, passo = r() < 0.55 ? 1 : (r() < 0.6 ? 2 : (r() < 0.6 ? 3 : 4));
    var su = r() < 0.5 ? 1 : -1, i = this._idx + su * passo;
    if (i < 0 || i > 4) i = this._idx - su * passo;
    if (i < 0 || i > 4) i = clamp(this._idx + su, 0, 4);
    if (i === this._idx) i = this._idx === 4 ? 3 : this._idx + 1;
    return i;
  };
  Mondo.prototype._aggiungi = function (o) { o.id = this._prossimoId++; this.rocce.push(o); };
  Mondo.prototype.genera = function (finoA) {
    var r = this._r, self = this;
    while (this._fine < finoA) {
      var lung = 7 + Math.floor(r() * 10);                // 7-16 m: i terreni cambiano spesso
      var da = this._fine, a = da + lung;
      this.strati.push({ da: da, a: a, tipo: ORDINE_TIPI[this._idx] });
      // ostacoli: pochi nel primo tratto, poi sempre piu' fitti e vari
      var n = Math.floor(lung / (da < 12 ? 7 : (da < 40 ? 3.6 : 2.6)));
      for (var i = 0; i < n; i++) {
        var y = da + 2.5 + r() * (lung - 2.5), q = r(), x = -0.88 + r() * 1.76;
        if (da < 12 || q < 0.45) self._aggiungi({ tipo: OSTACOLO.ROCCIA, x: x, y: y, rx: 0.07 + r() * 0.07, ry: 0.35 + r() * 0.25 });
        else if (q < 0.62) self._aggiungi({ tipo: OSTACOLO.MASSO, x: x * 0.8, y: y, rx: 0.17 + r() * 0.10, ry: 0.5 + r() * 0.3 });
        else if (q < 0.82) {
          var amp = 0.25 + r() * 0.3, x0 = clamp(x, -0.9 + amp, 0.9 - amp);
          self._aggiungi({ tipo: OSTACOLO.MOBILE, x: x0, y: y, rx: 0.09, ry: 0.32, amp: amp, freq: 0.12 + r() * 0.16, fase: r() * 6.28 });
        } else {   // muro con varco: due blocchi ai lati di un passaggio largo circa due talpe
          var gap = 0.34, c = -0.55 + r() * 1.1, sx = c - gap / 2, dx = c + gap / 2;
          self._aggiungi({ tipo: OSTACOLO.MURO, x: (-1 + sx) / 2, y: y, rx: (sx + 1) / 2, ry: 0.4 });
          self._aggiungi({ tipo: OSTACOLO.MURO, x: (1 + dx) / 2, y: y, rx: (1 - dx) / 2, ry: 0.4 });
        }
      }
      // gemme: una ogni tanto (rischio contro premio)
      if (da >= 8 && r() < 0.6) self._aggiungi({ tipo: OSTACOLO.GEMMA, x: -0.8 + r() * 1.6, y: da + 2 + r() * (lung - 3), rx: 0.07, ry: 0.3 });
      this._fine = a;
      this._idx = this._nuovoIndice();
    }
  };
  /** Ascissa di un ostacolo al tempo t (i mobili oscillano). */
  Mondo.prototype.xDi = function (o, t) {
    return o.tipo === OSTACOLO.MOBILE ? o.x + o.amp * Math.sin(2 * Math.PI * o.freq * t + o.fase) : o.x;
  };
  Mondo.prototype.strato = function (y) {
    this.genera(y + 60);
    for (var i = 0; i < this.strati.length; i++) if (y >= this.strati[i].da && y < this.strati[i].a) return this.strati[i];
    return this.strati[this.strati.length - 1];
  };
  Mondo.prototype.tipoA = function (y) { return this.strato(Math.max(0, y)).tipo; };
  /** Il prossimo cambio di terreno oltre y: { tra: metri, tipo } */
  Mondo.prototype.prossimoCambio = function (y) {
    var s = this.strato(Math.max(0, y));
    for (var i = this.strati.indexOf(s) + 1; i < this.strati.length; i++) {
      if (this.strati[i].tipo !== s.tipo) return { tra: this.strati[i].da - y, tipo: this.strati[i].tipo };
    }
    return null;
  };
  Mondo.prototype.rocceTra = function (da, a) {
    this.genera(a + 60);
    return this.rocce.filter(function (o) { return o.y + o.ry >= da && o.y - o.ry <= a; });
  };

  /* ---------- Deriva dei cursori della musica ----------
   * Senza che A faccia nulla, i tre cursori scivolano piano e a caso: A non puo' regolare una volta e
   * poi solo guidare. E' il modo di rendere il compito di A piu' impegnativo (richiesta del 10/10/2026). */
  function Deriva(seme) { this.r = rng((seme >>> 0) + 17); this.v = [0, 0, 0]; }
  /** Restituisce gli spostamenti [dTempo, dDensita, dMorbidezza] in unita' normalizzate 0..1. */
  Deriva.prototype.passo = function (dt, intensita) {
    var k = intensita == null ? CFG.derivaMusica : intensita, out = [0, 0, 0];
    if (!k) return out;
    for (var i = 0; i < 3; i++) {
      this.v[i] += -this.v[i] * dt / CFG.pesoMusicaDeriva + k * Math.sqrt(dt) * this.r.gauss();
      out[i] = this.v[i] * dt;
    }
    return out;
  };

  /* ---------- La partita ---------- */
  function Partita(opz) {
    opz = opz || {};
    this.durata = opz.durata || CFG.durataPartita;
    this.seme = (opz.seme == null ? (Date.now() & 0x7fffffff) : opz.seme) >>> 0;
    this.mondo = new Mondo(this.seme);
    this.t = 0;
    this.profondita = 0;
    this.x = 0;
    this.stordito = 0;          // secondi di stordimento rimasti
    this.turbo = false;
    this.finita = false;
    this.ultimo = { c: 0, stato: STATO.NEUTRO, tipo: TIPO.SOFFICE, sospeso: false, vel: 0 };
    this.st = {                 // statistiche
      tCoerente: 0, tNeutro: 0, tIncoerente: 0, tSospeso: 0, tTurbo: 0, tStordito: 0,
      urti: 0, sommaC: 0, tAttivo: 0, cambiTerreno: 0, gemme: 0, tDubbia: 0,
      tAmpiezza: 0, tAltaFreq: 0, urtiPerTipo: {}     // tAmpiezza / tAltaFreq: tempo scartato per ampiezza o per alte frequenze (muscoli)
    };
    this.serie = [];            // [t, profondita, coerenza, stato, tipo, qualita] una volta al secondo
    this._ts = 0;
    this._tipoPrec = null;
    this._rocceColpite = {};
    this.scia = [[0, 0]];       // percorso della talpa (per disegnare il tunnel)
  }

  /**
   * Avanza di dt secondi.
   * ingressi: { sterzo: -1..+1, turbo: bool, s: punteggio di B in [-1,+1], qualita: 'pulita'|'dubbia'|'scartata',
   *             motivo: '' | 'ampiezza' | 'alta_freq' | 'entrambi' (perche' la finestra e' stata scartata) }
   * Restituisce un elenco di eventi: 'urto', 'gemma', 'cambio', 'fine'.
   */
  Partita.prototype.passo = function (dt, ingressi) {
    var ev = [];
    if (this.finita) return ev;
    var inp = ingressi || {};
    var restante = this.durata - this.t;
    if (dt >= restante) { dt = restante; }
    this.turbo = !!inp.turbo;
    // il terreno sotto la talpa
    var tipo = this.mondo.tipoA(this.profondita + 0.3);
    if (this._tipoPrec !== null && tipo !== this._tipoPrec) { ev.push('cambio'); this.st.cambiTerreno++; }
    this._tipoPrec = tipo;
    // qualita' del segnale di B (V-11): se non e' pulita, nessun punto basato su quel segnale
    var qual = inp.qualita || QUALITA.PULITA;
    var sospeso = qual !== QUALITA.PULITA;
    var stato = sospeso ? STATO.ARTEFATTO : classificaStato(inp.s || 0);
    var c = sospeso ? 0 : coerenza(tipo, inp.s || 0);
    // sterzo
    this.x = clamp(this.x + clamp(inp.sterzo || 0, -1, 1) * CFG.velSterzo * dt, -0.95, 0.95);
    // discesa
    var vel = 0;
    if (this.stordito > 0) {
      this.stordito = Math.max(0, this.stordito - dt);
      this.st.tStordito += dt;
    } else if (!sospeso) {
      vel = velocita(c, this.turbo);
    }
    var prof0 = this.profondita;
    this.profondita += vel * dt;
    if (vel > 0 || this.stordito > 0) {
      var u = this.scia[this.scia.length - 1];
      if (this.profondita - u[1] >= 0.1) this.scia.push([this.x, this.profondita]);
    }
    // ostacoli e gemme (i mobili sono dove stanno adesso)
    var roc = this.mondo.rocceTra(prof0 - 0.4, this.profondita + 0.4);
    for (var i = 0; i < roc.length; i++) {
      var o = roc[i];
      if (this._rocceColpite[o.id]) continue;
      var ox = this.mondo.xDi(o, this.t);
      if (Math.abs(this.x - ox) < o.rx + CFG.larghezzaTalpa &&
          this.profondita + 0.3 > o.y - o.ry && prof0 < o.y + o.ry) {
        this._rocceColpite[o.id] = true;
        if (o.tipo === OSTACOLO.GEMMA) { this.st.gemme++; ev.push('gemma'); continue; }
        var pesante = o.tipo === OSTACOLO.MASSO || o.tipo === OSTACOLO.MURO;
        this.stordito = CFG.stordimento * (pesante ? 1.3 : 1) * (this.turbo ? CFG.moltStordTurbo : 1);
        this.profondita = Math.max(prof0, o.y - o.ry - 0.3);   // si ferma davanti all'ostacolo
        this.x = clamp(ox + (this.x >= ox ? 1 : -1) * (o.rx + CFG.larghezzaTalpa + 0.03), -0.95, 0.95);   // e viene spinta di lato
        this.st.urti++; this.st.urtiPerTipo[o.tipo] = (this.st.urtiPerTipo[o.tipo] || 0) + 1; ev.push('urto');
        break;
      }
    }
    // statistiche
    if (sospeso) {
      this.st.tSospeso += dt;
      var mot = inp.motivo || '';
      if (qual === QUALITA.DUBBIA) this.st.tDubbia += dt;
      if (mot === 'ampiezza' || mot === 'entrambi') this.st.tAmpiezza += dt;
      if (mot === 'alta_freq' || mot === 'entrambi') this.st.tAltaFreq += dt;
    } else {
      this.st.tAttivo += dt; this.st.sommaC += c * dt;
      if (c >= 0.5) this.st.tCoerente += dt; else if (stato === STATO.NEUTRO) this.st.tNeutro += dt; else this.st.tIncoerente += dt;
    }
    if (this.turbo) this.st.tTurbo += dt;
    this.t += dt;
    this.ultimo = { c: c, stato: stato, tipo: tipo, sospeso: sospeso, vel: vel };
    this._ts += dt;
    if (this._ts >= CFG.campionamentoSerie) {
      this._ts -= CFG.campionamentoSerie;
      this.serie.push([Math.round(this.t * 10) / 10, Math.round(this.profondita * 100) / 100, Math.round(c * 100) / 100, stato, tipo, qual]);
    }
    if (this.t >= this.durata - 1e-9) { this.finita = true; ev.push('fine'); }
    return ev;
  };

  Partita.prototype.punti = function () { return Math.floor(this.profondita * CFG.puntiPerMetro) + this.st.gemme * CFG.puntiPerGemma; };

  /** Riga da archiviare (V-04, V-05, V-06): solo dati di gioco, codici e nessun nome. */
  Partita.prototype.record = function (meta) {
    meta = meta || {};
    var st = this.st, att = st.tAttivo || 1e-9;
    return {
      id: meta.id || idCasuale(),
      versione: CFG.versione,
      data: meta.data || new Date().toISOString(),
      giocatoreA: meta.giocatoreA, giocatoreB: meta.giocatoreB,
      sorgente: meta.sorgente || 'simulata-manuale',      // vedi V-10: il simulato non si spaccia per vero
      simulata: meta.simulata !== false,
      durata: Math.round(this.t),
      durataPrevista: this.durata,
      seme: this.seme,
      profondita: Math.round(this.profondita * 100) / 100,
      punti: this.punti(),
      coerenzaMedia: Math.round((st.sommaC / att) * 1000) / 1000,
      tCoerente: Math.round(st.tCoerente), tNeutro: Math.round(st.tNeutro), tIncoerente: Math.round(st.tIncoerente),
      tSospeso: Math.round(st.tSospeso), tTurbo: Math.round(st.tTurbo),
      urti: st.urti, gemme: st.gemme,
      musica: meta.musica || null,                        // parametri medi (tempo, densita, morbidezza)
      serie: meta.conSerie === false ? null : this.serie.slice()
    };
  };

  /* ---------- Mente simulata (SOLO per prove e dimostrazioni, V-10) ----------
   * Modello giocattolo, NON scientifico: lo stato s insegue un bersaglio che dipende dalla musica
   * di A (ritmo lento/morbido/rado -> rilassato; veloce/secco/fitto -> concentrato), con inerzia e
   * rumore. Serve a far girare il gioco senza sensore; non dimostra nulla sul cervello. */
  var PERSONE = {
    tipica: { guadagno: 1.0, tau: 6, rumore: 0.10 },
    debole: { guadagno: 0.35, tau: 10, rumore: 0.16 },
    nulla: { guadagno: 0.0, tau: 4, rumore: 0.45 },
    manuale: { guadagno: 0.5, tau: 1.2, rumore: 0.02 }     // B governa con la tastiera: segue anche la musica, in piccola parte
  };
  function Mente(persona, seme) {
    this.persona = PERSONE[persona] ? persona : 'tipica';
    this.p = PERSONE[this.persona];
    this.s = 0;
    this.r = rng(seme == null ? 7 : seme);
  }
  /** Bersaglio dovuto alla musica: parametri in 0..1 (tempo normalizzato 60..140 -> 0..1). */
  Mente.bersaglioMusica = function (m) {
    var mt = (m.tempo - 0.5) * 2, mb = (0.5 - m.morbidezza) * 2, md = (m.densita - 0.5) * 2;   // timbro secco = come "chiaro"
    return Math.tanh(1.1 * mt + 0.9 * mb + 0.8 * md);
  };
  /** manuale: -1 (rilassati), 0, +1 (concentrati). */
  Mente.prototype.passo = function (dt, musica, manuale) {
    var target = this.p.guadagno * Mente.bersaglioMusica(musica);
    if (this.persona === 'manuale') target = clamp(target + 1.0 * (manuale || 0), -1, 1);
    this.s += (target - this.s) * (dt / this.p.tau) + this.p.rumore * Math.sqrt(dt) * this.r.gauss();
    this.s = clamp(this.s, -1, 1);
    return this.s;
  };

  /* ---------- Persone, validazione e archivio ---------- */
  var ID_PERSONA = /^P\d{2,3}$/;      // stesso schema di neurocontroller/profile.py (V-06)
  function codiceValido(c) { return typeof c === 'string' && ID_PERSONA.test(c); }

  function idCasuale() {
    var s = '', h = '0123456789abcdef';
    for (var i = 0; i < 16; i++) s += h[Math.floor(Math.random() * 16)];
    return 'g' + s;
  }

  var CAMPI_NUMERICI = ['durata', 'durataPrevista', 'profondita', 'punti', 'coerenzaMedia', 'tCoerente', 'tNeutro', 'tIncoerente', 'tSospeso', 'tTurbo', 'urti', 'seme', 'gemme'];
  var CAMPI_AMMESSI = ['id', 'versione', 'data', 'giocatoreA', 'giocatoreB', 'sorgente', 'simulata', 'musica', 'serie'].concat(CAMPI_NUMERICI);

  /** Controlla un record prima di archiviarlo. Rifiuta nomi e campi sconosciuti. Restituisce un elenco di errori. */
  function validaRecord(r) {
    var err = [];
    if (!r || typeof r !== 'object') return ['record non valido'];
    if (!codiceValido(r.giocatoreA)) err.push('giocatoreA: serve un codice tipo P01 (niente nomi)');
    if (!codiceValido(r.giocatoreB)) err.push('giocatoreB: serve un codice tipo P02 (niente nomi)');
    if (typeof r.id !== 'string' || !r.id) err.push('id mancante');
    if (typeof r.data !== 'string' || isNaN(Date.parse(r.data))) err.push('data non valida');
    if (typeof r.simulata !== 'boolean') err.push('simulata deve essere vero o falso (V-10)');
    CAMPI_NUMERICI.forEach(function (k) { if (typeof r[k] !== 'number' || !isFinite(r[k])) err.push(k + ' non numerico'); });
    Object.keys(r).forEach(function (k) { if (CAMPI_AMMESSI.indexOf(k) < 0) err.push('campo non ammesso: ' + k); });
    return err;
  }

  /** Statistiche di una persona (come A o come B). */
  function statistichePersona(partite, codice) {
    var mie = partite.filter(function (p) { return p.giocatoreA === codice || p.giocatoreB === codice; });
    var comeA = mie.filter(function (p) { return p.giocatoreA === codice; }).length;
    var comeB = mie.filter(function (p) { return p.giocatoreB === codice; }).length;
    var n = mie.length;
    var somma = function (f) { return mie.reduce(function (a, p) { return a + f(p); }, 0); };
    return {
      codice: codice, partite: n, comeA: comeA, comeB: comeB,
      migliore: n ? Math.max.apply(null, mie.map(function (p) { return p.profondita; })) : 0,
      media: n ? somma(function (p) { return p.profondita; }) / n : 0,
      coerenzaMedia: n ? somma(function (p) { return p.coerenzaMedia; }) / n : 0,
      urti: somma(function (p) { return p.urti; }), gemme: somma(function (p) { return p.gemme || 0; }),
      reali: mie.filter(function (p) { return !p.simulata; }).length,
      andamento: mie.slice().sort(function (a, b) { return a.data < b.data ? -1 : 1; }).map(function (p) { return p.profondita; })
    };
  }

  /** Classifica delle coppie A+B per profondita' massima. Solo partite con sorgente reale se soloReali. */
  function classificaCoppie(partite, n, soloReali) {
    var best = {};
    partite.forEach(function (p) {
      if (soloReali && p.simulata) return;
      var k = p.giocatoreA + '+' + p.giocatoreB;
      if (!best[k] || p.profondita > best[k].profondita) best[k] = { coppia: k, A: p.giocatoreA, B: p.giocatoreB, profondita: p.profondita, punti: p.punti, simulata: p.simulata, data: p.data };
    });
    return Object.keys(best).map(function (k) { return best[k]; })
      .sort(function (a, b) { return b.profondita - a.profondita; }).slice(0, n || 10);
  }

  /** CSV senza la serie (una riga per partita). */
  var COLONNE_CSV = ['id', 'data', 'giocatoreA', 'giocatoreB', 'sorgente', 'simulata', 'durata', 'durataPrevista', 'profondita', 'punti',
    'coerenzaMedia', 'tCoerente', 'tNeutro', 'tIncoerente', 'tSospeso', 'tTurbo', 'urti', 'gemme', 'seme', 'versione'];
  function aCSV(partite) {
    var righe = [COLONNE_CSV.join(',')];
    partite.forEach(function (p) {
      righe.push(COLONNE_CSV.map(function (k) {
        var v = p[k]; if (v == null) return '';
        v = String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
      }).join(','));
    });
    return righe.join('\n') + '\n';
  }

  function prossimoCodice(partite) {
    var max = 0;
    partite.forEach(function (p) {
      [p.giocatoreA, p.giocatoreB].forEach(function (c) { var m = /^P(\d+)$/.exec(c || ''); if (m) max = Math.max(max, +m[1]); });
    });
    var n = max + 1;
    return 'P' + (n < 10 ? '0' + n : String(n));
  }

  NC.core = {
    CFG: CFG, TIPO: TIPO, ORDINE_TIPI: ORDINE_TIPI, LIVELLO: LIVELLO, OSTACOLO: OSTACOLO, STATO: STATO, QUALITA: QUALITA, PERSONE: PERSONE,
    bersaglioTerreno: bersaglioTerreno, Deriva: Deriva,
    rng: rng, clamp: clamp,
    classificaStato: classificaStato, statoRichiesto: statoRichiesto, coerenza: coerenza, velocita: velocita,
    Mondo: Mondo, Partita: Partita, Mente: Mente,
    codiceValido: codiceValido, validaRecord: validaRecord, statistichePersona: statistichePersona,
    classificaCoppie: classificaCoppie, aCSV: aCSV, COLONNE_CSV: COLONNE_CSV, prossimoCodice: prossimoCodice, idCasuale: idCasuale
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = NC.core;
})(typeof window !== 'undefined' ? window : globalThis);
