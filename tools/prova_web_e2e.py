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
                pg.select_option("#durata", "20")
                pg.click("#avvia")
                pg.wait_for_selector("#gioco:not([hidden])")
                pg.wait_for_timeout(3000)
                pg.keyboard.press("1")
                if out:
                    pg.screenshot(path=str(out / "gioco.png"))
                pg.wait_for_selector("#fine:not([hidden])", timeout=60000)
                pg.wait_for_timeout(800)
                msg = pg.inner_text("#f-salvataggio")
                print("salvataggio:", msg)
                ok = "Salvata" in msg and (("browser" in msg) == statico)
                if out:
                    pg.screenshot(path=str(out / "fine.png"))
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
