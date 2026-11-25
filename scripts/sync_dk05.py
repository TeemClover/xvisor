#!/usr/bin/env python3
"""Copy the latest DK-05 cutting skill into this repo, whole.

The DK-05 skill (customer review tape -> short vertical clip in HabiX tone) is kept up to date by CloverX's
production team in their own repository, from what X-VISOR users report. This repo ships a complete copy so an
X-VISOR's companion has everything here and never needs to reach that repository.

  python3 scripts/sync_dk05.py --from <path to the upstream skills/cloverx-dk-05 folder>
  python3 scripts/sync_dk05.py --from <...> --check      only report what would change

Then run scripts/build.py and scripts/check.py, raise the version in manifest.json and open a pull request.
Standard library only.
"""
import argparse
import filecmp
import hashlib
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "skills" / "cloverx-dk-05"
# never copied: notes for the upstream maintainers, installed packages, caches and anything a test run leaves behind
SKIP_NAMES = {"UPSTREAM.md", "node_modules", "__pycache__", ".DS_Store", ".pytest_cache"}
# the public copy must stand alone: scripts/check.py stops on any internal repository or account name in it


def files(base: Path) -> dict[str, Path]:
    out = {}
    for p in sorted(base.rglob("*")):
        rel = p.relative_to(base)
        if any(part in SKIP_NAMES for part in rel.parts) or p.is_symlink() or not p.is_file():
            continue
        out[rel.as_posix()] = p
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from", dest="src", required=True, help="the upstream skills/cloverx-dk-05 folder")
    ap.add_argument("--check", action="store_true", help="report changes without writing")
    a = ap.parse_args()
    src = Path(a.src).expanduser().resolve()
    if not (src / "SKILL.md").exists() or not (src / "kit" / "rv").exists():
        print(f"ไม่ใช่โฟลเดอร์สกิล DK-05: {src} (ต้องมี SKILL.md และ kit/rv)")
        return 2
    if not re.match(r"^---\nname: cloverx-dk-05\n", (src / "SKILL.md").read_text(encoding="utf8")):
        print("SKILL.md ต้นทางต้องมี name: cloverx-dk-05")
        return 2

    new, old = files(src), files(DEST) if DEST.exists() else {}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(r for r in set(new) & set(old) if not filecmp.cmp(new[r], old[r], shallow=False))
    for tag, group in (("+", added), ("~", changed), ("-", removed)):
        for r in group:
            print(f"  {tag} {r}")
    print(f"เพิ่ม {len(added)} · แก้ {len(changed)} · ลบ {len(removed)} · ทั้งหมด {len(new)} ไฟล์")
    if a.check or not (added or changed or removed):
        return 0

    for r in removed:
        (DEST / r).unlink()
    for r in added + changed:
        d = DEST / r
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(new[r], d)
    for d in sorted((p for p in DEST.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()
    (DEST / "kit" / "rv").chmod(0o755)
    digest = hashlib.sha256()
    for r in sorted(new):
        digest.update(r.encode() + b"\0" + new[r].read_bytes())
    print(f"คัดลอกแล้ว · ลายนิ้วมือชุดสกิล {digest.hexdigest()[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
