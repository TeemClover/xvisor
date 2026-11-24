"""Subtitle phrases from the Whisper word timings (with text corrections) or from manual lines."""
import os, json, re
from pythainlp.tokenize import word_tokenize
import common
from common import T
edl = common.load_edl()
WJ = common.WORDS
MAXC = 17          # characters per phrase (one line at 84 px)

def _vis(s):  # visible width: Thai combining marks take no column
    return len(re.sub(r"[ัิ-ฺ็-๎]", "", s))

_chars = None
def chars():
    """whole transcript as [(char, time)], corrections applied"""
    global _chars
    if _chars is not None: return _chars
    cs = []
    for seg in (json.load(open(WJ, encoding="utf-8"))["segments"] if os.path.exists(WJ) else []):
        for w in seg.get("words", []):
            txt = w["word"]; n = max(1, len(txt)); t0, t1 = w["start"], max(w["end"], w["start"] + 0.02)
            for i, ch in enumerate(txt): cs.append((ch, t0 + (t1 - t0) * i / n))
    s = "".join(c for c, _ in cs)
    for wrong, right in edl.FIX:
        pos = 0; pat = re.compile(wrong)
        while True:
            mt = pat.search(s, pos)
            if not mt: break
            i, j = mt.span()
            if j == i: pos = j + 1; continue
            rep = mt.expand(right)
            t0 = cs[i][1]; t1 = cs[j][1] if j < len(cs) else cs[j - 1][1] + 0.1
            new = [(ch, t0 + (t1 - t0) * k / max(1, len(rep))) for k, ch in enumerate(rep)]
            cs[i:j] = new; s = s[:i] + rep + s[j:]; pos = i + len(rep)
    _chars = cs
    return cs

_pc = None
def piece_chars():
    global _pc
    if _pc is None:
        _pc = []
        f = common.PIECES
        if os.path.exists(f):
            for ws in json.load(open(f, encoding="utf-8")).values():
                for w in ws:
                    n = max(1, len(w["w"])); t1 = max(w["e"], w["s"] + 0.02)
                    for i, ch in enumerate(w["w"]): _pc.append((ch, w["s"] + (t1 - w["s"]) * i / n))
            _pc.sort(key=lambda x: x[1])
    return _pc

def dump(a, b):
    return "".join(c for c, t in chars() if a <= t < b)

def _tokens(cs):
    """[(char,time)] -> word tokens [{w,t,t1}]"""
    text = "".join(c for c, _ in cs)
    out, i = [], 0
    for tok in word_tokenize(text, engine="newmm", keep_whitespace=True):
        j = i + len(tok)
        out.append(dict(w=tok, t=cs[i][1], t1=cs[j - 1][1]))
        i = j
    return out

def _mark(words, kw):
    text = "".join(w["w"] for w in words); hit = [False] * len(text)
    for k in list(edl.KW) + list(kw):
        for mt in re.finditer(k, text):
            for x in range(*mt.span()): hit[x] = True
    i = 0
    for w in words:
        j = i + len(w["w"]); w["k"] = bool(w["w"].strip()) and sum(hit[i:j]) * 2 >= len(w["w"]); i = j
    return words

def _group(toks):
    phr, cur = [], []
    def flush():
        nonlocal cur
        while cur and not cur[-1]["w"].strip(): cur.pop()
        while cur and not cur[0]["w"].strip(): cur.pop(0)
        if cur: phr.append(cur)
        cur = []
    for tk in toks:
        ln = _vis("".join(w["w"] for w in cur))
        gap = tk["t"] - cur[-1]["t1"] if cur else 0
        if cur and (gap > 0.5 or ln + _vis(tk["w"]) > MAXC or (not tk["w"].strip() and ln >= 8)): flush()
        if not cur and not tk["w"].strip(): continue
        cur.append(tk)
    flush()
    # merge orphans
    out = []
    for p in phr:
        l = _vis("".join(w["w"] for w in p))
        if out and l <= 4 and _vis("".join(w["w"] for w in out[-1])) + l <= MAXC + 4 and p[0]["t"] - out[-1][-1]["t1"] < 0.4:
            out[-1] += p
        else: out.append(p)
    return out

def _aligned(a, b, lines, kw):
    """corrected lines (strings, optional (text, flags)) timed by aligning them to the Whisper characters in [a,b]"""
    import difflib
    items = [(l, "") if isinstance(l, str) else (l[0], l[1]) for l in lines]
    clean = [re.sub(r"\*", "", l) for l, _ in items]
    M = "".join(clean)
    # two readings of the same audio (whole-file pass, per-window pass): keep the one closer to the proofread text
    cands = [[(c, t) for c, t in chars() if a - 0.15 <= t < b + 0.1], [(c, t) for c, t in piece_chars() if a - 0.15 <= t < b + 0.1]]
    def score(cs):
        return difflib.SequenceMatcher(None, re.sub(r"\s", "", "".join(c for c, _ in cs)), re.sub(r"\s", "", M), autojunk=False).ratio() if cs else 0
    cs = max(cands, key=score); Wt = "".join(c for c, _ in cs)
    # anchors: matching blocks give M index -> time; everything else is interpolated
    anc = [(-1, a)]
    for blk in difflib.SequenceMatcher(None, Wt, M, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            t = min(max(cs[blk.a + k][1], a), b)
            if t >= anc[-1][1] - 1e-6: anc.append((blk.b + k, t))
    anc.append((len(M), b))
    def tm(i):
        for (i0, t0), (i1, t1) in zip(anc, anc[1:]):
            if i0 <= i <= i1: return t0 + (t1 - t0) * (i - i0) / max(1, i1 - i0)
        return b
    res, pos = [], 0
    for (raw, fl), cl in zip(items, clean):
        csm = [(ch, tm(pos + k)) for k, ch in enumerate(cl)]
        ws = _mark(_tokens(csm), kw)
        if "*" in raw:
            flags, on = [], False
            for ch in raw:
                if ch == "*": on = not on
                else: flags.append(on)
            p2 = 0
            for w in ws:
                j = p2 + len(w["w"]); w["k"] = bool(w["w"].strip()) and sum(flags[p2:j]) * 2 >= len(w["w"]); p2 = j
        res.append(dict(t0=max(a, csm[0][1] - 0.03), words=ws, big="B" in fl, q="Q" in fl))
        pos += len(cl)
    return res

def phrases(a, b, manual=None, kw=()):
    res = []
    if manual is not None and (not manual or isinstance(manual[0], str) or len(manual[0]) < 2 or ":" not in str(manual[0][1])):
        return _aligned(a, b, manual, kw)
    if manual is not None:
        ms = [(m[0], T(m[1]), m[2] if len(m) > 2 else "") for m in manual]
        for i, (txt, t0, fl) in enumerate(ms):
            if not txt: continue
            t1 = ms[i + 1][1] if i + 1 < len(ms) else b
            clean = re.sub(r"\*", "", txt); n = max(1, len(clean)); span = min(t1 - t0 - 0.1, 0.075 * n)
            cs = [(ch, t0 + span * k / n) for k, ch in enumerate(clean)]
            ws = _mark(_tokens(cs), kw)
            # explicit *keyword* markup wins
            if "*" in txt:
                pos, flags, on = 0, [], False
                for ch in txt:
                    if ch == "*": on = not on
                    else: flags.append(on)
                for w in ws:
                    j = pos + len(w["w"]); w["k"] = bool(w["w"].strip()) and sum(flags[pos:j]) * 2 >= len(w["w"]); pos = j
            res.append(dict(t0=t0, words=ws, big="B" in fl, q="Q" in fl))
        return res
    cs = [(c, t) for c, t in chars() if a - 0.05 <= t < b - 0.02]
    if not cs: return res
    for p in _group(_tokens(cs)):
        ws = _mark(p, kw)
        res.append(dict(t0=max(a, p[0]["t"] - 0.04), words=ws))
    return res
