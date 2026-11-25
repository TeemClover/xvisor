"""Speech to text for the kit, on any machine.
Apple-chip Macs use mlx-whisper; every other machine (Windows, Intel Mac, Linux) uses faster-whisper on the CPU.
rv picks the backend and exports RV_STT=mlx|fw; both return the same shape: {"text", "segments":[{start,end,text,words:[{word,start,end}]}]}.
As a script (through rv): stt.py <audio> <out.json>   writes the whole-tape transcript rv prep needs."""
import os, sys, json, platform

BACKEND = os.environ.get("RV_STT") or ("mlx" if (platform.system(), platform.machine()) == ("Darwin", "arm64") else "fw")
MLX_MODEL = "mlx-community/whisper-large-v3-mlx"
FW_MODEL = os.environ.get("RV_FW_MODEL", "large-v3-turbo")   # the full large-v3 is too slow on a laptop CPU
_fw = None

def transcribe(audio, word_timestamps=False):
    """audio: a file path, or mono float32 samples at 16 kHz"""
    if BACKEND == "mlx":
        import mlx_whisper
        return mlx_whisper.transcribe(audio, path_or_hf_repo=MLX_MODEL, language="th", word_timestamps=word_timestamps,
                                      condition_on_previous_text=False, verbose=None)
    global _fw
    if isinstance(audio, str):   # decode with ffmpeg (the kit needs it anyway) so the result does not depend on the PyAV build
        import subprocess, numpy as np
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", audio, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
        audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    if _fw is None:
        from faster_whisper import WhisperModel
        _fw = WhisperModel(FW_MODEL, device="cpu", compute_type="int8")
    segs, _ = _fw.transcribe(audio, language="th", word_timestamps=word_timestamps, condition_on_previous_text=False)
    out = []
    for s in segs:
        d = dict(start=float(s.start), end=float(s.end), text=s.text)
        if word_timestamps: d["words"] = [dict(word=w.word, start=float(w.start), end=float(w.end)) for w in (s.words or [])]
        out.append(d)
    return dict(text="".join(s["text"] for s in out), segments=out)

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    r = transcribe(src, word_timestamps=True)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    json.dump(dict(text=r["text"], segments=r["segments"], language="th"), open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    print(len(r["segments"]), "ช่วง ·", "mlx-whisper" if BACKEND == "mlx" else f"faster-whisper {FW_MODEL}")
