"""Final audio: narration over the bed (ducked), then mux with the rendered video.

python finalize.py   -> final.wav + uch_kun_final.mp4
"""
import json, os, subprocess, wave
import numpy as np
import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 24000
FF = imageio_ffmpeg.get_ffmpeg_exe()


def load(name):
    with wave.open(os.path.join(HERE, name), "rb") as w:
        assert w.getframerate() == SR, (name, w.getframerate())
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64) / 32768.0


voice, bed = load("narration.wav"), load("mix.wav")
n = max(len(voice), len(bed))
voice = np.pad(voice, (0, n - len(voice)))
bed = np.pad(bed, (0, n - len(bed)))

# envelope follower for ducking (20 ms window)
win = int(0.02 * SR)
env = np.abs(voice)
env = np.convolve(env, np.ones(win) / win, mode="same")
env = np.clip(env / 0.08, 0, 1)
# smooth the gain curve so it never jumps
gain = 1.0 - 0.62 * env
k = int(0.15 * SR)
gain = np.convolve(gain, np.ones(k) / k, mode="same")

bed = bed * 0.9 * gain
voice = voice * 1.0
mixed = voice + bed

peak = np.max(np.abs(mixed))
mixed = mixed / peak * 0.89
fade = int(0.3 * SR)
mixed[:fade] *= np.linspace(0, 1, fade)
mixed[-fade:] *= np.linspace(1, 0, fade)

with wave.open(os.path.join(HERE, "final.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(mixed, -1, 1) * 32767).astype("<i2").tobytes())

src = os.path.join(HERE, "uch_kun.mp4")
dst = os.path.join(HERE, "uch_kun_final.mp4")
subprocess.run([FF, "-y", "-loglevel", "error", "-i", src, "-i", os.path.join(HERE, "final.wav"),
                "-map", "0:v", "-map", "1:a",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                "-vf", "scale=in_range=full:out_range=tv", "-r", "30",
                "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", dst], check=True)
print("ok", dst, round(os.path.getsize(dst) / 1e6, 2), "MB")
