"""dialogue + SFX (mono, centred) + music bed from <project>/music (stereo) -> mix.wav (stereo, -14 LUFS)"""
import os, math, json, re, subprocess
import numpy as np, soundfile as sf

import common

def bed_file():
    """music bed: the first audio file in <project>/music/ (bed.* wins). None = no music."""
    d = os.path.join(common.PROJ, "music")
    if not os.path.isdir(d): return None
    fs = sorted(f for f in os.listdir(d) if f.lower().endswith((".wav", ".mp3", ".m4a", ".aac", ".flac")))
    fs.sort(key=lambda f: not f.lower().startswith("bed"))
    return os.path.join(d, fs[0]) if fs else None

def _decode(path, sr):
    """any audio file -> float stereo at sr (through ffmpeg, so mp3/m4a work too)"""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "2", "-ar", str(sr), "-af", "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.02",
                          "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)

def _load(path, sr, mono=True):
    x, xsr = sf.read(path, always_2d=True)
    if mono: x = x.mean(axis=1, keepdims=True)
    if xsr != sr:
        idx = np.arange(0, len(x), xsr / sr); x = np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in range(x.shape[1])], axis=1)
    return x

def sfx_file(sfx_dir, name):
    """the kit ships its effects as .flac (the source repo keeps .wav out of git); a .wav of the same name also works"""
    for ext in (".flac", ".wav"):
        p = os.path.join(sfx_dir, name + ext)
        if os.path.exists(p): return p
    raise SystemExit(f"ไม่พบเสียงเอฟเฟกต์ {name} ใน {sfx_dir} (ต้องมี {name}.flac) ลองโหลดการ์ดสกิลใหม่ แล้วรัน rv doctor")

def mix(out, tl, sfx_dir):
    dial, sr = sf.read(os.path.join(out, "dial.wav"))
    N = int(round(tl["total"] * sr))
    m = np.zeros(N + sr); m[:min(len(dial), N)] += dial[:N]
    for n, t, g in tl["sfx"]:
        x = _load(sfx_file(sfx_dir, n), sr)[:, 0]
        i0 = max(0, int(t * sr)); seg = x[: max(0, min(len(x), len(m) - i0))] * (10 ** (g / 20))
        m[i0:i0 + len(seg)] += seg
    st = np.stack([m[:N], m[:N]], axis=1)
    bedf = bed_file()
    if bedf:
        bed = _decode(bedf, sr)
        if len(bed) < N: bed = np.tile(bed, (int(math.ceil(N / len(bed))), 1))
        bed = bed[:N]
        t = np.arange(N) / sr; body = tl["body"]
        # under the voice: low; lifts into the end card; fades to silence
        # music rides a fixed distance under THIS clip's voice (18 dB by default), not a fixed file gain
        nb = int(tl["body"] * sr); act = m[:nb][np.abs(m[:nb]) > 10 ** (-45 / 20)]
        dial_db = 20 * np.log10(np.sqrt(np.mean(act ** 2)) + 1e-12) if len(act) > sr else -20.0
        bed_rms = 20 * np.log10(np.sqrt(np.mean(bed[:nb, 0] ** 2)) + 1e-12)
        under = tl.get("music_under_db", 20)
        g = np.full(N, 10 ** ((dial_db - under - bed_rms) / 20))
        tl["_bed_gain_db"] = round(dial_db - under - bed_rms, 1); tl["_dial_db"] = round(dial_db, 1)
        lift = np.clip((t - (body - 0.4)) / 0.6, 0, 1); g *= 10 ** (lift * 12 / 20)
        g *= np.clip(t / 0.25, 0, 1) * np.clip((tl["total"] - t) / 1.3, 0, 1)
        st += bed * g[:, None]
    raw = os.path.join(out, "mix_raw.wav")
    sf.write(raw, st, sr, subtype="FLOAT")
    # two-pass loudness: measure, then one linear gain to -14 LUFS with a peak limiter
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    js = json.loads(re.search(r"\{[^{}]*\}", r.stderr[r.stderr.rfind("Parsed_loudnorm"):], re.S).group(0))
    gain = -14.0 - float(js["input_i"])
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af", f"volume={gain:.2f}dB,alimiter=limit=0.84:attack=2:release=40:level=disabled",
                        "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", os.path.join(out, "mix.wav")], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode: raise SystemExit(r.stderr[-2000:])
    os.remove(raw)
    print(f"  mix ok (voice {tl.get('_dial_db', '-')} dB, music {tl.get('_bed_gain_db', 'ไม่มีเพลง')} dB, master {gain:+.1f} dB)")
