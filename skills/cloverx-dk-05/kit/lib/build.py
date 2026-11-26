"""Cutter: source ranges -> tightened, face-following base video + dialogue + timeline.json
usage (through rv): build <CLIP...|ALL> [--skip-video] [--subs-only]
"""
import re, sys, os, json, subprocess, math
import numpy as np, soundfile as sf, cv2

import common
from common import T, PROJ, BUILD, A16, A48, SFX
edl = common.load_edl()
import subs as SUBS
import mixer
import inserts as INS

CFG = common.config()
SRC = CFG["source_path"]
SPEED, FPS, W, H = float(CFG["speed"]), int(CFG["fps"]), 1080, 1920
END_PLAIN, END_WARN = 3.8, 5.8
GRADE = CFG.get("grade", "eq=contrast=1.05:saturation=1.10,vignette=PI/7")
FACES = json.load(open(common.FACES)) if os.path.exists(common.FACES) else {}
PEOPLE = getattr(edl, "PEOPLE", {})
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm", ".mkv")

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        print(" ".join(cmd)); print(r.stderr[-3000:]); sys.exit(1)

# ---------------- face track ----------------
def track(a, b, x):
    """smoothed (t, cx, cy) samples of the wanted face across the piece [a,b]. x = 'L' | 'R' | 0..1 | None (biggest)"""
    ts, pts = [], []
    t = math.floor((a - 1.0) * 2) / 2
    while t <= b + 1.0:
        fs = [f for f in FACES.get(f"{t:.1f}", []) if 0.10 < f[1] < 0.66 and f[2] > 0.13]
        if fs:
            if x == "L": f = min(fs, key=lambda f: f[0])
            elif x == "R": f = max(fs, key=lambda f: f[0])
            elif isinstance(x, (int, float)):
                f = min(fs, key=lambda f: abs(f[0] - x))
                if abs(f[0] - x) > 0.2: t += 0.5; continue
            else: f = max(fs, key=lambda f: f[2])
            ts.append(t); pts.append((f[0], f[1]))
        t += 0.5
    if len(ts) < 2: return None
    ts = np.array(ts); p = np.array(pts)
    keep = np.ones(len(ts), bool)            # drop samples that jump away from the local median (the other person, a passer-by)
    for i in range(len(ts)):
        m = np.abs(ts - ts[i]) <= 3.0
        if abs(p[i, 0] - np.median(p[m, 0])) > 0.16 or abs(p[i, 1] - np.median(p[m, 1])) > 0.12: keep[i] = False
    if keep.sum() < 2: return None
    ts, p = ts[keep], p[keep]
    g = np.arange(ts[0], ts[-1] + 0.01, 0.1)
    X = np.interp(g, ts, p[:, 0]); Y = np.interp(g, ts, p[:, 1])
    k = np.hanning(17); k /= k.sum()
    X = np.convolve(np.pad(X, 8, mode="edge"), k, "valid"); Y = np.convolve(np.pad(Y, 8, mode="edge"), k, "valid")
    return g, X, Y

# ---------------- speech / silence ----------------
audio16, sr16 = sf.read(A16)
def _voiced(a, b):
    a0, b0 = max(0, a - 3), min(len(audio16) / sr16, b + 3)
    x = audio16[int(a0 * sr16):int(b0 * sr16)]; hop = int(0.01 * sr16); n = len(x) // hop
    rms = np.sqrt(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    db = np.convolve(20 * np.log10(rms), np.ones(5) / 5, "same")
    lo, hi = np.percentile(db, [8, 95])
    return a0, db > lo + 0.36 * (hi - lo)

def snap(a, b):
    """move the in point onto the start of speech and the out point just past its end (within 0.35 s)"""
    a0, v = _voiced(a, b)
    def edge(t, rising):
        i = int((t - a0) / 0.01); best = None
        for j in range(max(1, i - 35), min(len(v) - 1, i + 35)):
            if (rising and v[j] and not v[j - 1]) or (not rising and not v[j] and v[j - 1]):
                if best is None or abs(j - i) < abs(best - i): best = j
        return None if best is None else a0 + best * 0.01
    ea, eb = edge(a, True), edge(b, False)
    return (ea - 0.07 if ea is not None else a), (eb + 0.10 if eb is not None else b)

def speech_spans(a, b, min_gap=0.26, margin=0.07):
    a0, vall = _voiced(a, b)
    i0 = int((a - a0) / 0.01); n = int((b - a) / 0.01); voiced = vall[i0:i0 + n]; n = len(voiced)
    if n < 30: return [(a, b)]
    cuts, i = [], 0
    while i < n:
        if not voiced[i]:
            j = i
            while j < n and not voiced[j]: j += 1
            if (j - i) * 0.01 >= min_gap and i > 0 and j < n: cuts.append((a + i * 0.01 + margin, a + j * 0.01 - margin))
            i = j
        else: i += 1
    keep, s = [], a
    for c0, c1 in cuts:
        if c1 > c0: keep.append((s, c0)); s = c1
    keep.append((s, b))
    keep = [[p, q] for p, q in keep if q - p > 0.03]
    merged = []
    for p, q in keep:
        if merged and ((q - p) < 0.35 or (merged[-1][1] - merged[-1][0]) < 0.35): merged[-1][1] = q
        else: merged.append([p, q])
    return [tuple(x) for x in merged]

# ---------------- inserts (round 2) ----------------
class Insert:
    """a picture or a clip shown over the speaker for a few seconds while the voice goes on"""
    PANEL = (60, 452, 960, 760)     # x, y, w, h of the safe box between the headline and the subtitles
    GAP = 24                        # space between the BF and AF pictures of a pair
    FRAME = (52, 168, 63)           # BGR frame colour, set per clip in build()
    def __init__(self, spec, t0, dur):
        self.t0, self.dur = t0, dur
        self.file = spec["file"] if os.path.isabs(spec["file"]) else os.path.join(PROJ, spec["file"])
        if not os.path.exists(self.file): sys.exit(f"ไม่พบไฟล์ insert: {spec['file']}")
        self.video = self.file.lower().endswith(VIDEO_EXT)
        w, h = self._size()
        self.fit = "pair" if spec.get("file2") else (spec.get("fit") or ("cover" if h / max(w, 1) >= (1.45 if self.video else 1.3) else "panel"))
        self.fin, self.fout = spec.get("fin", True), spec.get("fout", True)   # DK-05: a picture run cuts hard inside, dissolves only at its ends
        self.ss = float(spec.get("ss", 0)); self.proc = None; self.img = None; self.last = None
        if self.fit == "pair":                     # V.2: BF (before) left + AF (after) right, side by side in one frame
            self.video = False; bx, by, bw, bh = self.PANEL; hw = (bw - self.GAP) // 2
            self.pair = []
            for f in (self.file, spec["file2"] if os.path.isabs(spec["file2"]) else os.path.join(PROJ, spec["file2"])):
                if not os.path.exists(f): sys.exit(f"ไม่พบไฟล์ insert: {f}")
                im = cv2.imdecode(np.fromfile(f, np.uint8), cv2.IMREAD_COLOR)
                if im is None: sys.exit(f"เปิดภาพ insert ไม่ได้: {f} (ภาพคู่ BF/AF ต้องเป็นภาพนิ่ง)")
                ih, iw = im.shape[:2]; k = min(hw / iw, bh / ih)
                self.pair.append(cv2.resize(im, (int(iw * k), int(ih * k)), interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_LANCZOS4))
            return
        if self.fit == "cover": self.tw, self.th = W, H
        else:
            bx, by, bw, bh = self.PANEL; k = min(bw / w, bh / h); self.tw, self.th = int(w * k) // 2 * 2, int(h * k) // 2 * 2
        if not self.video:
            im = cv2.imdecode(np.fromfile(self.file, np.uint8), cv2.IMREAD_COLOR)
            if im is None: sys.exit(f"เปิดภาพ insert ไม่ได้: {spec['file']}")
            self.img = self._fit(im)
    def _size(self):
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams", "-of", "json", self.file], capture_output=True, text=True, encoding="utf-8", errors="replace")
        try: st = json.loads(r.stdout)["streams"][0]; w, h = st["width"], st["height"]
        except Exception: sys.exit(f"อ่านขนาดไฟล์ insert ไม่ได้: {self.file}")
        rot = 0
        for sd in st.get("side_data_list") or []:
            if "rotation" in sd: rot = abs(int(sd["rotation"]))
        rot = rot or abs(int((st.get("tags") or {}).get("rotate", 0) or 0))
        return (h, w) if rot in (90, 270) else (w, h)
    def _fit(self, im):
        h, w = im.shape[:2]
        if self.fit == "cover":
            k = max(W / w, H / h); im = cv2.resize(im, (math.ceil(w * k), math.ceil(h * k)), interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_CUBIC)
            y0 = (im.shape[0] - H) // 2; x0 = (im.shape[1] - W) // 2
            return im[y0:y0 + H, x0:x0 + W]
        return cv2.resize(im, (self.tw, self.th), interpolation=cv2.INTER_AREA if self.tw < w else cv2.INTER_CUBIC)
    def _next(self):
        if not self.video: return self.img
        if self.proc is None:
            vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}" if self.fit == "cover" else f"scale={self.tw}:{self.th}") + f",fps={FPS}"
            self.proc = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{self.ss:.3f}", "-i", self.file, "-vf", vf, "-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
        raw = self.proc.stdout.read(self.tw * self.th * 3)
        if len(raw) == self.tw * self.th * 3: self.last = np.frombuffer(raw, np.uint8).reshape(self.th, self.tw, 3)
        return self.last
    def draw(self, frame, t):
        q = t - self.t0
        if q < 0 or q >= self.dur: return frame
        if self.fit == "pair": return self._draw_pair(frame, q)
        im = self._next()
        if im is None: return frame
        a = min(1.0, q / 0.14 if self.fin else 1.0, (self.dur - q) / 0.14 if self.fout else 1.0)   # 4-frame dissolve in and out
        if self.fit == "cover":
            if not self.video:                                      # slow push on stills
                z = 1.0 + 0.05 * q / self.dur
                M = np.float32([[z, 0, -(z - 1) * W / 2], [0, z, -(z - 1) * H / 2]]); im = cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR)
            return cv2.addWeighted(frame, 1 - a, im, a, 0) if a < 1 else im
        bx, by, bw, bh = self.PANEL
        bg = cv2.GaussianBlur(cv2.resize(frame, (W // 4, H // 4)), (0, 0), 9); bg = cv2.resize(bg, (W, H)); bg = (bg * 0.55).astype(np.uint8)
        x0 = bx + (bw - self.tw) // 2; y0 = by + (bh - self.th) // 2
        cv2.rectangle(bg, (x0 - 6, y0 - 6), (x0 + self.tw + 5, y0 + self.th + 5), Insert.FRAME, 3, cv2.LINE_AA)   # thin HabiX-green frame (Xircle blue on Xircle clips)
        bg[y0:y0 + self.th, x0:x0 + self.tw] = im
        return cv2.addWeighted(frame, 1 - a, bg, a, 0) if a < 1 else bg
    def _draw_pair(self, frame, q):
        bx, by, bw, bh = self.PANEL; hw = (bw - self.GAP) // 2
        bg = cv2.GaussianBlur(cv2.resize(frame, (W // 4, H // 4)), (0, 0), 9); bg = cv2.resize(bg, (W, H)); bg = (bg * 0.55).astype(np.uint8)
        out = bg.copy()
        for i, im in enumerate(self.pair):                         # BF first, AF follows 0.35 s later
            th, tw = im.shape[:2]; x0 = bx + i * (hw + self.GAP) + (hw - tw) // 2; y0 = by + (bh - th) // 2
            k = max(0.0, min(1.0, (q - 0.35 * i) / 0.18, (self.dur - q) / 0.14))
            if k <= 0: continue
            tile = bg.copy()
            cv2.rectangle(tile, (x0 - 6, y0 - 6), (x0 + tw + 5, y0 + th + 5), Insert.FRAME, 3, cv2.LINE_AA)
            tile[y0:y0 + th, x0:x0 + tw] = im
            ys, xs = slice(max(0, y0 - 8), y0 + th + 8), slice(max(0, x0 - 8), x0 + tw + 8)
            out[ys, xs] = cv2.addWeighted(out[ys, xs], 1 - k, tile[ys, xs], k, 0)
        a = min(1.0, q / 0.14, (self.dur - q) / 0.14)
        return cv2.addWeighted(frame, 1 - a, out, a, 0) if a < 1 else out
    def close(self):
        if self.proc: self.proc.stdout.close(); self.proc.wait()

# ---------------- build ----------------
def person_of(p):
    return PEOPLE.get(p["who"]) if isinstance(p["who"], str) else None

def build(clip, skip_video=False):
    out = os.path.join(BUILD, clip["name"]); os.makedirs(out, exist_ok=True)
    segs, t_out, inserts = [], 0.0, []
    tl = dict(subs=[], chips=[], cards=[], tags=[], sfx=[], flashes=[], pieces=[], inserts=[], total=0, brand=clip.get("brand", "habix"), head=clip["head"],
              kicker=clip.get("kicker", "รีวิวจากผู้ใช้จริง"), note=clip.get("note", edl.NOTE), cuts=[])
    if "music_under_db" in clip: tl["music_under_db"] = clip["music_under_db"]
    Insert.FRAME = (244, 133, 66) if tl["brand"] == "xircle" else (52, 168, 63)   # DK-05: Xircle blue #4285F4
    zi = 0
    for pi, p in enumerate(clip["pieces"]):
        per = person_of(p)
        x = p["x"] if p["x"] is not None else (per or {}).get("x", p["who"] if p["who"] in ("L", "R") else None)
        a, b = snap(p["a"], p["b"]) if p.get("snap", True) else (p["a"], p["b"])
        spans = speech_spans(a, b) if p["tight"] else [(a, b)]
        mapping, p_o0 = [], t_out
        tr = track(a, b, x)
        if p["z"] is not None: zb = p["z"]
        else: zb = edl.ZCYCLE[zi % len(edl.ZCYCLE)]; zi += 1
        for k, (u0, u1) in enumerate(spans):
            nf = max(2, round((u1 - u0) / SPEED * FPS)); u1 = u0 + nf / FPS * SPEED; d = nf / FPS
            z = zb * (1.0 if k % 2 == 0 else 1.09)
            segs.append(dict(a=u0, b=u1, nf=nf, z=round(z, 3), tr=tr, o0=t_out, dur=d, slam=bool(p["slam"]) and k == 0))
            mapping.append((u0, u1, t_out)); t_out += d
        p_o1 = t_out
        def m(src, mapping=mapping, p_o1=p_o1):
            for u0, u1, o in mapping:
                if src < u0: return o
                if src <= u1: return o + (src - u0) / SPEED
            return p_o1
        def at(v, p_o0=p_o0, m=m): return p_o0 + v if isinstance(v, (int, float)) else m(T(v))
        tl["cuts"].append(round(p_o0, 3))
        said = []
        for ph in SUBS.phrases(a, b, p.get("subs"), clip.get("kw", ())):
            t0 = m(ph["t0"]); ws = [dict(w=w["w"], t=round(max(t0, m(w["t"])), 3), k=w["k"]) for w in ph["words"]]
            q = bool(p.get("q")) or ph.get("q", False)
            tl["subs"].append(dict(t0=round(t0, 3), t1=0, words=ws, q=q, big=ph.get("big", False), pend=p_o1))
            if not q: said.append("".join(w["w"] for w in ws))
            if ph.get("big"):
                tl["sfx"].append(("cut_hit_punch", t0, -16)); tl["flashes"].append(round(t0, 3))
        # one slot per piece: where an insert of round 2 can go, and whose words they are
        tl["pieces"].append(dict(slot=f"{clip['name']}-{pi + 1}", person=p["who"] if isinstance(p["who"], str) and p["who"] in PEOPLE else None,
                                 q=bool(p.get("q")), o0=round(p_o0, 3), o1=round(p_o1, 3), a=round(a, 2), b=round(b, 2), text=" ".join(said)))
        for c in p.get("chips", ()):
            ct = at(c[1]); tl["chips"].append(dict(text=c[0], t0=round(ct, 3), dur=c[2] if len(c) > 2 else 2.4)); tl["sfx"].append(("pro_pop_in_round", ct, -14))
        for c in p.get("cards", ()):
            ct = at(c[1]); img, nm, ln = edl.PRODUCTS[c[0]]
            px = (per or {}).get("x", 0.5) if isinstance(per, dict) else 0.5
            side = c[3] if len(c) > 3 else "center"   # V.2: centred above the subtitles with a green glow ("left"/"right" to move it)
            tl["cards"].append(dict(img=img, name=nm, line=ln, side=side, t0=round(ct, 3), dur=c[2] if len(c) > 2 else 2.8)); tl["sfx"].append(("pro_pop_in_round", ct, -15))
        for n, s, g in p.get("sfx", ()): tl["sfx"].append((n, at(s), g))
        for f in p.get("flash", ()): tl["flashes"].append(round(at(f), 3))
        tag = p.get("tag")
        if tag is True and per: tag = (per["name"], per.get("age") or per.get("role", ""), per.get("job", ""))
        if tag and tag is not True and p_o1 - p_o0 >= 1.0:
            first = not tl["tags"]; d = min(2.7, p_o1 - p_o0 - (0.35 if first else 0.2))
            tl["tags"].append(dict(name=tag[0], role=tag[1], job=(tag[2] if len(tag) > 2 else ""), t0=round(p_o0 + (0.3 if first else 0.12), 3), dur=round(d, 3)))
        for sp in p.get("ins", ()):
            for fx in [sp["file"]] + ([sp["file2"]] if sp.get("file2") else []):
              owner = INS.person_of_path(fx)               # a file from one person's folder never lands on another person's shot
              if owner and owner != INS.SHARED and owner != p["who"]:
                sys.exit(f"หยุด: {sp['file']} อยู่ในโฟลเดอร์ของ {PEOPLE.get(owner, {}).get('name', owner)} แต่ถูกวางในช็อตของ {(per or {}).get('name', p['who'])} ({clip['name']}-{pi + 1})")
            it0 = at(sp.get("at", 0.25)) + float(sp.get("after", 0))
            idur = float(sp.get("dur", 2.2)) if sp.get("span") else min(float(sp.get("dur", 2.2)), p_o1 - it0 - 0.05)   # DK-05 runs may run on into the next piece
            if idur < 0.6: print(f"  ข้าม insert {sp['file']} (ช็อตสั้นเกินไป)"); continue
            inserts.append(Insert(sp, it0, idur))
            tl["inserts"].append(dict(slot=f"{clip['name']}-{pi + 1}", file=sp["file"] + (" + " + sp["file2"] if sp.get("file2") else ""), t0=round(it0, 3), dur=round(idur, 3), fit=inserts[-1].fit,
                                      bfaf=bool(re.match(r"(?i)(BF|AF)\d", os.path.basename(sp["file"])))))
            if sp.get("fin", True): tl["sfx"].append(("swish_zing", max(0, it0 - 0.05), -18))
        for ap in p.get("apps", ()):                         # DK-05: Xircle app screenshot in a phone mock-up + its scores as text
            owner = INS.person_of_path(ap["img"])
            if owner and owner != INS.SHARED and owner != p["who"]:
                sys.exit(f"หยุด: {ap['img']} อยู่ในโฟลเดอร์ของ {PEOPLE.get(owner, {}).get('name', owner)} แต่ถูกวางในช็อตของ {(per or {}).get('name', p['who'])}")
            if not os.path.exists(ap["img"] if os.path.isabs(ap["img"]) else os.path.join(PROJ, ap["img"])): sys.exit(f"ไม่พบภาพแอป: {ap['img']}")
            a0 = at(ap.get("at", 0.25)) + float(ap.get("after", 0))
            stats = [(k, ap[k.lower()]) for k in ("EAT", "MOVE", "SLEEP", "HABIT") if ap.get(k.lower()) not in (None, "")]
            tl.setdefault("apps", []).append(dict(img=ap["img"], t0=round(a0, 3), dur=float(ap.get("dur", 3.5)), stats=stats, title=ap.get("title", "Xircle App"),
                                                  label=ap.get("label", ""), note=ap.get("note", ""), card=ap.get("card", ""), cont=bool(ap.get("cont")), last=ap.get("last", True)))
            tl["inserts"].append(dict(slot=f"{clip['name']}-{pi + 1}", file=ap["img"] + " (mock-up โทรศัพท์)", t0=round(a0, 3), dur=float(ap.get("dur", 3.5)), fit="app"))
            if not ap.get("cont"): tl["sfx"].append(("pro_pop_in_round", a0, -14))
    # the name tag, a product card and an insert share one zone: later items wait for the tag to leave
    for g in tl["tags"]:
        te = g["t0"] + g["dur"]
        for c in tl["cards"]:
            if c["t0"] < te + 0.1 and c["t0"] + c["dur"] > g["t0"]: c["t0"] = round(te + 0.1, 3)
    tl["cards"] = [c for c in tl["cards"] if not any(c["t0"] < i["t0"] + i["dur"] and c["t0"] + c["dur"] > i["t0"] for i in tl["inserts"])]
    S = tl["subs"]
    for i, s in enumerate(S):
        nxt = min(S[i + 1]["t0"], s["pend"]) if i + 1 < len(S) else s["pend"]
        last = s["words"][-1]["t"]
        s["t1"] = round(nxt if nxt - last <= 1.3 else last + 1.0, 3)
        del s["pend"]
    body = t_out
    e = dict(clip["end"]); e["t0"] = round(body, 3)
    if "bg" not in e and getattr(edl, "END_BG", ""): e["bg"] = edl.END_BG   # bg=None keeps the plain colour end (Xircle clips)   # V.2: end-card background picture
    tl["end"] = e
    if CFG.get("fda_warning") and tl["brand"] != "xircle" and not e.get("warn"): e["warn"] = edl.FDA_WARN
    END_DUR = END_WARN if e.get("warn") else END_PLAIN      # the warning must stay readable for at least 5 seconds
    t_out = body + END_DUR; tl["total"] = round(t_out, 3); tl["body"] = round(body, 3)
    tl["sfx"] += [("whoosh_fast_whip", 0.0, -13), ("cut_hit_kick", 0.02, -10)]
    for c in tl["cuts"][1:]: tl["sfx"].append(("swish_zing", max(0, c - 0.06), -19))
    tl["sfx"] += [("reverse_swell_short", max(0, body - 0.75), -13), ("pro_logo_sting_sweep_hit", body - 0.05, -10), ("pro_hover_tick_glass", body + 0.9, -17)]
    json.dump(tl, open(os.path.join(out, "timeline.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{clip['name']}: {len(segs)} segs, body {body:.2f}s total {t_out:.2f}s" + (f", {len(inserts)} insert" if inserts else ""), flush=True)
    with open(os.path.join(out, "subs.txt"), "w", encoding="utf-8") as f:
        for s in S: f.write(f"{s['t0']:6.2f}-{s['t1']:6.2f} {'[Q] ' if s['q'] else ''}{'[BIG] ' if s['big'] else ''}{''.join(('*'+w['w']+'*') if w['k'] else w['w'] for w in s['words'])}\n")
    if "--subs-only" in sys.argv: return

    if not skip_video:
        enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                                "-vf", GRADE + ",format=yuv420p", "-c:v", "libx264", "-crf", "13", "-preset", "fast", os.path.join(out, "base.mov")], stdin=subprocess.PIPE)
        last = None; prev_c = None; clean = None
        for s in segs:
            dec = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{s['a']:.3f}", "-t", f"{s['b'] - s['a'] + 0.3:.3f}", "-i", SRC,
                                    "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setpts=(PTS-STARTPTS)/{SPEED},fps={FPS}",
                                    "-frames:v", str(s["nf"]), "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
            for k in range(s["nf"]):
                raw = dec.stdout.read(W * H * 3)
                fr = np.frombuffer(raw, np.uint8).reshape(H, W, 3) if len(raw) == W * H * 3 else clean
                ts_src = s["a"] + k / FPS * SPEED; tt = k / FPS
                z = s["z"] * (1 + 0.022 * tt / max(s["dur"], 0.3))
                if s["slam"]: z += 0.30 * (1 - min(tt / 0.36, 1)) ** 3
                if s["tr"] is not None:
                    g, X, Y = s["tr"]; cx = float(np.interp(ts_src, g, X)); cy = float(np.interp(ts_src, g, Y))
                elif prev_c: cx, cy = prev_c
                else: cx, cy = 0.5, 0.36
                prev_c = (cx, cy)
                cw, ch = W / z, H / z
                x0 = min(max(cx * W - cw / 2, 0), W - cw); y0 = min(max(cy * H - 0.37 * ch, 0), H - ch)
                M = np.float32([[z, 0, -x0 * z], [0, z, -y0 * z]])
                o = fr if z <= 1.0005 else cv2.warpAffine(fr, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                clean = o; t_now = s["o0"] + tt
                for ins in inserts: o = ins.draw(o, t_now)
                enc.stdin.write(np.ascontiguousarray(o).tobytes()); last = o
            dec.stdout.close(); dec.wait()
        for ins in inserts: ins.close()
        # end plate: the last frame melts into a dark blur
        bl = cv2.GaussianBlur(last, (0, 0), 30); bl = (bl.astype(np.float32) * 0.8).astype(np.uint8)
        for k in range(round(END_DUR * FPS)):
            q = min(k / (0.3 * FPS), 1.0); z = 1 + 0.03 * k / (END_DUR * FPS)
            fr = cv2.addWeighted(last, 1 - q, bl, q, 0) if q < 1 else bl
            M = np.float32([[z, 0, -(z - 1) * W / 2], [0, z, -(z - 1) * H / 2]])
            enc.stdin.write(cv2.warpAffine(fr, M, (W, H), flags=cv2.INTER_LINEAR).tobytes())
        enc.stdin.close(); enc.wait()
        # dialogue: source audio of every segment, joined with short fades, then one speed change
        sr = 48000; parts = []
        for s in segs:
            x, _ = sf.read(A48, start=int(round(s["a"] * sr)), frames=int(round((s["b"] - s["a"]) * sr)))
            f = int(0.012 * sr); x = x.copy(); x[:f] *= np.linspace(0, 1, f); x[-f:] *= np.linspace(1, 0, f); parts.append(x)
        sf.write(os.path.join(out, "dial_src.wav"), np.concatenate(parts), sr)
        run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(out, "dial_src.wav"), "-ac", "1", "-ar", "48000",
             "-af", f"atempo={SPEED},highpass=f=95,afftdn=nr=14:nf=-42:tn=1,equalizer=f=3200:t=q:w=1.2:g=2.5,equalizer=f=280:t=q:w=1:g=-2,"
                    "acompressor=threshold=-22dB:ratio=3:attack=5:release=90:makeup=4dB,alimiter=limit=0.9", os.path.join(out, "dial.wav")])
    mixer.mix(out, tl, SFX)

if __name__ == "__main__":
    names = [a for a in sys.argv[1:] if not a.startswith("--")]
    done = 0
    for c in edl.CLIPS:
        if c["name"] in names or "ALL" in names: build(c, skip_video="--skip-video" in sys.argv); done += 1
    if not done: sys.exit("ไม่พบตอนที่ระบุใน edl.py")
