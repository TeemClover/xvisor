"""Round 2 — inserts, one folder per person.
usage (through rv):
  inserts init   make inserts/<key>-<name>/ for everyone in PEOPLE (+ inserts/_กลาง for shared product shots),
                 put a face picture and the list of their lines (slots) inside, write inserts/คำขอ-insert.md
  inserts scan   list what the team dropped in, check it, and print where each file can go (edl.py `ins=` lines)
Folder = person. A file from a person's folder may only be placed on that person's shots; _กลาง can go anywhere."""
import os, sys, json, re, subprocess
import common
from common import PROJ, BUILD, INSERTS, F

CATS = [("1-สินค้า", "ภาพหรือคลิปสินค้า: ซอง กล่อง ฉลาก (ใช้ภาพทางการจากการ์ด PD ใน /sources ได้)"),
        ("2-การใช้", "คลิปแกะซอง ชง ดื่ม พกพา ของคนนี้หรือที่ถ่ายใหม่"),
        ("3-แอป-Xircle", "สกรีนช็อตหรืออัดหน้าจอแอป Xircle (ต้องไม่มีข้อมูลส่วนตัวของคนอื่น)"),
        ("4-ภาพและฟุตเทจ", "ภาพหรือฟุตเทจของคนนี้: ออกกำลัง ทำงาน ชีวิตประจำวัน (ภาพก่อน–หลังเป็นระดับแดง ใช้ได้เมื่อผู้ตรวจเลือกเองในหน้าจับคู่)"),
        ("5-อื่นๆ", "อย่างอื่นที่อยากให้ลองใส่ เขียนบอกในชื่อไฟล์")]
MEDIA = (".mp4", ".mov", ".m4v", ".webm", ".jpg", ".jpeg", ".png", ".webp", ".heic")
SHARED = "_กลาง"
PRODUCT_WORDS = r"โปรตีน|HMB|กัส|G\.U\.S|แอสต้า|AstaMega|รูทีน|RoutineX|ซอง|รสชาติ|อร่อย|เฟลเวอร์"
APP_WORDS = r"แอป|แทร็ก|แคลอรี่|การนอน|การกิน|การขยับ|ก้าว|สายรัด|Xircle|Band|ฟังก์ชัน"

def people():
    return getattr(common.load_edl(), "PEOPLE", {})

def folder_of(key, per): return f"{key}-{per['name']}".replace("/", "-").replace(" ", "")

def person_of_path(path):
    """inserts/<key>-<name>/... -> key ; inserts/_กลาง/... -> SHARED ; anything else -> None"""
    rel = os.path.relpath(path if os.path.isabs(path) else os.path.join(PROJ, path), INSERTS)
    if rel.startswith(".."): return None
    top = rel.split(os.sep)[0]
    if top == SHARED: return SHARED
    for k in people():
        if top == k or top.startswith(k + "-"): return k
    return None

def slots():
    """every piece of every built clip: slot id, person, time in the clip, what is said"""
    out = []
    for c in common.load_edl().CLIPS:
        f = os.path.join(BUILD, c["name"], "timeline.json")
        if not os.path.exists(f): continue
        tl = json.load(open(f, encoding="utf-8"))
        for p in tl.get("pieces", []):
            if p.get("q") or not p.get("text"): continue
            out.append(dict(p, clip=c["name"], title=c.get("title", "")))
    return out

def face_picture(key, per, sl):
    """a still of the person from their first shot -> exports/people/<key>.jpg (also copied into their folder)"""
    import cv2, numpy as np
    mine = [s for s in sl if s["person"] == key]
    if not mine: return None
    s = mine[0]; t = (s["a"] + s["b"]) / 2
    src = common.config()["source_path"]
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    if len(raw) != 1080 * 1920 * 3: return None
    fr = np.frombuffer(raw, np.uint8).reshape(1920, 1080, 3)
    faces = json.load(open(common.FACES)) if os.path.exists(common.FACES) else {}
    fs = [f for f in faces.get(f"{round(t * 2) / 2:.1f}", []) if f[2] > 0.13]
    x = per.get("x")
    if fs: f = min(fs, key=lambda f: abs(f[0] - x)) if isinstance(x, (int, float)) else max(fs, key=lambda f: f[2]); cx, cy = f[0] * 1080, f[1] * 1920
    else: cx, cy = (x if isinstance(x, (int, float)) else 0.5) * 1080, 0.36 * 1920
    h = 620; x0 = int(min(max(cx - h / 2, 0), 1080 - h)); y0 = int(min(max(cy - h * 0.42, 0), 1920 - h))
    out = os.path.join(common.EXPORTS, "people"); os.makedirs(out, exist_ok=True)
    p = os.path.join(out, f"{key}.jpg"); cv2.imwrite(p, cv2.resize(fr[y0:y0 + h, x0:x0 + h], (480, 480), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 88])
    return p

def init():
    P = people(); sl = slots()
    if not P: sys.exit("edl.py ยังไม่มี PEOPLE — ใส่รายชื่อคนในคลิปก่อน")
    if not sl: sys.exit("ยังไม่มีตอนที่ตัดแล้ว (build/*/timeline.json) — สั่ง rv make ก่อน")
    os.makedirs(INSERTS, exist_ok=True)
    rows = ["# คำขอ insert รอบ 2", "", "หนึ่งโฟลเดอร์ = หนึ่งคน วางไฟล์ลงโฟลเดอร์ย่อยตามชนิด ถ้าอยากให้ลงช็อตไหนแน่ๆ ให้ขึ้นต้นชื่อไฟล์ด้วยรหัสช่อง เช่น `G03-2_แกะซอง.mp4`", ""]
    for key, per in P.items():
        d = os.path.join(INSERTS, folder_of(key, per))
        for c, _ in CATS: os.makedirs(os.path.join(d, c), exist_ok=True)
        mine = [s for s in sl if s["person"] == key]
        pic = face_picture(key, per, sl)
        if pic: subprocess.run(["cp", pic, os.path.join(d, "คนนี้คือใคร.jpg")])
        lines = [f"โฟลเดอร์ insert ของ: {per['name']}" + (f" ({per['role']})" if per.get("role") else ""), f"รหัสคน: {key}", "",
                 "วางไฟล์ตามชนิด:"] + [f"  {c}/  — {h}" for c, h in CATS] + ["",
                 "ถ้ามีภาพแคปการ์ดคนนี้จากหน้า HTML ตรวจงาน ให้วางไว้ในโฟลเดอร์นี้ด้วย (ตั้งชื่ออะไรก็ได้) จะได้รู้ว่าไฟล์ชุดนี้เป็นของใคร",
                 "ห้าม: ภาพก่อน–หลัง, ภาพที่มีข้อมูลสุขภาพหรือข้อมูลส่วนตัวของคนอื่น, คลิปที่ไม่มีสิทธิ์ใช้ (เช่น โหลดจาก YouTube ของคนอื่น)", "",
                 f"ช็อตของคนนี้ ({len(mine)} ช่อง):"] + [f"  {s['slot']:8s} {s['o0']:5.1f}–{s['o1']:5.1f} วิ  {s['text'][:70]}" for s in mine]
        open(os.path.join(d, "อ่านก่อน.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
        rows += [f"## {per['name']} · โฟลเดอร์ `inserts/{folder_of(key, per)}/`", "", "| ช่อง | ตอน | วินาที | พูดว่า | น่าใส่ |", "|---|---|---|---|---|"]
        for s in mine:
            hint = "สินค้า / การใช้" if re.search(PRODUCT_WORDS, s["text"]) else "แอป Xircle" if re.search(APP_WORDS, s["text"]) else "ภาพคนนี้ / ไม่ต้องใส่"
            rows.append(f"| {s['slot']} | {s['clip']} | {s['o0']:.1f}–{s['o1']:.1f} | {s['text'][:60]} | {hint} |")
        rows.append("")
    d = os.path.join(INSERTS, SHARED)
    for c, _ in CATS[:3]: os.makedirs(os.path.join(d, c), exist_ok=True)
    open(os.path.join(d, "อ่านก่อน.txt"), "w", encoding="utf-8").write("ของกลาง: ภาพและคลิปสินค้า คลิปการใช้ และหน้าจอแอป ที่ใช้กับช็อตของใครก็ได้\nภาพหรือฟุตเทจของตัวบุคคลให้วางในโฟลเดอร์ของคนนั้น ไม่ใช่ที่นี่\n")
    open(os.path.join(INSERTS, "คำขอ-insert.md"), "w", encoding="utf-8").write("\n".join(rows))
    print(f"สร้างโฟลเดอร์ insert {len(P)} คน + ของกลาง ที่ inserts/  ·  รายการช่อง: inserts/คำขอ-insert.md")

def probe(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,duration:format=duration", "-of", "json", f], capture_output=True, text=True)
    try:
        j = json.loads(r.stdout); st = j["streams"][0]; dur = float(st.get("duration") or j["format"].get("duration") or 0)
        return st["width"], st["height"], dur
    except Exception: return None

def scan():
    P = people(); sl = slots(); found = []; warn = []
    if not os.path.isdir(INSERTS): sys.exit("ยังไม่มีโฟลเดอร์ inserts/ — สั่ง rv inserts init ก่อน")
    for root, _, files in os.walk(INSERTS):
        for n in sorted(files):
            if not n.lower().endswith(MEDIA) or n == "คนนี้คือใคร.jpg": continue
            path = os.path.join(root, n); rel = os.path.relpath(path, PROJ); who = person_of_path(path)
            cat = os.path.relpath(root, INSERTS).split(os.sep)[1] if len(os.path.relpath(root, INSERTS).split(os.sep)) > 1 else "(ยังไม่จัดชนิด)"
            if cat == "(ยังไม่จัดชนิด)" and who: continue          # loose files at a person's top level = reference captures from the HTML
            if n.lower().endswith(".heic"): warn.append(f"{rel}: ไฟล์ HEIC ให้แปลงเป็น JPG ก่อน"); continue
            pr = probe(path)
            if not pr: warn.append(f"{rel}: เปิดไฟล์ไม่ได้"); continue
            w, h, dur = pr; video = n.lower().endswith((".mp4", ".mov", ".m4v", ".webm"))
            item = dict(file=rel, person=who, cat=cat, w=w, h=h, dur=round(dur, 2) if video else None, video=video)
            if min(w, h) < 720: warn.append(f"{rel}: ภาพเล็ก ({w}×{h}) อาจแตกเมื่อเต็มจอ")
            if who is None: warn.append(f"{rel}: อยู่นอกโฟลเดอร์คน ไม่รู้ว่าเป็นของใคร")
            pin = re.match(r"([A-Z]\d{2}-\d+)[_\- ]", n)
            cands = [s for s in sl if who in (SHARED, s["person"])]
            if pin:
                hit = [s for s in sl if s["slot"] == pin.group(1)]
                if not hit: warn.append(f"{rel}: ไม่พบช่อง {pin.group(1)}")
                elif who not in (SHARED, hit[0]["person"]): warn.append(f"{rel}: ช่อง {pin.group(1)} เป็นของคนอื่น ({hit[0]['person']}) ไม่ใช่ของโฟลเดอร์นี้")
                else: item["slots"] = [pin.group(1)]
            else:
                rx = PRODUCT_WORDS if cat.startswith(("1-", "2-")) else APP_WORDS if cat.startswith("3-") else None
                item["slots"] = [s["slot"] for s in cands if rx and re.search(rx, s["text"])][:6]
            found.append(item)
    json.dump(dict(files=found, warnings=warn), open(os.path.join(INSERTS, "found.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    by = {s["slot"]: s for s in sl}
    for it in found:
        size = f"{it['w']}×{it['h']}" + (f" {it['dur']} วิ" if it["video"] else " ภาพนิ่ง")
        print(f"\n{it['file']}  [{P.get(it['person'], {}).get('name', it['person'])}] {size}")
        for sid in it.get("slots", []):
            s = by[sid]; d = min(2.4, s["o1"] - s["o0"] - 0.4, it["dur"] or 9)
            print(f"   → {sid} ({s['o0']:.1f}–{s['o1']:.1f} วิ) “{s['text'][:44]}”   ins=[dict(file=\"{it['file']}\", at=0.3, dur={max(d, 1.0):.1f})]")
        if not it.get("slots"): print("   → ยังไม่มีช่องที่ตรง ให้คนหรือ AI เลือกช็อตจากรายการช่องของคนนี้")
    for w_ in warn: print("เตือน:", w_)
    print(f"\nพบ {len(found)} ไฟล์ · เตือน {len(warn)} ข้อ · บันทึกที่ inserts/found.json")

if __name__ == "__main__":
    {"init": init, "scan": scan}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit("ใช้: rv inserts init | scan"))()
