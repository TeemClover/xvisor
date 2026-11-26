"""What a project's edl.py imports: piece and clip builders, brand presets, subtitle keywords.
Times are source times "m:ss.ss".  A subtitle line may be (text, "B") = big punch word, (text, "Q") = the interviewer.
*word* inside a line turns it gold."""
from common import T

ZCYCLE = [1.0, 1.16, 1.06, 1.24]          # zoom levels the cuts walk through
NOTE = ""   # V.2: ไม่มีบรรทัดคำกำกับทุกเฟรม (เดิม: "ความคิดเห็นส่วนบุคคลของผู้ใช้ · ผลลัพธ์แตกต่างกันในแต่ละบุคคล")
NOTE_RESULT = "ประสบการณ์ส่วนบุคคล ควบคู่การปรับพฤติกรรม · ผลลัพธ์แตกต่างกันในแต่ละบุคคล"
NOTE_XIRCLE = "ความคิดเห็นส่วนบุคคลของผู้ใช้ · ใช้ติดตามพฤติกรรมสุขภาพ ไม่ใช่การวินิจฉัยโรค"
DISC = ["ผลิตภัณฑ์เสริมอาหาร ไม่มีผลในการป้องกันหรือรักษาโรค", "โปรดอ่านฉลากก่อนบริโภค · ผลลัพธ์แตกต่างกันในแต่ละบุคคล",
        "ความคิดเห็นในคลิปเป็นประสบการณ์ส่วนบุคคลของผู้ใช้"]
DISC_HMB = DISC[:2] + ["เด็กและสตรีมีครรภ์ไม่ควรรับประทาน · มีส่วนประกอบจากนมและถั่วเหลือง", DISC[2]]
DISC_X = ["Xircle ใช้เพื่อติดตามพฤติกรรมสุขภาพ ไม่ใช่การวินิจฉัยโรค", "ความคิดเห็นในคลิปเป็นประสบการณ์ส่วนบุคคลของผู้ใช้"]

# product cards that slide in when a product is named: key -> (image in assets/, name, line under it)
PRODUCTS = {
    "hmb": ("hmb.png", "Protein HMB+", "Habix · ผลิตภัณฑ์เสริมอาหาร"),
    "gus": ("gus.png", "G.U.S.+", "Habix · ผลิตภัณฑ์เสริมอาหาร"),
    "asta": ("asta.jpg", "AstaMega+", "Habix · ผลิตภัณฑ์เสริมอาหาร"),
    "set": ("routinex-pack.png", "RoutineX", "รวมผลิตภัณฑ์ Habix ไว้ใน Routine เดียว"),   # V.2: Daily Routine Pack + ซอง Habix (พื้นใสจริง แทนภาพ PD-03 ใบที่ 3)
    # DK-05: Habix Flavor+ ภาพทางการจากการ์ดสินค้า PD-08 (ใช้เมื่อพูดถึง Flavor / Cocoa Noir / Hakuto Peach / Midori)
    "flavor": ("habix-flavor.png", "Habix Flavor+", "ซองรสชาติ 3 รส"),
    "cocoa": ("habix-flavor-cocoa-noir.png", "Flavor+ Cocoa Noir", "Habix Flavor+"),
    "peach": ("habix-flavor-hakuto-peach.png", "Flavor+ Hakuto Peach", "Habix Flavor+"),
    "midori": ("habix-flavor-midori.png", "Flavor+ Midori", "Habix Flavor+"),
    "band": ("xircle-band.png", "Xircle Band", "สายรัดข้อมือติดตามพฤติกรรมสุขภาพ"),   # DK-05: ไดคัตพื้นโปร่ง
}

# words that turn gold in every subtitle (regex). A project may append its own.
KW = [r"Routine", r"My ?HMB", r"Core Duo", r"โปรตีน ?myHMB", r"โปรตีน ?HMB\+?", r"Protein HMB\+?", r"รูทีน", r"G\.U\.S\.\+?", r"กัส", r"แอสต้า", r"Habix", r"Xircle ?Band",
      r"อร่อย(มากๆ|มาก)?", r"ไม่หวาน", r"ไม่เลี่ยน", r"ไม่สาก", r"ฮอกไกโด", r"หอมพีช", r"ทุกวัน", r"ง่าย(ขึ้น)?มาก(ๆ)?", r"พกง่าย", r"สะดวก", r"ไม่ลืม",
      r"ประทับใจ(มากๆ|มาก)?", r"คอนเฟิร์ม", r"ต้องลอง", r"พลาด", r"ว้าวมาก", r"ลงตัว", r"ไม่เบื่อ", r"ทั้งบ้าน"]
FIX = []      # (regex, replacement) applied to the whole transcript before automatic subtitles

# คำเตือนอาหารเสริมตามบัญชี 4 ของประกาศ อย. หลักเกณฑ์การโฆษณาอาหาร พ.ศ. 2569: ขึ้นจอไม่น้อยกว่า 5 วินาที ตัวอักษรสูงไม่น้อยกว่า 1/25 ของภาพ
FDA_WARN = ["เด็กและสตรีมีครรภ์", "ไม่ควรรับประทาน", "ไม่มีผลในการป้องกัน", "หรือรักษาโรค", "อ่านคำเตือนในฉลาก", "ก่อนบริโภค"]

def P(a, b, who="B", subs=None, x=None, z=None, q=False, tight=True, slam=False, chips=(), cards=(), sfx=(), flash=(), tag=None, snap=True, ins=(), apps=()):
    """one piece of the source tape.
    who  = a key of PEOPLE (the reviewer on screen), or (key, x); x = where the face is, 0 left .. 1 right
    tag  = True -> name tag from PEOPLE, or (name, role), or None
    snap = move the in/out points onto the start/end of speech (within 0.35 s); False for shots under ~1.5 s
    ins  = inserts of round 2: dict(file=..., at=seconds from the piece start or "m:ss.s", dur=2.2, fit="cover"|"panel")"""
    key = who
    if isinstance(who, (tuple, list)): key, x = who[0], who[1]
    return dict(a=T(a), b=T(b), z=z, who=key, x=x, subs=subs, q=q, tight=tight, slam=slam, chips=chips, cards=cards, sfx=sfx, flash=flash,
                tag=tag, snap=snap, ins=list(ins), apps=list(apps))

def END(title, sub, search, img="hmb.png", logo="habix-white.png", over="", disc=DISC, **k):
    """end card: title (2 lines, \\n), line under it, the words typed into the search bar, product picture"""
    return dict(title=title, sub=sub, search=search, img=img, logo=logo, over=over, disc=disc, **k)

E_HMB = END("อร่อยแค่ไหน\n*ต้องลองเอง*", "Protein HMB+ · ผลิตภัณฑ์เสริมอาหารจาก Habix", "Habix Protein HMB+", img="hmb.png", disc=DISC_HMB)
E_SET = END("เริ่ม *Routine* ของคุณ\nได้ตั้งแต่วันนี้", "เซ็ต RoutineX · ผลิตภัณฑ์ Habix ครบใน Routine เดียว", "Habix RoutineX", img="routinex-open.png", imgh=560, imgtop=420, disc=DISC_HMB)   # V.2: ภาพจริงจากการ์ด PD-03
E_GUS = END("ใยอาหารที่\n*ทานง่าย* ทุกวัน", "G.U.S.+ · ผลิตภัณฑ์เสริมอาหารจาก Habix", "Habix G.U.S.+", img="gus.png")
E_BAND = END("เห็นพฤติกรรมตัวเอง\n*ชัดขึ้นทุกวัน*", "Xircle Band · กิน นอน ขยับ ครบในแอปเดียว", "Xircle Band", img="xircle-band.png", logo="xircle-logo.png", bg="endbg-xircle.jpg",
             theme="light", imgh=470, imgtop=470, disc=DISC_X)
XIRCLE = dict(brand="xircle", kicker="XIRCLE BAND · รีวิวจากผู้ใช้จริง", note=NOTE_XIRCLE)

CLIPS = []
def C(name, head, pieces, end, **k):
    """one episode. name = code shown in the review page (first letter = group), head = 2 opening lines.
    k: title, product, level ("G" ok / "Y" has personal result numbers), risk, check, brand, kicker, note, kw, music_under_db"""
    CLIPS.append(dict(name=name, head=head, pieces=pieces, end=end, **k))

# ---------- DK-05: picture codes in a person's folder ----------
# BF = before (heaviest, before Routine / Lean Lab) · AF = after · X = wearing the Xircle band · E = food / eating Routine
# M = moving: exercise, walking, running, gym · app = Xircle app screenshot (goes in a phone mock-up, see APP)
import os as _os, re as _re
_PIC = (".jpg", ".jpeg", ".png", ".webp")
def _codes(folder, code):
    from common import PROJ
    d = folder if _os.path.isabs(folder) else _os.path.join(PROJ, folder)
    out = [f for f in _os.listdir(d) if _os.path.splitext(f)[1].lower() in _PIC and _re.fullmatch(code + r"\d+", _os.path.splitext(f)[0], _re.I)]
    return sorted(out, key=lambda f: int(_re.findall(r"\d+", f)[0]))

def bfaf_each(n):
    """DK-05 (25 พ.ย. 69): seconds per picture in a BF or AF group: 3 pictures or more = 1 s each, fewer than 3 = 2 s each"""
    return 1.0 if n >= 3 else 2.0

def SEQ(folder, code, at, each=None):
    """every picture of one code, one after another, starting at `at` (tape time "m:ss.s").
    code "BF" = all BF pictures then all AF pictures. Each group is timed on its own: 3+ pictures = 1 s each, 1–2 pictures = 2 s each
    (pass each= to force one length). "E" · "M" · "X" (any other prefix works too) = 1 s each unless each= is given.
    The run cuts hard between pictures, dissolves only in and out, and may run on into the next piece."""
    rel = folder.rstrip("/\\") + "/"
    if code.upper() == "BF":
        groups = [g for g in (_codes(folder, "BF"), _codes(folder, "AF")) if g]
        timed = [(f, each or bfaf_each(len(g))) for g in groups for f in g]
    else:
        timed = [(f, each or 1.0) for f in _codes(folder, code)]
    if not timed: raise SystemExit(f"SEQ: ไม่พบภาพรหัส {code} ใน {folder}")
    out, t, n = [], 0.0, len(timed)
    for i, (f, d) in enumerate(timed):
        out.append(dict(file=rel + f, at=at, after=round(t, 3), dur=d, span=True, fin=(i == 0), fout=(i == n - 1))); t += d
    return out

def BA(folder, at, dur=3.0, gap=0.3, pair=False):
    """before/after: by default the DK-05 run (all BF, then all AF; 3+ pictures 1 s each, 1–2 pictures 2 s each) = SEQ(folder, "BF", at)
    pair=True: the older V.2 look, BF left + AF right side by side in one frame, `dur` seconds per pair"""
    if not pair: return SEQ(folder, "BF", at)
    bf, af = _codes(folder, "BF"), _codes(folder, "AF")
    if not bf or not af: raise SystemExit(f"BA: ต้องมีทั้งภาพ BF และ AF ใน {folder} (พบ BF {len(bf)} · AF {len(af)})")
    num = lambda f: _re.findall(r"\d+", f)[0]
    pairs = []
    for b in list(bf):
        m = [a for a in af if num(a) == num(b)]
        if m: pairs.append((b, m[0])); bf.remove(b); af.remove(m[0])
    pairs += list(zip(bf, af))
    rel = folder.rstrip("/\\") + "/"
    return [dict(file=rel + b, file2=rel + a, at=at, after=i * (dur + gap), dur=dur, fit="pair", span=True) for i, (b, a) in enumerate(pairs)]

def APP(file, at, dur=3.5, eat=None, move=None, sleep=None, habit=None, title="Xircle App"):
    """Xircle app screenshot inside a phone mock-up on the left, its scores as big text on the right.
    Read EAT / MOVE / SLEEP / HABIT from the screenshot itself; leave out a value you cannot read (never make one up)."""
    return dict(img=file, at=at, dur=dur, eat=eat, move=move, sleep=sleep, habit=habit, title=title)

# ---------- DK-05: Xircle app screens from the source cards UI-01, UI-03, UI-04 ----------
# The screens show sample data from a real account, so they are NOT shipped with the skill.
# Put the approved screens in kit/assets/ui/ under the file names below (see kit/assets/ui/README.txt).
# สกรีนจากการ์ด Source ตัดแถบสถานะ/ปุ่มโทรศัพท์ออกแล้ว อยู่ใน kit/assets/ui/
UI = {
    "home":    ("home.jpg", "UI-01", "หน้าแรก", "Sleep · Eat · Move · Habits ในหน้าเดียว"),
    "scan":    ("eat-ai-scan.jpg", "UI-03", "AI Food Scan", "ถ่ายรูปอาหาร AI วิเคราะห์ให้"),
    "nutri":   ("add-eat-krapow.jpg", "UI-03", "ข้อมูลสารอาหาร", "โปรตีน คาร์บ ไขมัน แคลอรีของมื้อ"),
    "eatlog":  ("eat-log.jpg", "UI-03", "Eat Log", "บันทึกมื้ออาหารทั้งวัน"),
    "balance": ("energy-balance.jpg", "UI-04", "สมดุลพลังงาน", "กินเข้า เทียบกับเผาผลาญ"),
}
def UISEQ(at, keys=("home", "scan", "nutri", "eatlog", "balance"), each=1.0, after=0.0):
    """Xircle app screens in the phone mock-up, `each` seconds apiece, the phone stays put between screens.
    Right side shows the feature name. Use in Xircle clips when the person talks about the app."""
    d = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "assets", "ui")
    out = []
    keys = [k for k in keys if _os.path.exists(_os.path.join(d, UI[k][0])) or print(f"UISEQ: ไม่มีสกรีน {UI[k][0]} ใน kit/assets/ui/ ข้ามภาพนี้ (อ่าน kit/assets/ui/README.txt)")]
    for i, k in enumerate(keys):
        f, no, label, note = UI[k]
        out.append(dict(img=_os.path.join(d, f).replace("\\", "/"), at=at, after=after + i * each, dur=each, label=label, note=note, card=no,
                        cont=(i > 0 or after > 0), last=(i == len(keys) - 1), title="Xircle App"))
    return out
