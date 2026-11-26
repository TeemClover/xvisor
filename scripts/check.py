#!/usr/bin/env python3
"""Pre-publish checks for the public xvisor repo. Standard library only.

  python3 scripts/check.py            offline checks (run in CI and before every push)
  python3 scripts/check.py --online   also open every external link (needs network)
"""
import json
import re
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
errors: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf8"))
skill_dir = ROOT / manifest["files"]["skillDir"]

# 1. manifest points at real files
for key in ("entry", "starter", "skillZip"):
    if not (ROOT / manifest["files"][key]).exists():
        fail(f"manifest.files.{key} missing: {manifest['files'][key]}")
for e in manifest["entries"]:
    for k in ("id", "label", "hint", "context"):
        if not e.get(k):
            fail(f"entry {e.get('id')} lacks {k}")
for l in manifest["lessons"]:
    for k in ("id", "no", "title", "minutes", "context"):
        if not l.get(k):
            fail(f"lesson {l.get('id')} lacks {k}")
if not manifest["prompts"]["start"].count(manifest["repo"]) == 1:
    fail("prompts.start must contain the repo URL exactly once")
if manifest["prompts"]["linkOnly"] != manifest["repo"]:
    fail("prompts.linkOnly must be exactly the repo URL")

readme = (ROOT / "README.md").read_text(encoding="utf8")
if manifest["prompts"]["start"] not in readme:
    fail("README.md must contain manifest prompts.start exactly")

# 2. SKILL.md frontmatter and references
skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf8")
m = re.match(r"---\nname: ([a-z0-9-]+)\ndescription: (.+)\n---\n", skill_md)
if not m or m.group(1) != "xvisor":
    fail("SKILL.md needs frontmatter with name: xvisor and a description")
elif len(m.group(2)) > 1024:
    fail("SKILL.md description is longer than 1024 characters")
for ref in set(re.findall(r"references/([a-z0-9-]+\.md)", skill_md)):
    if not (skill_dir / "references" / ref).exists():
        fail(f"SKILL.md names a missing file: references/{ref}")

# 2b. the DK-05 cutting skill ships whole: its own SKILL.md, the kit entry point, and every file it names
dk = ROOT / "skills" / "cloverx-dk-05"
dk_md = (dk / "SKILL.md").read_text(encoding="utf8")
if not re.match(r"^---\nname: cloverx-dk-05\ndescription: .+\n---\n", dk_md):
    fail("cloverx-dk-05/SKILL.md needs frontmatter with name: cloverx-dk-05 and a description")
for ref in set(re.findall(r"`((?:references|kit)/[\w./-]+)`", dk_md)):
    if not (dk / ref).exists():
        fail(f"cloverx-dk-05/SKILL.md names a missing file: {ref}")
if not (dk / "kit" / "rv").is_file():
    fail("cloverx-dk-05/kit/rv is missing")

# 3. assets listed and present
assets_md = (skill_dir / "references" / "assets.md").read_text(encoding="utf8")
listed = set(re.findall(r"`(assets/[^`]+)`", assets_md))
present = {p.relative_to(ROOT).as_posix() for p in (ROOT / "assets").rglob("*") if p.is_file() and p.name != ".DS_Store"}
for p in listed - present:
    fail(f"assets.md lists a missing file: {p}")
for p in present - listed:
    fail(f"asset not described in assets.md: {p}")

# 4. generated files up to date
r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py"), "--check"], capture_output=True, text=True)
if r.returncode:
    fail(r.stdout.strip() or "build --check failed")

# 5. zip matches the source
zpath = ROOT / manifest["files"]["skillZip"]
if zpath.exists():
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        if "xvisor/SKILL.md" not in names:
            fail("zip must contain xvisor/SKILL.md")
        if any(n.startswith("/") or ".." in n for n in names):
            fail("zip has unsafe paths")
        if z.read("xvisor/SKILL.md").decode("utf8") != skill_md:
            fail("zip SKILL.md differs from source")

# 6. nothing that should not be public
BAD_EXT = {".mp4", ".mov", ".mkv", ".wav", ".mp3", ".m4a", ".flac", ".env", ".pem", ".key", ".p12"}
BAD_TEXT = [
    (r"x\.myclover\.com", "internal office host"),
    (r"cloverx-office", "internal repo name"),
    (r"TomThanet", "private account name"),
    (r"/Users/", "local path"),
    (r"(?i)elevenlabs", "internal tool/key reference"),
    (r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*\S{8,}", "credential-looking value"),
    (r"\b(sk|pk)_[A-Za-z0-9]{16,}", "key-looking value"),
    (r"ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}", "token"),
    (r"(?i)\bผ่านการอนุมัติทางกฎหมาย", "legal-approval claim"),
]
tracked = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
for rel in filter(None, tracked):
    p = ROOT / rel
    if not p.is_file():
        continue
    # the cutting kit of the DK-05 skill ships eight short sound effects made in code (see its sfx/README.txt)
    if p.suffix.lower() in BAD_EXT and not rel.startswith("skills/cloverx-dk-05/kit/sfx/"):
        fail(f"forbidden file type: {rel}")
    size = p.stat().st_size
    if size > 2_000_000:
        fail(f"file larger than 2 MB: {rel}")
    if p.suffix.lower() in {".md", ".json", ".py", ".yml", ".txt", ".svg"} and rel != "scripts/check.py":
        text = p.read_text(encoding="utf8", errors="ignore")
        for pat, why in BAD_TEXT:
            if re.search(pat, text):
                fail(f"{rel}: {why} ({pat})")

# 7. relative markdown links resolve
for md in ROOT.rglob("*.md"):
    if ".git" in md.parts or "node_modules" in md.parts:  # node_modules is what `npm install` puts in the kit, never committed
        continue
    for target in re.findall(r"\]\((?!https?:|#|mailto:)([^)\s]+)\)", md.read_text(encoding="utf8")):
        if not (md.parent / target.split("#")[0]).exists():
            fail(f"{md.relative_to(ROOT)}: broken link {target}")

# 8. optional: every external link opens
if "--online" in sys.argv:
    PENDING = {"https://www.myclover.com/xvisor/play/"}
    urls = set()
    for md in list(skill_dir.rglob("*.md")) + [ROOT / "README.md", ROOT / "START-HERE.md"]:
        urls |= set(u.rstrip(".,") for u in re.findall(r"https?://[^\s)`>\]]+", md.read_text(encoding="utf8")))
    for u in sorted(urls):
        if u in PENDING or u.startswith("https://raw.githubusercontent.com/TeemClover/xvisor"):
            continue
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            code = urllib.request.urlopen(req, timeout=20).status
        except Exception as ex:  # noqa: BLE001
            code = getattr(ex, "code", str(ex))
        if code != 200:
            fail(f"link {code}: {u}")

if errors:
    print("FAIL")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("OK: xvisor repo checks passed")
