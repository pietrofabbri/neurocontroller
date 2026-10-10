"""Prova del flusso 'sensore' nel browser con una porta seriale FINTA (nessun hardware).

La porta finta parla il protocollo del firmware (WHORU/START, pacchetti binari C7 7C ... 01) a 250 campioni/s con un segnale sintetico il cui stato (rilassato /
concentrato) e' deciso dallo script. Verifica collegamento, controllo, calibrazione, partita e salvataggio
con sorgente 'sensore'. NON prova nulla sul sensore vero. Richiede Playwright con Chromium (facoltativo).
Uso: python3 tools/prova_web_sensore.py [cartella-screenshot] [--ascii]\n--ascii: simula lo sketch a righe di testo a 9600 baud (a 115200 la porta restituisce solo zeri), come il sensore\ndel docente il 9/10/2026; la pagina deve riconoscere da sola formato e baud.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = "8798"

MOCK = r"""
(() => {
  const ASCII = %ASCII%; let baud = 0; const fs = ASCII ? 193 : 250; let n = 0, t0 = null; window.__mockMind = 0.5; window.__mockJaw = 0;
  let seed = 12345; const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  const gauss = () => Math.sqrt(-2 * Math.log(Math.max(rnd(), 1e-12))) * Math.cos(2 * Math.PI * rnd());
  const ph = Array.from({ length: 16 }, () => rnd() * 6.283);
  const amp = (u) => ({ d: 5 + 0 * u, th: 4.5, a: 8.5 - 3.5 * u, b: 3 + 3.5 * u });
  function sample() {
    const t = n / fs, A = amp(window.__mockMind); let v = 0;
    v += A.d * Math.sin(6.283 * 2.5 * t + ph[0]) + A.th * Math.sin(6.283 * 6 * t + ph[1]) + A.a * Math.sin(6.283 * 10 * t + ph[2]);
    v += A.b * (Math.sin(6.283 * 18 * t + ph[3]) + Math.sin(6.283 * 24 * t + ph[4])) / 1.4;
    v += gauss() * 2 + Math.sin(6.283 * 50 * t) + 10 * Math.sin(6.283 * 0.2 * t);
    if (window.__mockJaw > 0) { v += gauss() * 40; window.__mockJaw--; }
    n++; return Math.max(0, Math.min(1023, Math.round(512 + v)));
  }
  let started = false, outq = [];
  const enc = (str) => new TextEncoder().encode(str);
  function packet() {
    const p = new Uint8Array(16); p[0] = 0xC7; p[1] = 0x7C; p[2] = n & 255;
    for (let c = 0; c < 6; c++) { const v = c === 0 ? sample() : 512 + Math.round(gauss()); p[3 + 2 * c] = v >> 8; p[4 + 2 * c] = v & 255; }
    p[15] = 1; return p;
  }
  const port = {
    async open(o) { baud = o.baudRate; }, async close() {},
    writable: { getWriter() { return {
      async write(bytes) {
        const t = new TextDecoder().decode(bytes).trim().toUpperCase();
        if (t === 'WHORU') outq.push(enc('UNO-CLONE\r\n'));
        else if (t === 'START') { started = true; t0 = null; }
        else if (t === 'STOP') started = false;
      }, releaseLock() {} }; } },
    readable: { getReader() { let closed = false; return {
      async read() {
        if (ASCII) {
          if (baud !== 9600) { await new Promise((r) => setTimeout(r, 20)); return { value: new Uint8Array(100), done: closed }; }   // zeri
          if (t0 === null) t0 = performance.now();
          const due = t0 + (n + 8) / fs * 1000, wait = due - performance.now();
          if (wait > 0) await new Promise((r) => setTimeout(r, wait));
          let txt = ''; for (let i = 0; i < 8; i++) txt += sample() + '\r\n';
          return { value: enc(txt), done: closed };
        }
        if (outq.length) return { value: outq.shift(), done: false };
        if (!started) { await new Promise((r) => setTimeout(r, 30)); return { value: new Uint8Array(0), done: closed }; }
        if (t0 === null) t0 = performance.now();
        const due = t0 + (n + 10) / fs * 1000, wait = due - performance.now();
        if (wait > 0) await new Promise((r) => setTimeout(r, wait));
        const out = new Uint8Array(160); for (let i = 0; i < 10; i++) out.set(packet(), i * 16);
        return { value: out, done: closed };
      },
      async cancel() { closed = true; }, releaseLock() {} }; } },
  };
  Object.defineProperty(navigator, 'serial', { value: { requestPort: async () => port }, configurable: true });
  Object.defineProperty(navigator, 'getBattery', { value: async () => ({ charging: false, level: 0.9 }), configurable: true });
})();
"""


def main() -> int:
    from playwright.sync_api import sync_playwright
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ascii_mode = "--ascii" in sys.argv
    out = Path(args[0]) if args else None
    exe = os.environ.get("CHROMIUM", "/opt/pw-browsers/chromium")
    errs, ok = [], False
    with tempfile.TemporaryDirectory() as tmp:
        srv = subprocess.Popen([sys.executable, "-m", "neurocontroller", "serve", "--data-dir", tmp, "--port", PORT],
                               cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(1.5)
            with sync_playwright() as p:
                b = p.chromium.launch(executable_path=exe if Path(exe).exists() else None,
                                      args=["--autoplay-policy=no-user-gesture-required"])
                pg = b.new_page(viewport={"width": 1280, "height": 900})
                pg.add_init_script(MOCK.replace("%ASCII%", "true" if ascii_mode else "false"))
                pg.on("console", lambda m: errs.append(m.text) if m.type in ("error", "warning") else None)
                pg.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)))
                pg.goto("http://localhost:%s/?calib=14" % PORT)
                pg.wait_for_timeout(500)
                pg.select_option("#sorgente", "sensore")
                pg.select_option("#durata", "20")
                pg.select_option("#sorgente", "sensore")
                pg.click("#avvia")                      # crea due giocatori, ma senza consenso il sensore non parte
                pg.wait_for_selector("#scheda[open]", timeout=5000)
                print("senza consenso la scheda si apre da sola:", pg.inner_text("#home-msg"))
                for lato in ("A", "B"):
                    if not pg.evaluate("document.getElementById('scheda').open"):
                        pg.click("#scheda" + lato); pg.wait_for_selector("#scheda[open]")
                    pg.check("#sc-consenso"); pg.select_option("#sc-da", "persona"); pg.click("#sc-salva"); pg.wait_for_timeout(500)
                pg.select_option("#durata", "20")
                pg.click("#avvia")
                pg.wait_for_selector("#sensore:not([hidden])")
                pg.check("#s-ok")
                pg.click("#s-collega")
                pg.wait_for_selector("#s-calibra:not([hidden])", timeout=20000)
                print("controllo:", pg.inner_text("#s-check")[:260].replace("\n", " "))
                if ascii_mode and "formato testo" not in pg.inner_text("#s-check"):
                    print("ERRORE: formato testo non riconosciuto")
                    return 1
                pg.click("#s-calibra")
                for _ in range(4):                      # quattro blocchi: l'istruzione dice se rilassarsi o calcolare
                    pg.wait_for_function("document.getElementById('s-tempo').textContent.startsWith('Preparati')", timeout=30000)
                    titolo = pg.inner_text("#s-blocco")
                    mind = 0 if "Rilassamento" in titolo else 1
                    pg.evaluate("m => window.__mockMind = m", mind)
                    pg.wait_for_function("!document.getElementById('s-tempo').textContent.startsWith('Preparati')", timeout=15000)
                    pg.wait_for_function("document.getElementById('s-tempo').textContent.startsWith('Preparati') || !document.getElementById('s-esito').hidden || document.getElementById('s-calib').hidden", timeout=40000)
                pg.wait_for_selector("#s-esito:not([hidden])", timeout=20000)
                esito = pg.inner_text("#s-esito")
                print("esito:", esito[:200].replace("\n", " "))
                if out:
                    pg.screenshot(path=str(out / "sensore.png"))
                ok = "profilo affidabile" in esito
                if ok:
                    pg.evaluate("window.__mockMind = 1")
                    pg.click("#s-gioca")
                    pg.wait_for_selector("#fine:not([hidden])", timeout=60000)
                    pg.wait_for_timeout(800)
                    msg = pg.inner_text("#f-salvataggio")
                    print("salvataggio:", msg, "|", pg.inner_text("#f-titolo"))
                    ok = "Salvata" in msg and "simulato" not in pg.inner_text("#f-titolo")
                    r = pg.evaluate("({ fmt: window.__S.riga.sensor_format, baud: window.__S.riga.sensor_baud, fs: window.__S.riga.signal_fs_hz, lv: window.__S.riga.profile_level, pr: window.__S.riga.calib_protocol, src: window.__S.riga.source, raw: !document.getElementById('f-raw').hidden })")
                    print("record sensore:", r)
                    ok = ok and r["fmt"] == ("ascii" if ascii_mode else "chords") and r["lv"] == "affidabile" and r["pr"] == "web-v1-30s" and r["src"] == "sensore" and r["raw"] and r["fs"] > 100
                    if out:
                        pg.screenshot(path=str(out / "sensore-fine.png"))
                b.close()
        finally:
            srv.terminate()
    print("errori nel browser:", errs or "nessuno")
    return 0 if ok and not errs else 1


if __name__ == "__main__":
    sys.exit(main())
