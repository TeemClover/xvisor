#!/usr/bin/env python3
"""Build generated files from the single source in skills/xvisor and manifest.json.

  python3 scripts/build.py          write version.md, X-VISOR-START.md, X-VISOR-QUICK.md, downloads/xvisor-skill.zip
  python3 scripts/build.py --check  fail if any generated file is out of date

Standard library only. Output is deterministic (sorted entries, fixed zip timestamps).
"""
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf8"))
SKILL_DIR = ROOT / MANIFEST["files"]["skillDir"]
REF_ORDER = [
    "welcome.md",
    "journey.md",
    "clip-playbook.md",
    "example-scale-no-camera.md",
    "edit-and-review.md",
    "setup-machine.md",
    "channel-plan.md",
    "products.md",
    "claims.md",
    "assets.md",
    "links.md",
    "learn.md",
    "company.md",
    "faq.md",
    "version.md",
]
# The small fallback file for phones: enough for a first clip or review, about a third of X-VISOR-START.md.
QUICK_ORDER = ["welcome.md", "journey.md", "clip-playbook.md", "edit-and-review.md", "claims.md", "faq.md", "version.md"]


def version_md() -> str:
    m = MANIFEST
    return (
        "# เวอร์ชันของชุดนี้\n\n"
        f"- ชุดสกิล: {m['title']}\n"
        f"- เวอร์ชัน: {m['version']}\n"
        f"- อัปเดตล่าสุด: {m['updated']}\n"
        f"- ต้นทาง: {m['repo']}\n\n"
        "ข้อมูลสินค้าและลิงก์ในชุดนี้สรุปจากหน้าเว็บสาธารณะ ณ วันที่ข้างบน "
        "ถ้าผู้ใช้ถามว่าข้อมูลใหม่แค่ไหน ให้บอกวันที่นี้ และแนะนำให้ตรวจหน้าทางการก่อนโพสต์\n"
    )


def read(rel: str) -> str:
    return (SKILL_DIR / rel).read_text(encoding="utf8").replace("\r\n", "\n")


def starter_md() -> str:
    parts = [
        "# X-VISOR START · ไฟล์เริ่มต้นไฟล์เดียว\n",
        f"เวอร์ชัน {MANIFEST['version']} · อัปเดต {MANIFEST['updated']} · ต้นทาง {MANIFEST['repo']}\n",
        "ไฟล์นี้รวมทุกอย่างที่ AI ต้องใช้เพื่อช่วย X-VISOR ทำผลงานแรก ผู้ใช้แนบไฟล์นี้ในแชต หรือวางเนื้อหาทั้งหมดลงในแชต "
        "AI อ่านส่วนที่ต้องใช้ได้เลย ไม่ต้องเปิดลิงก์อื่น ส่วนที่ขึ้นต้นด้วย `FILE:` คือไฟล์ในชุดสกิลที่ SKILL.md อ้างถึง\n",
        "ลิงก์รูปในส่วน assets เปิดดูได้ผ่านเบราว์เซอร์ AI ที่เปิดลิงก์ไม่ได้ให้บอกผู้ใช้ตามจริง\n",
        "\n---\nFILE: SKILL.md\n---\n",
        read("SKILL.md"),
    ]
    for name in REF_ORDER:
        body = version_md() if name == "version.md" else read(f"references/{name}")
        parts.append(f"\n---\nFILE: references/{name}\n---\n")
        parts.append(body)
    out = "\n".join(p.rstrip("\n") + "\n" for p in parts)
    out = out.replace("`assets/", f"`{MANIFEST['rawBase']}assets/")
    return out


def quick_md() -> str:
    parts = [
        "# X-VISOR QUICK · ไฟล์สั้นสำหรับคลิปแรกและคลิปรีวิว\n",
        f"เวอร์ชัน {MANIFEST['version']} · อัปเดต {MANIFEST['updated']} · ต้นทาง {MANIFEST['repo']}\n",
        "ไฟล์นี้ย่อจาก X-VISOR-START.md ให้แนบในแชตบนมือถือได้ง่าย มีคู่มือหลัก วิธีทำคลิป ลำดับตัด กติการีวิวและคำเสี่ยง "
        "ถ้าผู้ใช้ถามเรื่องสินค้า โลโก้ หรือแผนช่อง ให้บอกว่าไฟล์เต็มอยู่ที่ "
        f"{MANIFEST['rawBase']}{MANIFEST['files']['starter']}\n",
        "\n---\nFILE: SKILL.md\n---\n",
        read("SKILL.md"),
    ]
    for name in QUICK_ORDER:
        body = version_md() if name == "version.md" else read(f"references/{name}")
        parts.append(f"\n---\nFILE: references/{name}\n---\n")
        parts.append(body)
    return "\n".join(p.rstrip("\n") + "\n" for p in parts)


def skill_zip() -> bytes:
    files = {"xvisor/SKILL.md": read("SKILL.md").encode("utf8")}
    for name in REF_ORDER:
        body = version_md() if name == "version.md" else read(f"references/{name}")
        files[f"xvisor/references/{name}"] = body.encode("utf8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 23, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, files[name])
    return buf.getvalue()


def targets() -> dict:
    return {
        SKILL_DIR / "references" / "version.md": version_md().encode("utf8"),
        ROOT / MANIFEST["files"]["starter"]: starter_md().encode("utf8"),
        ROOT / MANIFEST["files"]["quick"]: quick_md().encode("utf8"),
        ROOT / MANIFEST["files"]["skillZip"]: skill_zip(),
    }


def main() -> int:
    check = "--check" in sys.argv
    stale = []
    for path, data in targets().items():
        if check:
            if not path.exists() or path.read_bytes() != data:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            print(f"wrote {path.relative_to(ROOT)} ({len(data)} bytes)")
    if stale:
        print("OUT OF DATE (run: python3 scripts/build.py): " + ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
