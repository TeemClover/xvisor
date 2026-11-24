"""Paths and project settings shared by every tool of the kit.
PROJECT = the folder the editor works in (RV_PROJECT or the current folder); KIT = this kit."""
import os, sys, json

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = os.path.abspath(os.environ.get("RV_PROJECT") or os.getcwd())
WORK = os.path.join(PROJ, "work")
BUILD = os.path.join(PROJ, "build")
EXPORTS = os.path.join(PROJ, "exports")
INSERTS = os.path.join(PROJ, "inserts")
A16 = os.path.join(WORK, "audio", "a16.wav")
A48 = os.path.join(WORK, "audio", "a48.wav")
FACES = os.path.join(WORK, "faces.json")
WORDS = os.path.join(WORK, "transcript", "a16.json")
PIECES = os.path.join(WORK, "transcript", "pieces.json")
SFX = os.path.join(KIT, "sfx")

def config():
    f = os.path.join(PROJ, "project.json")
    if not os.path.exists(f): sys.exit(f"ไม่พบ project.json ใน {PROJ} — สั่ง rv init <ไฟล์วิดีโอ> ก่อน")
    c = json.load(open(f, encoding="utf-8"))
    c.setdefault("speed", 1.12); c.setdefault("fps", 30)
    src = c["source"]; c["source_path"] = src if os.path.isabs(src) else os.path.join(PROJ, src)
    return c

def load_edl():
    """the project's edl.py (it imports edlkit from this kit)"""
    for p in (os.path.join(KIT, "lib"), PROJ):
        if p not in sys.path: sys.path.insert(0, p)
    import edl
    return edl

def asset(name):
    """project assets win over the kit's"""
    for base in (os.path.join(PROJ, "assets"), os.path.join(KIT, "assets")):
        p = os.path.join(base, name)
        if os.path.exists(p): return p
    return os.path.join(KIT, "assets", name)

def T(s):
    if isinstance(s, (int, float)): return float(s)
    m, x = s.split(":"); return int(m) * 60 + float(x)

def F(t): return f"{int(t // 60)}:{t % 60:05.2f}"
