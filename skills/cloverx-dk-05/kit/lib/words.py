"""word-level transcript of every source window used by the EDL.
DK-05: the words come from the whole-tape transcript rv prep already made (work/transcript/a16.json), so cutting needs no second
transcription. --fresh runs speech to text again on the windows (stt.py picks the backend) for a line the first pass heard badly.
usage (through rv): words [--fresh] [a-b ...]   no args = every piece in edl.py (padded 1.2 s); writes work/transcript/pieces.json"""
import sys, os, json, wave, numpy as np, stt
import common
from common import T, F
edl = common.load_edl()
OUTF = common.PIECES
os.makedirs(os.path.dirname(OUTF), exist_ok=True)
_w = wave.open(common.A16); sr = _w.getframerate()
x = np.frombuffer(_w.readframes(_w.getnframes()), np.int16).astype(np.float32) / 32768.0
db = json.load(open(OUTF)) if os.path.exists(OUTF) else {}
PAD = 1.2
FRESH = "--fresh" in sys.argv
ARGS = [a for a in sys.argv[1:] if a != "--fresh"]
TAPE = None
if not FRESH and os.path.exists(common.WORDS):
    TAPE = [dict(w=w["word"], s=round(w["start"], 2), e=round(w["end"], 2))
            for sg in json.load(open(common.WORDS, encoding="utf-8"))["segments"] for w in sg.get("words", [])]
wins = []
if ARGS:
    for r in ARGS:
        a, b = [T(v) for v in r.split("-")]; wins.append((a, b))
else:
    for c in edl.CLIPS:
        for p in c["pieces"]: wins.append((p["a"] - PAD, p["b"] + PAD))
# merge overlapping windows
wins.sort(); merged = []
for a, b in wins:
    if merged and a <= merged[-1][1] + 0.5: merged[-1][1] = max(merged[-1][1], b)
    else: merged.append([a, b])
for a, b in merged:
    key = f"{a:.2f}-{b:.2f}"
    if key not in db and TAPE is not None and not FRESH:   # a window read with --fresh keeps that reading
        db[key] = [w for w in TAPE if w["s"] >= a and w["e"] <= b]
        json.dump(db, open(OUTF, "w"), ensure_ascii=False)
    elif key not in db or FRESH:
        r = stt.transcribe(x[int(a * sr):int(b * sr)], word_timestamps=True)
        db[key] = [dict(w=w["word"], s=round(a + w["start"], 2), e=round(a + w["end"], 2)) for s in r["segments"] for w in s.get("words", [])]
        json.dump(db, open(OUTF, "w"), ensure_ascii=False)
    ws = db[key]; line = []; out = []; last = None
    for w in ws:
        gap = w["s"] - last if last is not None else 0
        if last is None or gap > 0.28 or len("".join(line)) > 70:
            if line: out.append("".join(line))
            line = [f"  {F(w['s'])} " + (f"(+{gap:.1f}) " if gap > 0.28 else "")]
        line.append(w["w"]); last = w["e"]
    if line: out.append("".join(line) + f"  ~{F(last)}")
    print(f"=== {F(a)}-{F(b)}"); print("\n".join(out), flush=True)
