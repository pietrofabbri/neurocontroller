// Archivio dei dati di gioco. Due modi, scelti da soli (V-04: nulla esce dal computer in entrambi):
//  - 'server': server locale (python3 -m neurocontroller serve) con database SQLite;
//  - 'browser': sito statico pubblicato (nessun server): le partite restano nel browser di chi gioca.
import { ArchivioLocale } from './archivio_locale.mjs';

let modo = null, locale = null;

async function chiama(metodo, percorso, corpo) {
  const opz = { method: metodo, headers: {} };
  if (corpo !== undefined) { opz.headers['Content-Type'] = 'application/json'; opz.body = JSON.stringify(corpo); }
  const r = await fetch(percorso, opz);
  const testo = await r.text();
  let dati = null;
  try { dati = testo ? JSON.parse(testo) : null; } catch (e) { dati = null; }
  if (!r.ok) throw new Error((dati && dati.error) || ('errore ' + r.status));
  return dati;
}

export async function rileva() {
  if (modo) return modo;
  try {
    const r = await fetch('/api/health', { cache: 'no-store' });
    const d = r.ok ? await r.json() : null;
    modo = d && d.ok ? 'server' : 'browser';
  } catch (e) { modo = 'browser'; }
  if (modo === 'browser') {
    let st = null;
    try { st = window.localStorage; st.getItem('x'); } catch (e) { st = null; }
    if (!st) { const m = new Map(); st = { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, v) }; modo = 'browser-volatile'; }
    locale = new ArchivioLocale(st);
  }
  return modo;
}
export const modoAttuale = () => modo;
const L = async (f) => { await rileva(); return f(locale); };
const srv = () => modo === 'server';

export const giocatori = async () => { await rileva(); return srv() ? (await chiama('GET', '/api/players')).players : locale.giocatori(); };
export const nuovoGiocatore = async (code) => { await rileva(); return srv() ? chiama('POST', '/api/players', code ? { code } : {}) : locale.nuovoGiocatore(code); };
export const aggiornaGiocatore = async (code, dati) => { await rileva(); return srv() ? chiama('PUT', '/api/players/' + encodeURIComponent(code), dati) : locale.aggiornaGiocatore(code, dati); };
export const cancellaGiocatore = async (code) => { await rileva(); return srv() ? chiama('DELETE', '/api/players/' + encodeURIComponent(code)) : locale.cancellaGiocatore(code); };
export const salvaPartita = async (g) => { await rileva(); return srv() ? (await chiama('POST', '/api/games', g)).id : locale.salvaPartita(g); };
export const partite = async (player, limit = 10) => { await rileva(); return srv()
  ? (await chiama('GET', '/api/games?limit=' + limit + (player ? '&player=' + encodeURIComponent(player) : ''))).games : locale.partite(player, limit); };
export const classifica = async (limit = 10) => { await rileva(); return srv() ? (await chiama('GET', '/api/leaderboard?limit=' + limit)).games : locale.classifica(limit); };
export const serie = async (id) => { await rileva(); return srv() ? (await chiama('GET', '/api/games/' + id + '/series')).series : locale.serie(id); };
export const csvTesto = async () => { await rileva(); return srv() ? (await fetch('/api/export.csv')).text() : locale.csv(); };
export const csvSerieTesto = async () => { await rileva(); return srv() ? (await fetch('/api/export-series.csv')).text() : locale.csvSerie(); };
void L;
