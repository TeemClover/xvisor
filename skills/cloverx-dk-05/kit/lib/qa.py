"""second reading of each clip's own dialogue (tightened, original speed): does the cut clip the words, do the subtitles match?
usage (through rv): qa <CLIP...>   prints A: what the model heard / S: the subtitles"""
import sys, os, mlx_whisper
import common
MODEL = "mlx-community/whisper-large-v3-mlx"
for name in sys.argv[1:]:
    d = os.path.join(common.BUILD, name); out = []
    for f in ("dial_src.wav", "dial.wav"):          # two readings: original speed and final speed
        r = mlx_whisper.transcribe(os.path.join(d, f), path_or_hf_repo=MODEL, language="th", condition_on_previous_text=False, verbose=None)
        out.append(" | ".join(f"{s['start']:.1f} {s['text'].strip()}" for s in r["segments"]))
    open(os.path.join(d, "heard.txt"), "w", encoding="utf-8").write("\n".join(out))
    subs = " / ".join(l[14:].strip().replace("*", "") for l in open(os.path.join(d, "subs.txt"), encoding="utf-8").read().splitlines())
    print("==", name); print("A1:", out[0]); print("A2:", out[1]); print("S :", subs, flush=True)
