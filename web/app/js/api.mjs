// Comunicazione con il server locale (stessa origine, solo localhost). Nessun dato esce dal computer (V-04).
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
export const giocatori = () => chiama('GET', '/api/players').then((d) => d.players);
export const nuovoGiocatore = (code) => chiama('POST', '/api/players', code ? { code } : {});
export const cancellaGiocatore = (code) => chiama('DELETE', '/api/players/' + encodeURIComponent(code));
export const salvaPartita = (g) => chiama('POST', '/api/games', g).then((d) => d.id);
export const partite = (player, limit = 10) => chiama('GET', '/api/games?limit=' + limit + (player ? '&player=' + encodeURIComponent(player) : '')).then((d) => d.games);
export const classifica = (limit = 10) => chiama('GET', '/api/leaderboard?limit=' + limit).then((d) => d.games);
export const serie = (id) => chiama('GET', '/api/games/' + id + '/series').then((d) => d.series);
