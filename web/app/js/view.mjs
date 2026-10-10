// Disegno della partita (schermo di A): la talpa, gli strati di terreno (5 livelli), gli ostacoli, le gemme.
const PX_PER_M = 38, MOLE_Y = 150;
const LIV = { soffice: 0, morbido: 1, medio: 2, duro: 3, compatto: 4 };
const COLORI = ['#dcc08a', '#c4a272', '#9d8466', '#7a655a', '#5d5049'];
const NOME_TERRENO = { soffice: 'SOFFICE · serve B rilassato', morbido: 'MORBIDO · serve B un po\' rilassato', medio: 'MEDIO · serve B a metà (né l\'uno né l\'altro)',
  duro: 'DURO · serve B un po\' concentrato', compatto: 'COMPATTO · serve B concentrato' };

export function drawWorld(ctx, W, H, game, now) {
  const lane = W * 0.45, cx = W / 2, prof = game.profondita;
  const yOf = (d) => MOLE_Y + (d - prof) * PX_PER_M;
  ctx.clearRect(0, 0, W, H);
  // cielo e superficie
  const y0 = yOf(0);
  if (y0 > 0) { ctx.fillStyle = '#bfe3f5'; ctx.fillRect(0, 0, W, y0); ctx.fillStyle = '#6aa84f'; ctx.fillRect(0, y0 - 8, W, 8); }
  // strati
  const dMin = prof - MOLE_Y / PX_PER_M - 1, dMax = prof + (H - MOLE_Y) / PX_PER_M + 1;
  game.mondo.genera(dMax + 5);
  for (const s of game.mondo.strati) {
    if (s.a < dMin || s.da > dMax) continue;
    const top = Math.max(yOf(s.da), 0), bot = Math.min(yOf(s.a), H);
    const lv = LIV[s.tipo] == null ? 2 : LIV[s.tipo], soft = lv < 2, hard = lv > 2;
    ctx.fillStyle = COLORI[lv];
    ctx.fillRect(0, top, W, bot - top);
    ctx.save(); ctx.beginPath(); ctx.rect(0, top, W, bot - top); ctx.clip();
    ctx.strokeStyle = soft ? 'rgba(255,255,255,0.28)' : 'rgba(0,0,0,0.35)'; ctx.fillStyle = ctx.strokeStyle; ctx.lineWidth = 2;
    // il disegno cambia con il livello: puntini (soffice), puntini radi, onde (medio), righe larghe, righe fitte (compatto)
    if (lv === 0 || lv === 1) { const passo = lv === 0 ? 22 : 34; for (let y = top - (top % passo); y < bot; y += passo) for (let x = (y / passo % 2) * (passo / 2); x < W; x += passo) { ctx.beginPath(); ctx.arc(x + 6, y + 6, 2, 0, 6.3); ctx.fill(); } }
    else if (lv === 2) { for (let y = top - (top % 30); y < bot; y += 30) { ctx.beginPath(); for (let x = 0; x <= W; x += 12) { const yy = y + Math.sin(x / 18) * 4; if (x) ctx.lineTo(x, yy); else ctx.moveTo(x, yy); } ctx.stroke(); } }
    else { const passo = lv === 3 ? 40 : 26; for (let k = -H; k < W + H; k += passo) { ctx.beginPath(); ctx.moveTo(k, bot); ctx.lineTo(k + (bot - top), top); ctx.stroke(); } }
    ctx.restore();
    // etichetta (testo, non solo colore: V-20)
    const ly = Math.max(top, 0) + 18;
    if (ly < bot - 6) {
      ctx.font = 'bold 15px system-ui, sans-serif'; ctx.textAlign = 'left';
      const txt = 'TERRENO ' + (NOME_TERRENO[s.tipo] || s.tipo);
      ctx.fillStyle = 'rgba(0,0,0,0.55)'; const w = ctx.measureText(txt).width + 16; ctx.fillRect(8, ly - 15, w, 22);
      ctx.fillStyle = '#fff'; ctx.fillText(txt, 16, ly);
    }
    ctx.strokeStyle = 'rgba(0,0,0,0.5)'; ctx.setLineDash([8, 6]); ctx.beginPath(); ctx.moveTo(0, yOf(s.da)); ctx.lineTo(W, yOf(s.da)); ctx.stroke(); ctx.setLineDash([]);
  }
  // tunnel scavato
  if (game.scia.length > 1) {
    ctx.strokeStyle = '#2a1d12'; ctx.lineWidth = lane * 0.075 * 2; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.beginPath();
    game.scia.forEach(([x, d], i) => { const px = cx + x * lane, py = yOf(d); if (i) ctx.lineTo(px, py); else ctx.moveTo(px, py); });
    ctx.lineTo(cx + game.x * lane, MOLE_Y); ctx.stroke();
  }
  // ostacoli e gemme
  for (const o of game.mondo.rocceTra(dMin, dMax)) {
    const ox = game.mondo.xDi(o, game.t), px = cx + ox * lane, py = yOf(o.y), rx = o.rx * lane, ry = o.ry * PX_PER_M;
    if (o.tipo === 'gemma') {
      if (game._rocceColpite[o.id]) continue;
      ctx.fillStyle = '#35e0d0'; ctx.strokeStyle = '#0b6b64'; ctx.lineWidth = 2; ctx.beginPath();
      ctx.moveTo(px, py - 13); ctx.lineTo(px + 11, py); ctx.lineTo(px, py + 13); ctx.lineTo(px - 11, py); ctx.closePath(); ctx.fill(); ctx.stroke();
      continue;
    }
    if (o.tipo === 'muro') {
      ctx.fillStyle = '#3a3a40'; ctx.fillRect(px - rx, py - ry, 2 * rx, 2 * ry);
      ctx.fillStyle = 'rgba(255,255,255,0.12)'; ctx.fillRect(px - rx, py - ry, 2 * rx, 5);
      continue;
    }
    ctx.fillStyle = o.tipo === 'mobile' ? '#8a3b3b' : o.tipo === 'masso' ? '#46464d' : '#2b2b2f';
    ctx.beginPath(); ctx.ellipse(px, py, rx, ry, 0, 0, 6.3); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.18)'; ctx.beginPath(); ctx.ellipse(px - rx * 0.3, py - ry * 0.35, rx * 0.4, ry * 0.25, 0, 0, 6.3); ctx.fill();
    if (o.tipo === 'mobile') { ctx.fillStyle = '#fff'; ctx.font = 'bold 14px system-ui'; ctx.textAlign = 'center'; ctx.fillText('↔', px, py + 5); }
  }
  // talpa
  const mx = cx + game.x * lane;
  const st = game.stordito > 0, shake = st ? Math.sin(now / 40) * 3 : 0;
  ctx.save(); ctx.translate(mx + shake, MOLE_Y);
  if (game.turbo && !st) { ctx.strokeStyle = '#ffd24a'; ctx.lineWidth = 3; for (let i = -1; i <= 1; i++) { ctx.beginPath(); ctx.moveTo(i * 10, -26); ctx.lineTo(i * 10, -26 - 14 - Math.random() * 10); ctx.stroke(); } }
  ctx.fillStyle = '#4b3b34'; ctx.beginPath(); ctx.ellipse(0, 0, 22, 27, 0, 0, 6.3); ctx.fill();         // corpo
  ctx.fillStyle = '#e8a8b0'; ctx.beginPath(); ctx.ellipse(0, 24, 9, 8, 0, 0, 6.3); ctx.fill();        // muso (verso il basso)
  ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(-9, 8, 4, 0, 6.3); ctx.arc(9, 8, 4, 0, 6.3); ctx.fill();
  ctx.fillStyle = '#111'; ctx.beginPath(); ctx.arc(-9, 9, 1.8, 0, 6.3); ctx.arc(9, 9, 1.8, 0, 6.3); ctx.fill();
  ctx.strokeStyle = '#e8a8b0'; ctx.lineWidth = 6; ctx.lineCap = 'round';                               // zampe-pala
  const sw = game.ultimo.vel > 0 ? Math.sin(now / 70) * 5 : 0;
  ctx.beginPath(); ctx.moveTo(-20, 14); ctx.lineTo(-30, 24 + sw); ctx.moveTo(20, 14); ctx.lineTo(30, 24 - sw); ctx.stroke();
  ctx.restore();
  if (st) { ctx.font = 'bold 22px system-ui'; ctx.textAlign = 'center'; ctx.fillStyle = '#ffd24a'; ctx.fillText('✦ ✦ ✦', mx, MOLE_Y - 40); }
  // indicatore di profondita'
  ctx.textAlign = 'right'; ctx.font = 'bold 16px system-ui'; ctx.fillStyle = 'rgba(0,0,0,0.6)';
  for (let m = Math.ceil(dMin / 5) * 5; m < dMax; m += 5) { if (m <= 0) continue; ctx.fillText(m + ' m', W - 8, yOf(m) - 3); }
}

// Vista "sotto il cofano": onda grezza, barre delle bande, punteggio di B.
export function drawScope(ctx, W, H, onda, ultimo) {
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#10161c'; ctx.fillRect(0, 0, W, H);
  if (onda.length > 2) {
    let lo = Infinity, hi = -Infinity; for (const v of onda) { if (v < lo) lo = v; if (v > hi) hi = v; }
    const mid = (lo + hi) / 2, span = Math.max(40, hi - lo);
    ctx.strokeStyle = '#6fe0a8'; ctx.lineWidth = 1.2; ctx.beginPath();
    onda.forEach((v, i) => { const x = i / (onda.length - 1) * W, y = 56 - (v - mid) / span * 90; if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y); });
    ctx.stroke();
  }
  ctx.fillStyle = '#9fb3c4'; ctx.font = '11px system-ui'; ctx.textAlign = 'left'; ctx.fillText('segnale (ultimi 3 s)', 6, 12);
  if (ultimo && ultimo.rel) {
    const nomi = ['delta', 'theta', 'alpha', 'beta', 'gamma'], et = ['δ', 'θ', 'α', 'β', 'γ'], col = ['#7a8aa0', '#9b7fd1', '#4fb3d9', '#f2a541', '#e86a6a'];
    nomi.forEach((n, i) => {
      const h = Math.min(1, ultimo.rel[n] * 1.6) * 56, x = 10 + i * 40;
      ctx.fillStyle = col[i]; ctx.fillRect(x, H - 16 - h, 28, h);
      ctx.fillStyle = '#cfd8e3'; ctx.fillText(et[i], x + 10, H - 4);
    });
  }
}
