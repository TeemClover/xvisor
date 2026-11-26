"""usage (through rv): transcript      -> ถอดเสียง.txt + ถอดเสียง-<part>.srt in the project folder
A readable, timestamped transcript of the whole tape (from work/transcript/a16.json, made by `rv prep`),
for the editor and reviewer to read BEFORE choosing lines to cut. Machine transcript: not proofread.

When the tape joins several source clips, list them in project.json so times are shown per original clip:
  "parts": [{"name": "I063", "file": "LL0811_INT_I063_....MP4", "start": 0}, {"name": "I064", "file": "...", "start": 425.83}]
"""
import json, os, sys
import common

sys.stdout.reconfigure(encoding="utf-8")
GAP, MAXC, LOWP = 0.55, 60, 0.45      # new line after a pause / when long; lines whose mean word probability is low get a flag

def F(t, ms=False):
    h, r = divmod(max(t, 0), 3600); m, s = divmod(r, 60)
    if ms: return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)) % 1000:03d}"
    return (f"{int(h)}:" if h else "") + f"{int(m):02d}:{s:05.2f}"

cfg = common.config()
data = json.load(open(common.WORDS, encoding="utf-8"))
words = [w for s in data["segments"] for w in (s.get("words") or [])]
if not words: sys.exit("ไม่มีเวลาของคำใน a16.json — สั่ง rv prep ก่อน")

parts = cfg.get("parts") or [dict(name=os.path.splitext(os.path.basename(cfg["source"]))[0], file=cfg["source"], start=0)]
cuts_at = sorted(p["start"] for p in parts if p["start"] > 0)

# characters with their own time (Whisper's Thai "words" are often single letters)
chars, brk = [], set()                 # brk = char index where a new line must start
for si, seg in enumerate(data["segments"]):
    for wi, w in enumerate(seg.get("words") or []):
        if chars and (w["start"] - chars[-1][2] > GAP or (wi == 0) or any(chars[-1][1] < c <= w["start"] + 0.01 for c in cuts_at)):
            brk.add(len(chars))
        txt = w["word"]; n = max(1, len(txt))
        for i, ch in enumerate(txt):
            chars.append((ch, w["start"] + (w["end"] - w["start"]) * i / n, w["end"], w.get("probability", 1)))
from pythainlp.tokenize import word_tokenize
lines = []
bounds = sorted(brk | {0, len(chars)})
for x0, x1 in zip(bounds, bounds[1:]):
    seg = chars[x0:x1]; text = "".join(c[0] for c in seg)
    # long stretch without a pause: split at a word boundary, never inside a word
    pieces, start, cur = [], 0, 0
    for tok in word_tokenize(text, engine="newmm", keep_whitespace=True):
        if cur - start + len(tok) > MAXC and cur > start: pieces.append((start, cur)); start = cur
        cur += len(tok)
    pieces.append((start, cur))
    for a, b in pieces:
        cs = seg[a:b]; t = "".join(c[0] for c in cs).strip()
        if not t: continue
        lines.append(dict(a=cs[0][1], b=cs[-1][2], text=" ".join(t.split()), low=sum(c[3] for c in cs) / len(cs) < LOWP))

parts = sorted(parts, key=lambda p: p["start"])
def part_of(t):
    k = 0
    for i, p in enumerate(parts):
        if t >= p["start"] - 0.01: k = i
    return k

out = [f"ถอดเสียง · {cfg.get('set', '')}".rstrip(" ·"),
       "ถอดด้วยเครื่อง ยังไม่ได้พิสูจน์อักษร ใช้หาประโยคและเวลา ก่อนใส่เป็นซับต้องฟังและแก้ให้ตรงเสียง",
       f"⚠ = เครื่องไม่มั่นใจ ต้องฟังซ้ำ · เวลา [ในคลิปต้นฉบับ] (ในเทปรวม)", ""]
srt = {i: [] for i in range(len(parts))}
last = -1
for ln in lines:
    k = part_of(ln["a"]); p = parts[k]
    if k != last:
        out += ["", f"══ {p['name']} · {p.get('file', '')}", ""]; last = k
    a, b = ln["a"] - p["start"], ln["b"] - p["start"]
    tape = f" ({F(ln['a'])})" if len(parts) > 1 else ""
    out.append(f"[{F(a)}–{F(b)}]{tape} {'⚠ ' if ln['low'] else ''}{ln['text']}")
    srt[k].append(f"{len(srt[k]) + 1}\n{F(a, True)} --> {F(b, True)}\n{ln['text']}\n")

base = os.path.join(common.PROJ, "ถอดเสียง")
open(base + ".txt", "w", encoding="utf-8-sig").write("\n".join(out) + "\n")
for k, p in enumerate(parts):
    open(f"{base}-{p['name']}.srt", "w", encoding="utf-8-sig").write("\n".join(srt[k]))
print(f"ถอดเสียง.txt: {len(lines)} บรรทัด · ต้องฟังซ้ำ {sum(l['low'] for l in lines)} · srt {len(parts)} ไฟล์")
