"""second reading of each clip's own dialogue (tightened, original speed): does the cut clip the words, do the subtitles match?
usage (through rv): qa <CLIP...>   prints A: what the model heard at final speed / S: the subtitles"""
import sys, os, stt
import common
for name in sys.argv[1:]:
    d = os.path.join(common.BUILD, name); out = []
    for f in ("dial.wav",):                         # DK-05: one reading of the finished dialogue (final speed) is enough
        r = stt.transcribe(os.path.join(d, f))
        out.append(" | ".join(f"{s['start']:.1f} {s['text'].strip()}" for s in r["segments"]))
    open(os.path.join(d, "heard.txt"), "w", encoding="utf-8").write("\n".join(out))
    subs = " / ".join(l[14:].strip().replace("*", "") for l in open(os.path.join(d, "subs.txt"), encoding="utf-8").read().splitlines())
    print("==", name); print("A :", out[0]); print("S :", subs, flush=True)
