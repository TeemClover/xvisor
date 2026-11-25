"""What a project's edl.py imports: piece and clip builders, brand presets, subtitle keywords.
Times are source times "m:ss.ss".  A subtitle line may be (text, "B") = big punch word, (text, "Q") = the interviewer.
*word* inside a line turns it HabiX green (DK-05)."""
from common import T

ZCYCLE = [1.0, 1.16, 1.06, 1.24]          # zoom levels the cuts walk through
NOTE = "ความคิดเห็นส่วนบุคคลของผู้ใช้ · ผลลัพธ์แตกต่างกันในแต่ละบุคคล"
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
    "set": ("duo.png", "เซ็ต RoutineX", "รวมผลิตภัณฑ์ Habix ไว้ในรูทีนเดียว"),
    "band": ("band-sq.jpg", "Xircle Band", "สายรัดข้อมือติดตามพฤติกรรมสุขภาพ"),
}

# words that turn gold in every subtitle (regex). A project may append its own.
KW = [r"โปรตีน ?myHMB", r"โปรตีน ?HMB\+?", r"Protein HMB\+?", r"รูทีน", r"G\.U\.S\.\+?", r"กัส", r"แอสต้า", r"Habix", r"Xircle ?Band",
      r"อร่อย(มากๆ|มาก)?", r"ไม่หวาน", r"ไม่เลี่ยน", r"ไม่สาก", r"ฮอกไกโด", r"หอมพีช", r"ทุกวัน", r"ง่าย(ขึ้น)?มาก(ๆ)?", r"พกง่าย", r"สะดวก", r"ไม่ลืม",
      r"ประทับใจ(มากๆ|มาก)?", r"คอนเฟิร์ม", r"ต้องลอง", r"พลาด", r"ว้าวมาก", r"ลงตัว", r"ไม่เบื่อ", r"ทั้งบ้าน"]
FIX = []      # (regex, replacement) applied to the whole transcript before automatic subtitles

# คำเตือนอาหารเสริมตามบัญชี 4 ของประกาศ อย. หลักเกณฑ์การโฆษณาอาหาร พ.ศ. 2569: ขึ้นจอไม่น้อยกว่า 5 วินาที ตัวอักษรสูงไม่น้อยกว่า 1/25 ของภาพ
FDA_WARN = ["เด็กและสตรีมีครรภ์", "ไม่ควรรับประทาน", "ไม่มีผลในการป้องกัน", "หรือรักษาโรค", "อ่านคำเตือนในฉลาก", "ก่อนบริโภค"]

def P(a, b, who="B", subs=None, x=None, z=None, q=False, tight=True, slam=False, chips=(), cards=(), sfx=(), flash=(), tag=None, snap=True, ins=()):
    """one piece of the source tape.
    who  = a key of PEOPLE (the reviewer on screen), or (key, x); x = where the face is, 0 left .. 1 right
    tag  = True -> name tag from PEOPLE, or (name, role), or None
    snap = move the in/out points onto the start/end of speech (within 0.35 s); False for shots under ~1.5 s
    ins  = inserts of round 2: dict(file=..., at=seconds from the piece start or "m:ss.s", dur=2.2, fit="cover"|"panel")
           DK-05 before/after: dict(bf="inserts/.../BF1.jpg", af="inserts/.../AF1.jpg", at=..., dur=2.6) -> BF left, AF right in one frame (red level)"""
    key = who
    if isinstance(who, (tuple, list)): key, x = who[0], who[1]
    return dict(a=T(a), b=T(b), z=z, who=key, x=x, subs=subs, q=q, tight=tight, slam=slam, chips=chips, cards=cards, sfx=sfx, flash=flash,
                tag=tag, snap=snap, ins=list(ins))

def END(title, sub, search, img="hmb.png", logo="habix-white.png", over="", disc=DISC, **k):
    """end card: title (2 lines, \\n), line under it, the words typed into the search bar, product picture"""
    return dict(title=title, sub=sub, search=search, img=img, logo=logo, over=over, disc=disc, **k)

E_HMB = END("อร่อยแค่ไหน\n*ต้องลองเอง*", "Protein HMB+ · ผลิตภัณฑ์เสริมอาหารจาก Habix", "Habix Protein HMB+", img="hmb.png", disc=DISC_HMB)
E_SET = END("เริ่ม*รูทีน*ของคุณ\nได้ตั้งแต่วันนี้", "เซ็ต RoutineX · ผลิตภัณฑ์ Habix ครบในรูทีนเดียว", "Habix RoutineX", img="duo.png", imgh=520, imgtop=440, disc=DISC_HMB)
E_GUS = END("ใยอาหารที่\n*ทานง่าย* ทุกวัน", "G.U.S.+ · ผลิตภัณฑ์เสริมอาหารจาก Habix", "Habix G.U.S.+", img="gus.png")
E_BAND = END("เห็นพฤติกรรมตัวเอง\n*ชัดขึ้นทุกวัน*", "Xircle Band · กิน นอน ขยับ ครบในแอปเดียว", "Xircle Band", img="band-sq.jpg", logo="xircle-logo.png",
             theme="light", imgh=470, imgtop=470, disc=DISC_X)
XIRCLE = dict(brand="xircle", kicker="XIRCLE BAND · รีวิวจากผู้ใช้จริง", note=NOTE_XIRCLE)

CLIPS = []
def C(name, head, pieces, end, **k):
    """one episode. name = code shown in the review page (first letter = group), head = 2 opening lines.
    k: title, product, level ("G" ok / "Y" has personal result numbers), risk, check, brand, kicker, note, kw, music_under_db"""
    CLIPS.append(dict(name=name, head=head, pieces=pieces, end=end, **k))
