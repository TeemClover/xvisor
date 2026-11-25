"""Risk-word check: every word on screen and every spoken line of each clip against risk-words.json
(platform ad rules + Thai FDA food-advertising rules + the brand's own claim guard).
usage (through rv): risk [CLIP…]   -> build/risk.json and a table.  A project may add rules in <project>/risk-words.json.
This is a first filter for the editor, not a legal opinion: a clean result does not mean the clip is approved."""
import os, re, sys, json
import common

ORDER = {"red": 0, "amber": 1, "yellow": 2}
THAI = {"red": "แดง", "amber": "ส้ม", "yellow": "เหลือง"}

def rules():
    base = json.load(open(os.path.join(common.KIT, "risk-words.json"), encoding="utf-8"))
    extra = os.path.join(common.PROJ, "risk-words.json")
    if os.path.exists(extra): base["rules"] += json.load(open(extra, encoding="utf-8")).get("rules", [])
    for r in base["rules"]: r["_re"] = [re.compile(p) for p in r["patterns"]]
    return base

def texts(clip, tl):
    """(where, time or None, text) for everything a viewer reads or hears"""
    out = [("หัวเรื่อง", None, " ".join(l.replace("*", "") for l in clip["head"]))]
    for s in tl["subs"]:
        out.append(("เสียงคนถาม" if s["q"] else "ซับ/เสียงพูด", s["t0"], "".join(w["w"] for w in s["words"])))
    e = tl.get("end") or {}
    out.append(("ฉากปิดท้าย", tl.get("body"), " ".join(str(e.get(k, "")) for k in ("title", "sub", "search")).replace("*", "").replace("\n", " ")))
    for c in tl.get("chips", []): out.append(("ป้ายข้อความ", c["t0"], c["text"].replace("*", "")))
    return out

def scan(clip, tl, R):
    hits = []
    lines = texts(clip, tl)
    # neighbouring subtitle lines are read together too, so a claim split over two lines is still caught
    joined = []
    subs = [x for x in lines if x[1] is not None and x[0].startswith(("ซับ", "เสียง"))]
    for i in range(len(subs) - 1):
        joined.append((subs[i][0], subs[i][1], subs[i][2] + subs[i + 1][2]))
    seen = set()
    for where, t, text in lines + joined:
        for r in R["rules"]:
            for rx in r["_re"]:
                for m in rx.finditer(text):
                    key = (r["id"], m.group(0), round(t or -1, 1))
                    if key in seen or (r["id"], m.group(0), round((t or -1) - 0.0, 1)) in seen: continue
                    seen.add(key)
                    hits.append(dict(rule=r["id"], level=r["level"], label=r["label"], word=m.group(0), where=where, t=t, text=text[:60],
                                     platforms=r.get("platforms", []), why=r.get("why", ""), fix=r.get("fix", "")))
    # one hit per (rule, word): keep the earliest
    best = {}
    for h in sorted(hits, key=lambda h: (h["t"] is None, h["t"] or 0)):
        best.setdefault((h["rule"], h["word"]), h)
    # within one rule, a match that sits inside a longer match says nothing new ("48 บวก" inside "วัย 48 บวก")
    out = [h for h in best.values() if not any(o is not h and o["rule"] == h["rule"] and h["word"] in o["word"] and len(o["word"]) > len(h["word"]) for o in best.values())]
    # DK-05: a before/after picture is red whatever is said over it
    for i in tl.get("inserts", []):
        if i.get("bfaf"): out.append(dict(rule="bfaf", level="red", label="ภาพก่อน–หลัง", word="ภาพ BF/AF", where="ภาพแทรก", t=i["t0"], text=i["file"][:60],
                                          platforms=["อย.", "Meta", "TikTok"], why="ภาพเปรียบเทียบก่อน–หลังเข้าข่ายโฆษณาเกินจริง", fix="ใช้ได้เมื่อเจ้าของภาพยินยอมและทีมตัดสินว่าจะเผยแพร่ที่ไหน"))
    return sorted(out, key=lambda h: (ORDER[h["level"]], h["t"] or 0))

def run(names=None):
    edl = common.load_edl(); R = rules(); out = {}
    for c in edl.CLIPS:
        if names and c["name"] not in names: continue
        f = os.path.join(common.BUILD, c["name"], "timeline.json")
        if not os.path.exists(f): continue
        out[c["name"]] = scan(c, json.load(open(f, encoding="utf-8")), R)
    return out, R

if __name__ == "__main__":
    names = [a for a in sys.argv[1:] if not a.startswith("--")] or None
    res, R = run(names)
    os.makedirs(common.BUILD, exist_ok=True)
    json.dump(dict(version=R.get("version"), clips=res), open(os.path.join(common.BUILD, "risk.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tot = {"red": 0, "amber": 0, "yellow": 0}
    for name, hits in res.items():
        worst = THAI[hits[0]["level"]] if hits else "ไม่พบ"
        print(f"{name}  [{worst}]  " + ("; ".join(f"{THAI[h['level']]}:{h['word']} ({h['label']})" for h in hits) if hits else "—"))
        for h in hits: tot[h["level"]] += 1
    print(f"\nรวม {len(res)} ตอน · แดง {tot['red']} · ส้ม {tot['amber']} · เหลือง {tot['yellow']}  (รายละเอียด: build/risk.json)")
    print("หมายเหตุ: เป็นตัวกรองเบื้องต้น ไม่ใช่คำรับรองทางกฎหมาย ตอนที่จะยิงแอดต้องให้ผู้รับผิดชอบด้านกฎหมาย/อย. ตรวจอีกครั้ง")
