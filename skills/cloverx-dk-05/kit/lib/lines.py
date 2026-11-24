"""work/transcript/a16.json -> lines.txt (one spoken line per row with its time)"""
import json, os, common
d = json.load(open(common.WORDS, encoding="utf-8"))
out = [f"{int(s['start'] // 60)}:{s['start'] % 60:05.2f}-{s['end'] % 60:05.2f} {s['text'].strip()}" for s in d["segments"]]
open(os.path.join(os.path.dirname(common.WORDS), "lines.txt"), "w", encoding="utf-8").write("\n".join(out))
print(len(out), "บรรทัด")
