"""Genera i vettori di riferimento per la parita' Python/JavaScript (V-18).

Segnali SINTETICI e deterministici (nessun dato fisiologico). Uso:
    python3 tools/genera_vettori_web.py            # riscrive web/app/test/vettori.json
Il test web/app/test/parita.test.js confronta il JavaScript con questi numeri.
"""
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from neurocontroller import dsp, profile as prof  # noqa: E402


def lcg(seed):
    s = seed
    while True:
        s = (1103515245 * s + 12345) % 2 ** 31
        yield s / 2 ** 31 - 0.5


def segnale(n, fs, seed, comp, rumore=2.0, jaw=0.0):
    g = lcg(seed)
    out = []
    for i in range(n):
        t = i / fs
        v = sum(a * math.sin(2 * math.pi * f * t + ph) for f, a, ph in comp)
        v += rumore * next(g) * 3.46 + jaw * (next(g) - next(g)) * 8
        out.append(512 + v)
    return out


def finestre():
    casi = []
    base = [(2.0, 6, 0.3), (6.0, 4, 1.1), (10.0, 8, 2.0), (20.0, 4, 0.5), (36.0, 1, 0.9)]
    alto = [(2.0, 5, 0.3), (6.0, 4, 1.1), (10.0, 4, 2.0), (20.0, 8, 0.5), (36.0, 2, 0.9)]
    for nome, n, fs, seed, comp, jaw in [
        ("riposo_512_250", 512, 250.0, 11, base, 0.0),
        ("calcolo_512_250", 512, 250.0, 12, alto, 0.0),
        ("mascella_512_250", 512, 250.0, 13, alto, 6.0),
        ("corta_256_250", 256, 250.0, 14, base, 0.0),
        ("lenta_256_100", 256, 100.0, 15, base[:4], 0.0),
    ]:
        x = [round(v, 6) for v in segnale(n, fs, seed, comp, jaw=jaw)]
        f, _, _ = dsp.analyze_window(x, fs)
        casi.append({"nome": nome, "fs": fs, "x": x, "atteso": f.to_dict()})
    return casi


def classificatore():
    g = lcg(99)

    def feat(e, rms, hf):
        return {"engagement": e, "rms": rms, "hfRatio": hf}

    rilassato = [feat(-0.9 + 0.3 * next(g), 9 + 2 * next(g), 0.02 + 0.01 * next(g)) for _ in range(40)]
    concentrato = [feat(0.1 + 0.3 * next(g), 10 + 2 * next(g), 0.03 + 0.01 * next(g)) for _ in range(40)]
    # qualche disturbo: devono essere scartati nel calcolo del profilo
    rilassato += [feat(0.0, 80.0, 0.02), feat(0.0, 9.0, 0.5)]
    pulite = rilassato + concentrato
    rf, rthr, rmed = prof._pick_factor([f["rms"] for f in pulite], prof.RMS_FACTORS, prof.MAX_FALSE_ALARM / 2)
    hf, hthr, hmed = prof._pick_factor([f["hfRatio"] for f in pulite], prof.HF_FACTORS, prof.MAX_FALSE_ALARM / 2)
    art = {"rms_thr": rthr, "hf_thr": hthr}
    ok = lambda f: not prof.is_artifact(f["rms"], f["hfRatio"], art)  # noqa: E731
    er = [f["engagement"] for f in rilassato if ok(f)]
    ef = [f["engagement"] for f in concentrato if ok(f)]
    mr, sr = prof._mean_std(er)
    mf, sf = prof._mean_std(ef)
    thr, dp = prof._decision(mr, sr, mf, sf)
    stato = {"relax_mean": mr, "relax_std": sr, "focus_mean": mf, "focus_std": sf, "threshold": thr, "dprime": dp}
    profilo = SimpleNamespace(state=stato, artifact=art)
    clf = prof.StateClassifier(profilo)
    seq = []
    for e, r, h in [(-1.0, 9, .02), (-0.9, 9, .02), (-0.4, 9, .02), (-0.2, 9, .02), (0.0, 9, .02), (0.2, 10, .03),
                    (0.3, 10, .03), (0.4, 99, .03), (0.4, 10, .03), (0.5, 10, .9), (0.3, 10, .03), (-0.9, 9, .02)]:
        r_ = clf.update(SimpleNamespace(engagement=e, rms=r, hf_ratio=h))
        seq.append({"in": feat(e, r, h), "state": r_.state, "score": r_.score})
    return {"rilassato": rilassato, "concentrato": concentrato,
            "fattori": {"rms": [rf, rthr, rmed], "hf": [hf, hthr, hmed]},
            "profilo": {"artifact": art, "state": stato}, "sequenza": seq}


if __name__ == "__main__":
    out = ROOT / "web" / "app" / "test" / "vettori.json"
    out.write_text(json.dumps({"finestre": finestre(), "classificatore": classificatore()}, separators=(",", ":")), encoding="utf-8")
    print("scritto", out, out.stat().st_size, "byte")
