"""print speech runs (start-end, seconds of pause before) for source ranges: python runs.py 17:02-17:16 ..."""
import sys, numpy as np, soundfile as sf
from common import A16, T, F
x, sr = sf.read(A16)
for r in sys.argv[1:]:
    a, b = [T(v) for v in r.split("-")]
    a0, b0 = max(0, a - 3), b + 3
    seg = x[int(a0 * sr):int(b0 * sr)]; hop = int(0.01 * sr); n = len(seg) // hop
    rms = np.sqrt(np.mean(seg[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    db = np.convolve(20 * np.log10(rms), np.ones(5) / 5, "same"); lo, hi = np.percentile(db, [8, 95]); v = db > lo + 0.36 * (hi - lo)
    out, i = [], 0
    while i < n:
        if v[i]:
            j = i
            while j < n and v[j]: j += 1
            t0, t1 = a0 + i * 0.01, a0 + j * 0.01
            if t1 > a and t0 < b and (t1 - t0) > 0.08: out.append((t0, t1))
            i = j
        else: i += 1
    s = []; prev = None
    for t0, t1 in out:
        gap = (t0 - prev) if prev else 0
        s.append((f" ·{gap:.2f}· " if gap >= 0.12 else "~") + f"{F(t0)}–{t1%60:05.2f}"); prev = t1
    print(f"[{r}] " + "".join(s))
