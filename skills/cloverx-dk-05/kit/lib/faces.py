"""Scan the source at 2 fps and store every detected face (normalised cx, cy, w) per time."""
import subprocess, json, sys, os, numpy as np, cv2
import common
SRC = common.config()["source_path"]
W, H, FPS = 540, 960, 2
fc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
pc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", SRC, "-vf", f"fps={FPS},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
out, i = {}, 0
while True:
    raw = p.stdout.read(W * H)
    if len(raw) < W * H: break
    g = np.frombuffer(raw, np.uint8).reshape(H, W)
    fs = []
    for (x, y, w, h) in fc.detectMultiScale(g, 1.1, 6, minSize=(70, 70)):
        fs.append([round((x + w / 2) / W, 4), round((y + h / 2) / H, 4), round(w / W, 4), "f"])
    for flip in (False, True):
        img = g[:, ::-1] if flip else g
        for (x, y, w, h) in pc.detectMultiScale(np.ascontiguousarray(img), 1.1, 6, minSize=(70, 70)):
            if flip: x = W - x - w
            c = [round((x + w / 2) / W, 4), round((y + h / 2) / H, 4), round(w / W, 4), "p"]
            if not any(abs(c[0] - f[0]) < 0.12 and abs(c[1] - f[1]) < 0.08 for f in fs): fs.append(c)
    out[f"{i / FPS:.1f}"] = fs
    i += 1
    if i % 400 == 0: print(i, flush=True)
os.makedirs(common.WORK, exist_ok=True); json.dump(out, open(common.FACES, "w"))
print("done", i)
