// Disegno della partita (schermo di A): la talpa, gli strati di terreno, le rocce.
const PX_PER_M = 38, MOLE_Y = 150;

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
    const soft = s.tipo === 'soffice';
    ctx.fillStyle = soft ? '#d8b77a' : '#5d5049';
    ctx.fillRect(0, top, W, bot - top);
    ctx.save(); ctx.beginPath(); ctx.rect(0, top, W, bot - top); ctx.clip();
    ctx.strokeStyle = soft ? 'rgba(255,255,255,0.28)' : 'rgba(0,0,0,0.35)'; ctx.fillStyle = ctx.strokeStyle; ctx.lineWidth = 2;
    if (soft) { for (let y = top - (top % 22); y < bot; y += 22) for (let x = (y / 22 % 2) * 11; x < W; x += 22) { ctx.beginPath(); ctx.arc(x + 6, y + 6, 2, 0, 6.3); ctx.fill(); } }
    else { for (let k = -H; k < W + H; k += 26) { ctx.beginPath(); ctx.moveTo(k, bot); ctx.lineTo(k + (bot - top), top); ctx.stroke(); } }
    ctx.restore();
    // etichetta (testo, non solo colore: V-20)
    const ly = Math.max(top, 0) + 18;
    if (ly < bot - 6) {
      ctx.font = 'bold 15px system-ui, sans-serif'; ctx.textAlign = 'left';
      const txt = soft ? 'TERRENO SOFFICE · serve B rilassato' : 'TERRENO COMPATTO · serve B concentrato';
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
  // rocce
  for (const o of game.mondo.rocceTra(dMin, dMax)) {
    const px = cx + o.x * lane, py = yOf(o.y);
    ctx.fillStyle = '#2b2b2f'; ctx.beginPath(); ctx.ellipse(px, py, o.rx * lane, o.ry * PX_PER_M, 0, 0, 6.3); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.18)'; ctx.beginPath(); ctx.ellipse(px - o.rx * lane * 0.3, py - o.ry * PX_PER_M * 0.35, o.rx * lane * 0.4, o.ry * PX_PER_M * 0.25, 0, 0, 6.3); ctx.fill();
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
