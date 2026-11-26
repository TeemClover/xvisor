"""Review page: <project>/ตรวจงาน.html — every episode with its risk words, insert slots, a comment box and a decision,
plus the people sheet for round 2. The reviewer can save the page (comments inside) to their own machine.
usage (through rv): report            build the page
                    report --read <saved.html | comments.json>   print the comments of a saved page (for the next round)"""
import os, sys, json, html, re, subprocess, datetime
import common
from common import PROJ, BUILD, EXPORTS

LV = {"red": ("แดง", "ห้ามยิงแอด"), "amber": ("ส้ม", "ต้องให้ตรวจก่อน"), "yellow": ("เหลือง", "เฝ้าระวัง")}
CHECKLIST = [
    ("consent", "ผู้รีวิวทุกคนในคลิปเซ็นยินยอมให้ใช้ภาพ เสียง ชื่อ และอายุในโฆษณาแล้ว"),
    ("permit", "ถ้ากล่าวถึงคุณประโยชน์ของอาหาร: มีเลขที่ใบอนุญาตโฆษณา (ฆอ.) และข้อความตรงกับที่ได้รับอนุญาต"),
    ("warning", "คำเตือนอาหารเสริม 3 ข้อ อ่านออกเสียง หรือขึ้นจอไม่น้อยกว่า 5 วินาที ตัวอักษรสูงไม่น้อยกว่า 1/25 ของภาพ"),
    ("age", "ตั้งกลุ่มเป้าหมายแอดอายุ 18 ปีขึ้นไป (TikTok และ Meta กำหนดสำหรับสินค้าสุขภาพ/น้ำหนัก)"),
    ("disclose", "เปิดสวิตช์เปิดเผยเนื้อหาเชิงพาณิชย์ของแพลตฟอร์ม เมื่อเป็นโพสต์ของแบรนด์หรือผู้รีวิวได้ค่าตอบแทน"),
    ("rights", "เพลง ภาพ และฟุตเทจ insert ทุกชิ้นมีสิทธิ์ใช้กับโฆษณาออนไลน์"),
    ("line", "หนึ่งคลิปมีแบรนด์เดียว ไม่ปนสาย (เช่น Habix กับ Xircle)"),
    ("ears", "มีคนฟังเสียงและอ่านซับทั้งคลิปครบทุกตอนแล้ว"),
]
DEFAULT_GROUPS = [("H", "มอนทาจช็อตเด็ด", "รวมช็อตเด็ดของหลายคนในคลิปเดียว"), ("G", "รีวิวรายบุคคล", "หนึ่งคน หนึ่งเรื่อง"),
                  ("X", "อุปกรณ์", "รีวิวอุปกรณ์และแอป"), ("M", "รวมรีวิวตามเรื่อง", "หลายคนในประเด็นเดียว"), ("Y", "มีตัวเลขผลลัพธ์ส่วนบุคคล", "ให้ทีมตรวจคำกล่าวอ้างก่อนใช้")]

def read_saved(path):
    s = open(path, encoding="utf-8").read()
    if path.endswith(".json"): st = json.loads(s)
    else:
        m = re.search(r'<script id="rv-saved" type="application/json">(.*?)</script>', s, re.S)
        if not m: sys.exit("ไฟล์นี้ไม่มีคอมเมนต์ที่บันทึกไว้")
        st = json.loads(m.group(1).strip() or "{}")
    print(f"# คอมเมนต์จาก {os.path.basename(path)}\nผู้ตรวจ: {st.get('reviewer') or '-'} · บันทึกเมื่อ {st.get('at') or '-'}\n")
    if st.get("overall"): print("ภาพรวม:", st["overall"], "\n")
    for cid, c in (st.get("clips") or {}).items():
        notes = {k: v for k, v in (c.get("slots") or {}).items() if v}
        if not (c.get("status") or c.get("comment") or notes): continue
        print(f"## {cid} — {c.get('status') or 'ยังไม่ตรวจ'}")
        if c.get("comment"): print(c["comment"])
        for k, v in notes.items(): print(f"- insert ช่อง {k}: {v}")
        print()
    done = [k for k, v in (st.get("checks") or {}).items() if v]
    print("ข้อตรวจก่อนปล่อยที่ติ๊กแล้ว:", ", ".join(done) or "-")

def esc(s): return html.escape(str(s or ""))

def main():
    edl = common.load_edl()
    import risk as RISK, inserts as INS
    riskres, R = RISK.run()
    PEOPLE = getattr(edl, "PEOPLE", {})
    groups = getattr(edl, "GROUPS", DEFAULT_GROUPS)
    found = {}
    ff = os.path.join(common.INSERTS, "found.json")
    if os.path.exists(ff):
        for it in json.load(open(ff, encoding="utf-8"))["files"]: found.setdefault(it["person"], []).append(it)
    cards = {g[0]: [] for g in groups}; other = []; n = 0; allslots = []; usedby = {}
    tot = {"red": 0, "amber": 0, "yellow": 0, "none": 0}
    os.makedirs(os.path.join(EXPORTS, "posters"), exist_ok=True)
    for c in edl.CLIPS:
        mp4 = os.path.join(EXPORTS, c["name"] + ".mp4"); tlf = os.path.join(BUILD, c["name"], "timeline.json")
        if not (os.path.exists(mp4) and os.path.exists(tlf)): continue
        n += 1; tl = json.load(open(tlf, encoding="utf-8"))
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout or 0)
        poster = os.path.join(EXPORTS, "posters", c["name"] + ".jpg")
        if not os.path.exists(poster) or os.path.getmtime(poster) < os.path.getmtime(mp4):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1.2", "-i", mp4, "-frames:v", "1", "-vf", "scale=540:-2", "-q:v", "4", poster])
        hits = riskres.get(c["name"], []); worst = hits[0]["level"] if hits else "none"; tot[worst] += 1
        chips = "".join(f'<span class="rk {h["level"]}" title="{esc(h["label"])}: {esc(h["why"])}">{esc(h["word"])}</span>' for h in hits)
        rows = "".join(f'<li class="{h["level"]}"><b>{LV[h["level"]][0]} · {esc(h["label"])}</b> — “{esc(h["word"])}” <span class="at">{esc(h["where"])}{"" if h["t"] is None else f" · วินาทีที่ {h['t']:.1f}"}</span>'
                       f'<div class="why">{esc(h["why"])}</div><div class="fix">ทางแก้: {esc(h["fix"])}</div><div class="pf">เกี่ยวกับ: {esc(" · ".join(h["platforms"]))}</div></li>' for h in hits)
        riskbox = (f'<details class="risk {worst}" open><summary>{LV[worst][0]}: {LV[worst][1]} · คำเสี่ยง {len(hits)} จุด</summary><div class="chips">{chips}</div><ul>{rows}</ul></details>'
                   if hits else '<p class="clean">ไม่พบคำในคลังคำเสี่ยง (ยังต้องให้คนตรวจตามรายการท้ายหน้า)</p>')
        placed = {i["slot"]: i for i in tl.get("inserts", [])}
        srows = ""
        for p in tl.get("pieces", []):
            if p.get("q"): continue
            per = PEOPLE.get(p.get("person") or "", {})
            usedby.setdefault(p.get("person"), set()).add(c["name"]); allslots.append(dict(p, clip=c["name"]))
            ins = placed.get(p["slot"])
            srows += (f'<tr><td class="sid">{p["slot"]}</td><td>{esc(per.get("name", "—"))}</td><td class="tm">{p["o0"]:.1f}–{p["o1"]:.1f}</td><td>{esc(p["text"][:80])}'
                      + "".join(f'<div class="placed">ใส่แล้ว: {esc(os.path.basename(i["file"]))} ({i["dur"]:.1f} วิ)</div>' for i in tl.get("inserts", []) if i["slot"] == p["slot"])
                      + f'</td><td><input class="sn" data-clip="{c["name"]}" data-slot="{p["slot"]}" placeholder="อยากได้ insert อะไร"></td></tr>')
        head = " ".join(l.replace("*", "") for l in c["head"])
        subs = "".join(f'<li class="{"q" if s["q"] else ""}"><span>{s["t0"]:.1f}</span>{esc("".join(w["w"] for w in s["words"]))}</li>' for s in tl["subs"])
        who = c.get("who") or " · ".join(dict.fromkeys(PEOPLE.get(p.get("person") or "", {}).get("name", "") for p in tl.get("pieces", []) if p.get("person")))
        chk = f'<p class="chk"><b>ควรฟังซ้ำ:</b> {esc(c["check"])}</p>' if c.get("check") else ""
        card = f'''
<article class="card" id="{c["name"]}" data-clip="{c["name"]}">
  <div class="vid"><video src="exports/{c["name"]}.mp4" poster="exports/posters/{c["name"]}.jpg" controls preload="none" playsinline></video></div>
  <div class="meta">
    <div class="row"><span class="code">{c["name"]}</span><span class="pill {worst}">{LV[worst][0] + " · " + LV[worst][1] if hits else "ไม่พบคำเสี่ยง"}</span><span class="dur">{dur:.0f} วินาที</span></div>
    <h3>{esc(c.get("title", head))}</h3>
    <dl><dt>ข้อความเปิด</dt><dd>{esc(head)}</dd><dt>ผู้รีวิว</dt><dd>{esc(who)}</dd><dt>สินค้า</dt><dd>{esc(c.get("product", ""))}</dd><dt>ไฟล์</dt><dd><code>exports/{c["name"]}.mp4</code></dd></dl>
    {chk}{riskbox}
    <details class="slots"><summary>ช่อง insert รอบ 2 ({sum(1 for p in tl.get("pieces", []) if not p.get("q"))} ช่อง · ใส่แล้ว {len(tl.get("inserts", []))})</summary>
      <table><thead><tr><th>ช่อง</th><th>คน</th><th>วินาที</th><th>พูดว่า</th><th>โน้ตถึงคนหา insert</th></tr></thead><tbody>{srows}</tbody></table></details>
    <details><summary>ข้อความซับทั้งตอน (ใช้ตรวจคำ)</summary><ol>{subs}</ol></details>
    <div class="rev">
      <div class="st" role="group" aria-label="ผลตรวจ">{"".join(f'<label><input type="radio" name="st-{c["name"]}" value="{v}"><span>{v}</span></label>' for v in ("ผ่าน", "แก้", "ไม่ใช้"))}</div>
      <textarea class="cm" placeholder="คอมเมนต์ของตอนนี้ เช่น ตัดช็อตที่ 3 ออก / เปลี่ยนคำเปิด / ซับวินาทีที่ 12 ผิด"></textarea>
    </div>
  </div>
</article>'''
        (cards[c["name"][0]] if c["name"][0] in cards else other).append(card)
    if not n: sys.exit("ยังไม่มีตอนที่เรนเดอร์แล้วใน exports/ — สั่ง rv make ก่อน")
    sections = ""
    for k, ttl, desc in groups:
        if cards[k]: sections += f'<section><div class="sh"><h2>{esc(ttl)}</h2><span>{len(cards[k])} ตอน</span></div><p class="sd">{esc(desc)}</p><div class="grid">{"".join(cards[k])}</div></section>'
    if other: sections += f'<section><div class="sh"><h2>ตอนอื่นๆ</h2><span>{len(other)} ตอน</span></div><div class="grid">{"".join(other)}</div></section>'
    # people sheet (round 2: one folder per person)
    people_html = ""
    for key, per in PEOPLE.items():
        mine = [s for s in allslots if s.get("person") == key]
        if not mine: continue
        pic = os.path.join(EXPORTS, "people", f"{key}.jpg")
        if not os.path.exists(pic): INS.face_picture(key, per, [dict(s) for s in mine])
        files = found.get(key, [])
        people_html += f'''<div class="pcard" id="p-{esc(key)}"><img src="exports/people/{esc(key)}.jpg" alt="" onerror="this.style.visibility='hidden'">
  <div><div class="pn">{esc(per["name"])}</div><div class="pr">{esc(per.get("role", ""))} · รหัส <b>{esc(key)}</b></div>
  <div class="pf2">โฟลเดอร์: <code>inserts/{esc(INS.folder_of(key, per))}/</code></div>
  <div class="pc">อยู่ใน {len(usedby.get(key, []))} ตอน: {esc(" ".join(sorted(usedby.get(key, []))))}</div>
  <div class="pc">{len(mine)} ช่อง · มีไฟล์ในโฟลเดอร์แล้ว {len(files)} ไฟล์</div></div></div>'''
    people_sec = (f'''<section id="people"><div class="sh"><h2>คนในคลิป · โฟลเดอร์ insert รอบ 2</h2><span>{people_html.count('class="pcard"')} คน</span></div>
<p class="sd">หนึ่งคน = หนึ่งโฟลเดอร์ แคปการ์ดของคนนั้นจากหน้านี้ไปวางในโฟลเดอร์เดียวกับไฟล์ที่หามา (ภาพ คลิปสินค้า ฟุตเทจ สกรีนช็อตแอป) รอบ 2 จะได้ใส่ insert ถูกคน รหัสช่อง (เช่น G03-2) ดูได้ใต้แต่ละคลิป</p>
<div class="people">{people_html}</div></section>''' if people_html else "")
    checks = "".join(f'<label class="ck"><input type="checkbox" data-check="{k}"><span>{esc(t)}</span></label>' for k, t in CHECKLIST)
    title = common.config().get("title") or os.path.basename(PROJ)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    page = TEMPLATE.replace("{{TITLE}}", esc(title)).replace("{{N}}", str(n)).replace("{{NOW}}", now).replace("{{SECTIONS}}", sections).replace("{{PEOPLE}}", people_sec) \
        .replace("{{CHECKS}}", checks).replace("{{RED}}", str(tot["red"])).replace("{{AMBER}}", str(tot["amber"])).replace("{{YELLOW}}", str(tot["yellow"])).replace("{{CLEAN}}", str(tot["none"])) \
        .replace("{{RISKVER}}", esc(R.get("version", ""))).replace("{{KEY}}", esc(re.sub(r"\W+", "-", title)))
    out = os.path.join(PROJ, "ตรวจงาน.html")
    open(out, "w", encoding="utf-8").write(page)
    print(f"หน้าตรวจงาน {n} ตอน → {out}  (แดง {tot['red']} · ส้ม {tot['amber']} · เหลือง {tot['yellow']} · ไม่พบ {tot['none']})")

TEMPLATE = r'''<!doctype html><html lang="th"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ตรวจงาน · {{TITLE}}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#07110E;--bg2:#0D1A16;--card:#11201B;--line:rgba(245,240,230,.13);--ink:#F5F0E6;--soft:#B9C2BC;--gold:#E9C987;--green:#8FDCAF;--red:#FF8A80;--amber:#FFB86B;--yellow:#F3E38B}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:Kanit,system-ui,sans-serif;font-weight:300;line-height:1.55;padding-bottom:90px}
header,main,.wrap{max-width:1240px;margin:0 auto;padding-left:24px;padding-right:24px}
header{padding-top:48px}
header .k{color:var(--gold);letter-spacing:.28em;font-size:13px;font-weight:500}
header h1{font-weight:700;font-size:clamp(28px,4.4vw,48px);line-height:1.15;margin:10px 0 10px}
header h1 em{font-style:normal;color:var(--gold)}
header p{color:var(--soft);max-width:800px;margin:0;font-size:16px}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin-top:22px}
.stats div{border:1px solid var(--line);border-radius:14px;padding:10px 16px;background:var(--bg2)}
.stats b{display:block;font-weight:700;font-size:24px;line-height:1.1}
.stats span{color:var(--soft);font-size:13px}
.s-red b{color:var(--red)}.s-amber b{color:var(--amber)}.s-yellow b{color:var(--yellow)}.s-clean b{color:var(--green)}
.who{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-top:22px}
input,textarea,button{font:inherit;color:inherit}
.who input,.overall{background:var(--bg2);border:1px solid var(--line);border-radius:12px;padding:10px 14px}
.who input{width:260px}.overall{width:100%;min-height:74px;margin-top:12px;resize:vertical}
.box{border:1px solid var(--line);border-left:3px solid var(--gold);border-radius:14px;background:var(--bg2);padding:16px 20px;margin-top:22px}
.box h4{margin:0 0 6px;font-weight:600;font-size:17px}
.box ul{margin:0;padding-left:20px;color:var(--soft);font-size:15px}.box li{margin:3px 0}.box b{color:var(--ink);font-weight:500}
.ck{display:flex;gap:10px;align-items:flex-start;padding:5px 0;font-size:15px;cursor:pointer}.ck input{margin-top:6px;accent-color:#E9C987;width:17px;height:17px;flex:none}
section{margin-top:40px}
.sh{display:flex;align-items:baseline;gap:14px;border-bottom:1px solid var(--line);padding-bottom:10px}
.sh h2{margin:0;font-weight:600;font-size:25px}.sh span{color:var(--gold);font-size:14px}
.sd{color:var(--soft);margin:10px 0 18px;font-size:15px;max-width:900px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;overflow:hidden;display:flex;flex-direction:column;min-width:0}
.vid{aspect-ratio:9/16;background:#000;max-height:560px}
.vid video{width:100%;height:100%;display:block;object-fit:contain;background:#000}
.meta{padding:16px}
.row{display:flex;align-items:center;gap:8px;font-size:12.5px;flex-wrap:wrap}
.code{font-weight:600;color:var(--gold);letter-spacing:.08em}
.pill{border-radius:999px;padding:2px 10px;font-weight:500}
.pill.none{background:rgba(143,220,175,.14);color:var(--green)}.pill.red{background:rgba(255,138,128,.16);color:var(--red)}
.pill.amber{background:rgba(255,184,107,.16);color:var(--amber)}.pill.yellow{background:rgba(243,227,139,.14);color:var(--yellow)}
.dur{margin-left:auto;color:var(--soft)}
h3{margin:10px 0;font-weight:600;font-size:19px;line-height:1.3}
dl{display:grid;grid-template-columns:86px 1fr;gap:4px 10px;margin:0;font-size:14px}dt{color:var(--soft)}dd{margin:0;min-width:0}
code{font-size:12.5px;color:var(--gold);word-break:break-all}
.chk,.clean{margin:12px 0 0;font-size:13.5px;color:var(--soft);background:rgba(245,240,230,.06);border-radius:10px;padding:8px 12px}.chk b{color:var(--ink);font-weight:500}
.clean{color:var(--green)}
details{margin-top:12px;border-top:1px solid var(--line);padding-top:10px;font-size:14px}
summary{cursor:pointer;color:var(--gold)}
details.risk{border:1px solid var(--line);border-radius:12px;padding:10px 12px}
details.risk.red{border-color:rgba(255,138,128,.5)}details.risk.amber{border-color:rgba(255,184,107,.45)}details.risk.yellow{border-color:rgba(243,227,139,.35)}
details.risk.red>summary{color:var(--red)}details.risk.amber>summary{color:var(--amber)}details.risk.yellow>summary{color:var(--yellow)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 4px}
.rk{border-radius:8px;padding:1px 9px;font-size:13px;font-weight:500;cursor:help}
.rk.red{background:rgba(255,138,128,.18);color:var(--red)}.rk.amber{background:rgba(255,184,107,.18);color:var(--amber)}.rk.yellow{background:rgba(243,227,139,.15);color:var(--yellow)}
details.risk ul{list-style:none;margin:8px 0 0;padding:0;max-height:300px;overflow:auto}
details.risk li{padding:8px 0;border-top:1px dashed var(--line);font-size:13.5px}
details.risk li b{font-weight:500}li.red b{color:var(--red)}li.amber b{color:var(--amber)}li.yellow b{color:var(--yellow)}
.at{color:var(--soft);font-size:12px}.why{color:var(--soft);margin-top:3px}.fix{margin-top:3px}.pf{color:var(--soft);font-size:12px;margin-top:2px}
details ol{list-style:none;margin:10px 0 0;padding:0;max-height:240px;overflow:auto}
details ol li{display:flex;gap:10px;padding:2px 0}details ol li.q{color:var(--soft);font-style:italic}
details ol li span{color:var(--soft);font-size:12px;min-width:34px;text-align:right;padding-top:2px;font-variant-numeric:tabular-nums}
.slots table{width:100%;border-collapse:collapse;margin-top:8px;font-size:13px}
.slots th{text-align:left;color:var(--soft);font-weight:400;padding:4px 6px;border-bottom:1px solid var(--line)}
.slots td{padding:6px;border-bottom:1px dashed var(--line);vertical-align:top}
.sid{color:var(--gold);font-weight:500;white-space:nowrap}.tm{white-space:nowrap;color:var(--soft);font-variant-numeric:tabular-nums}
.placed{color:var(--green);font-size:12px;margin-top:2px}
.sn{width:100%;min-width:120px;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:4px 8px;font-size:13px}
.rev{margin-top:14px;border-top:1px solid var(--line);padding-top:12px}
.st{display:flex;gap:8px}
.st label{flex:1;cursor:pointer}.st input{position:absolute;opacity:0}
.st span{display:block;text-align:center;border:1px solid var(--line);border-radius:10px;padding:6px 0;font-weight:500;color:var(--soft)}
.st input:checked+span{background:var(--gold);color:#10201a;border-color:var(--gold)}
.st input:focus-visible+span{outline:2px solid var(--gold);outline-offset:2px}
.cm{width:100%;min-height:76px;margin-top:10px;background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:8px 10px;resize:vertical;font-size:14px}
.people{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.pcard{display:flex;gap:14px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:12px}
.pcard img{width:108px;height:108px;border-radius:12px;object-fit:cover;flex:none;background:#000}
.pn{font-weight:600;font-size:19px;line-height:1.2}.pr{color:var(--gold);font-size:13.5px}.pc,.pf2{color:var(--soft);font-size:13px;margin-top:2px}
#bar{position:fixed;left:0;right:0;bottom:0;background:rgba(7,17,14,.94);backdrop-filter:blur(8px);border-top:1px solid var(--line);z-index:5}
#bar .wrap{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding-top:12px;padding-bottom:12px}
button{border:1px solid var(--line);background:var(--bg2);border-radius:999px;padding:8px 18px;cursor:pointer;font-weight:500}
button.main{background:var(--gold);color:#10201a;border-color:var(--gold)}
#msg{color:var(--soft);font-size:13.5px;margin-left:auto}
footer{color:var(--soft);font-size:13px;margin-top:40px}
@media(max-width:560px){.grid{grid-template-columns:1fr}.who input{width:100%}#msg{margin-left:0;width:100%}}
</style></head><body>
<header><div class="k">ตรวจงาน · รีวิวลูกค้า</div><h1>{{TITLE}} <em>{{N}} ตอน</em></h1>
<p>กดเล่นแต่ละตอน เลือกผลตรวจ แล้วพิมพ์คอมเมนต์ใต้คลิป หน้านี้จำสิ่งที่พิมพ์ไว้ในเบราว์เซอร์นี้เอง และกด “บันทึกหน้านี้ลงเครื่อง” เพื่อได้ไฟล์ HTML ที่มีคอมเมนต์ติดไปด้วย · สร้างเมื่อ {{NOW}}</p>
<div class="stats"><div class="s-red"><b>{{RED}}</b><span>ตอนที่มีคำระดับแดง</span></div><div class="s-amber"><b>{{AMBER}}</b><span>ระดับส้ม</span></div><div class="s-yellow"><b>{{YELLOW}}</b><span>ระดับเหลือง</span></div><div class="s-clean"><b>{{CLEAN}}</b><span>ไม่พบคำเสี่ยง</span></div></div>
<div class="who"><input id="reviewer" placeholder="ชื่อผู้ตรวจ" autocomplete="name"><span id="savedat" style="color:var(--soft);font-size:13.5px"></span></div>
<textarea id="overall" class="overall" placeholder="คอมเมนต์ภาพรวมของทั้งชุด"></textarea>
<div class="box"><h4>วิธีอ่านสีคำเสี่ยง (คลังคำ {{RISKVER}})</h4><ul>
<li><b style="color:var(--red)">แดง</b> อยู่ในข้อห้ามของ อย. หรือของแพลตฟอร์มโดยตรง ห้ามใช้ในโฆษณา</li>
<li><b style="color:var(--amber)">ส้ม</b> ใกล้ข้อห้าม ใช้ได้เมื่อผู้รับผิดชอบด้านกฎหมาย/อย. เซ็นผ่านเท่านั้น</li>
<li><b style="color:var(--yellow)">เหลือง</b> ขึ้นกับบริบทและการตั้งค่าแอด</li>
<li>เป็นตัวกรองเบื้องต้นจากคำที่อยู่ในซับและหัวเรื่อง ไม่ใช่คำรับรองทางกฎหมาย ตอนที่ “ไม่พบคำเสี่ยง” ยังต้องผ่านรายการตรวจท้ายหน้า</li></ul></div>
</header>
<main>{{SECTIONS}}{{PEOPLE}}
<section id="checks"><div class="sh"><h2>ตรวจก่อนปล่อย</h2><span>ติ๊กเมื่อยืนยันแล้ว</span></div><div class="box" style="margin-top:14px">{{CHECKS}}</div></section>
<footer>คลิปเล่นจากโฟลเดอร์ <code>exports/</code> ที่อยู่ข้างไฟล์นี้ ถ้าบันทึกหน้านี้ไปไว้ที่อื่น ให้เก็บไว้ในโฟลเดอร์โปรเจ็กต์เดิมเพื่อให้คลิปยังเล่นได้</footer>
</main>
<div id="bar"><div class="wrap"><button class="main" id="save">บันทึกหน้านี้ลงเครื่อง</button><button id="md">ส่งออกคอมเมนต์ (.md)</button><button id="js">ส่งออก (.json)</button><span id="msg"></span></div></div>
<script id="rv-saved" type="application/json"></script>
<script>
(function(){
  var KEY='rv-review-{{KEY}}';
  var $=function(s,r){return (r||document).querySelector(s)}, $$=function(s,r){return [].slice.call((r||document).querySelectorAll(s))};
  function read(){
    var st={reviewer:$('#reviewer').value.trim(),overall:$('#overall').value,at:new Date().toISOString(),clips:{},checks:{}};
    $$('.card').forEach(function(c){var id=c.dataset.clip,r=$('input[type=radio]:checked',c),o={status:r?r.value:'',comment:$('.cm',c).value,slots:{}};
      $$('.sn',c).forEach(function(i){if(i.value.trim())o.slots[i.dataset.slot]=i.value.trim()});st.clips[id]=o});
    $$('[data-check]').forEach(function(i){st.checks[i.dataset.check]=i.checked});
    return st;
  }
  function apply(st){ if(!st) return;
    $('#reviewer').value=st.reviewer||''; $('#overall').value=st.overall||'';
    $$('.card').forEach(function(c){var o=(st.clips||{})[c.dataset.clip]; if(!o) return;
      $$('input[type=radio]',c).forEach(function(r){r.checked=(r.value===o.status)}); $('.cm',c).value=o.comment||'';
      $$('.sn',c).forEach(function(i){i.value=(o.slots||{})[i.dataset.slot]||''})});
    $$('[data-check]').forEach(function(i){i.checked=!!(st.checks||{})[i.dataset.check]});
    if(st.at) $('#savedat').textContent='บันทึกล่าสุด '+new Date(st.at).toLocaleString('th-TH');
  }
  function local(){try{return JSON.parse(localStorage.getItem(KEY)||'null')}catch(e){return null}}
  function keep(){var st=read();try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){} $('#msg').textContent='จำไว้ในเบราว์เซอร์นี้แล้ว '+new Date().toLocaleTimeString('th-TH'); return st}
  var emb=null; try{emb=JSON.parse($('#rv-saved').textContent||'null')}catch(e){}
  var loc=local(); apply(emb&&(!loc||(emb.at||'')>(loc.at||''))?emb:loc);
  var t; document.addEventListener('input',function(){clearTimeout(t);t=setTimeout(keep,500)}); document.addEventListener('change',function(){clearTimeout(t);t=setTimeout(keep,200)});
  function stamp(){var d=new Date(),p=function(n){return (n<10?'0':'')+n};return d.getFullYear()+p(d.getMonth()+1)+p(d.getDate())+'-'+p(d.getHours())+p(d.getMinutes())}
  function give(name,text,type){
    if(window.showSaveFilePicker){return window.showSaveFilePicker({suggestedName:name}).then(function(h){return h.createWritable()}).then(function(w){return w.write(text).then(function(){return w.close()})})
      .then(function(){$('#msg').textContent='บันทึกแล้ว: '+name}).catch(function(e){if(e&&e.name==='AbortError')return; dl(name,text,type)})}
    dl(name,text,type); return Promise.resolve();
  }
  function dl(name,text,type){var a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type:type}));a.download=name;document.body.appendChild(a);a.click();
    setTimeout(function(){URL.revokeObjectURL(a.href);a.remove()},500);$('#msg').textContent='ดาวน์โหลดแล้ว: '+name+' (ย้ายไปไว้ในโฟลเดอร์โปรเจ็กต์เพื่อให้คลิปเล่นได้)'}
  $('#save').onclick=function(){var st=keep(), who=(st.reviewer||'ผู้ตรวจ').replace(/[\\/:*?"<>| ]+/g,'-');
    var doc=document.documentElement.cloneNode(true); doc.querySelector('#rv-saved').textContent=JSON.stringify(st).replace(/</g,'\\u003c'); doc.querySelector('#msg').textContent='';
    give('ตรวจงาน-'+stamp()+'-'+who+'.html','<!doctype html>\n'+doc.outerHTML,'text/html')};
  function md(st){var L=['# คอมเมนต์ตรวจงาน','ผู้ตรวจ: '+(st.reviewer||'-')+' · '+new Date(st.at).toLocaleString('th-TH'),''];
    if(st.overall)L.push('ภาพรวม: '+st.overall,'');
    Object.keys(st.clips).forEach(function(id){var c=st.clips[id],ks=Object.keys(c.slots||{}); if(!c.status&&!c.comment&&!ks.length)return;
      L.push('## '+id+' — '+(c.status||'ยังไม่ตรวจ')); if(c.comment)L.push(c.comment); ks.forEach(function(k){L.push('- insert ช่อง '+k+': '+c.slots[k])}); L.push('')});
    return L.join('\n')}
  $('#md').onclick=function(){var st=keep();give('คอมเมนต์-'+stamp()+'.md',md(st),'text/markdown')};
  $('#js').onclick=function(){var st=keep();give('คอมเมนต์-'+stamp()+'.json',JSON.stringify(st,null,1),'application/json')};
})();
</script></body></html>'''

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--read": read_saved(sys.argv[2])
    else: main()
