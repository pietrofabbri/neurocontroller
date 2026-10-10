"""Prova di una partita lampo (20 s) nel browser, con server e database temporanei.

Richiede Playwright con Chromium (non e' una dipendenza del progetto). Uso:
    python3 tools/prova_web_e2e.py [cartella-per-gli-screenshot] [--statico]
--statico: serve web/app con un semplice server di file (senza API), come sul sito pubblicato:
le partite si salvano nel browser.
Esce con codice diverso da 0 se la partita non finisce, non si salva o compaiono errori nel browser.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = "8799"


def main() -> int:
    from playwright.sync_api import sync_playwright
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    statico = "--statico" in sys.argv
    out = Path(args[0]) if args else None
    exe = os.environ.get("CHROMIUM", "/opt/pw-browsers/chromium")
    errs = []
    with tempfile.TemporaryDirectory() as tmp:
        cmd = ([sys.executable, "-m", "http.server", PORT, "--bind", "127.0.0.1", "--directory", str(ROOT / "web" / "app")]
               if statico else [sys.executable, "-m", "neurocontroller", "serve", "--data-dir", tmp, "--port", PORT])
        srv = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(1.5)
            with sync_playwright() as p:
                b = p.chromium.launch(executable_path=exe if Path(exe).exists() else None,
                                      args=["--autoplay-policy=no-user-gesture-required"])
                pg = b.new_page(viewport={"width": 1280, "height": 900})
                pg.on("console", lambda m: errs.append(m.text) if m.type in ("error", "warning") and not (statico and "404" in m.text) else None)
                pg.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)))
                pg.goto("http://localhost:%s/" % PORT)
                # scheda del partecipante: solo risposte a scelta, consenso esplicito
                pg.click("#newA"); pg.wait_for_timeout(300); pg.click("#newB"); pg.wait_for_timeout(300)
                pg.click("#schedaA")
                pg.wait_for_selector("#scheda[open]")
                pg.fill("#sc-eta", "17"); pg.select_option("#sc-genere", "donna"); pg.select_option("#sc-gaming", "1-3h")
                pg.check("#sc-consenso"); pg.select_option("#sc-da", "genitore_tutore")
                pg.click("#sc-salva"); pg.wait_for_timeout(500)
                ok = pg.evaluate("document.getElementById('scheda').open") is False
                print("scheda salvata e chiusa:", ok)
                pg.select_option("#durata", "20")
                pg.click("#condizioni summary"); pg.fill("#c-sonno", "7"); pg.select_option("#c-caffe", "0"); pg.select_option("#c-stanchezza", "2")
                pg.click("#avvia")
                pg.wait_for_selector("#gioco:not([hidden])")
                # tre cursori e nessuna scorciatoia di preset
                tre = pg.evaluate("[...document.querySelectorAll('#gioco input[type=range]')].map(e => e.id).filter(i => i.startsWith('r-'))")
                print("cursori di A:", tre)
                ok = ok and tre == ["r-tempo", "r-densita", "r-morbidezza"] and pg.query_selector("[data-preset]") is None
                pg.wait_for_timeout(3000)
                pg.keyboard.press("q")
                liv = pg.inner_text("#h-livello")
                ok = ok and "di 5" in liv and pg.inner_text("#h-terreno") in ("SOFFICE", "MORBIDO", "MEDIO", "DURO", "COMPATTO")
                print("terreno:", pg.inner_text("#h-terreno"), liv)
                # la deriva muove i cursori da sola
                v0 = pg.evaluate("window.__S.music.p.tempo + window.__S.music.p.densita * 100 + window.__S.music.p.morbidezza * 100")
                pg.wait_for_timeout(4000)
                v1 = pg.evaluate("window.__S.music.p.tempo + window.__S.music.p.densita * 100 + window.__S.music.p.morbidezza * 100")
                ok = ok and abs(v1 - v0) > 0.01
                print("deriva dei cursori:", round(v0, 2), "->", round(v1, 2))
                if out:
                    pg.screenshot(path=str(out / "gioco.png"))
                pg.wait_for_selector("#fine:not([hidden])", timeout=60000)
                pg.wait_for_timeout(800)
                msg = pg.inner_text("#f-salvataggio")
                print("salvataggio:", msg)
                ok = ok and "Salvata" in msg and (("browser" in msg) == statico)
                if out:
                    pg.screenshot(path=str(out / "fine.png"))
                righe = pg.evaluate("""async () => (window.__S.riga ? { v: window.__S.riga.app_version, fs: window.__S.riga.signal_fs_hz, sl: window.__S.riga.b_sleep_h,
                    caf: window.__S.riga.b_caffeine_3h, fat: window.__S.riga.b_fatigue, prot: window.__S.riga.calib_protocol, tipi: [...new Set(window.__S.serie.map(r => r.terrain))],
                    kp: Object.keys(window.__S.serie[0]).join(',') } : null)""")
                print("record:", righe)
                ok = ok and righe and righe["v"] == "W0.2" and righe["sl"] == 7 and righe["caf"] == 0 and righe["fat"] == 2 and righe["prot"] == "simulata-rapida"
                ok = ok and righe["kp"] == "t,depth_m,terrain,state,score_b,quality,coherence,tempo,density,softness,reason"
                pg.click("#f-home")
                pg.wait_for_timeout(800)
                classifica = pg.inner_text("#classifica")
                print("classifica:", classifica)
                ok = ok and " m" in classifica
                if statico:
                    pg.reload(); pg.wait_for_timeout(800)
                    ok = ok and " m" in pg.inner_text("#classifica")      # i dati sopravvivono alla ricarica
                    print("dopo la ricarica:", pg.inner_text("#classifica"))
                b.close()
        finally:
            srv.terminate()
    print("errori nel browser:", errs or "nessuno")
    return 0 if ok and not errs else 1


if __name__ == "__main__":
    sys.exit(main())
