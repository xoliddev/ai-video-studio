"""Sound bed for video 5 — procedural, no external samples.

python mix.py  ->  mix.wav (24 kHz mono, ready for render.js)
"""
import json, os, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 24000
TL = json.load(open(os.path.join(HERE, "timeline.json"), encoding="utf-8"))
DUR = TL["duration"] + 0.4
N = int(DUR * SR)
t = np.arange(N) / SR
rng = np.random.default_rng(7)
mix = np.zeros(N)


def add(sig, at, gain=1.0):
    i = int(at * SR)
    j = min(N, i + len(sig))
    if i < N:
        mix[i:j] += sig[: j - i] * gain


def env(n, a, d, sustain=0.0):
    e = np.ones(n) * sustain
    na, nd = max(1, int(a * SR)), max(1, int(d * SR))
    na = min(na, n); nd = min(nd, n - na)
    e[:na] = np.linspace(0, 1, na)
    if nd > 0:
        e[na:na + nd] = np.linspace(1, 0, nd)
    return e


def bell(freq, dur=1.6, gain=1.0):
    n = int(dur * SR); tt = np.arange(n) / SR
    s = np.zeros(n)
    for k, f in enumerate((freq, freq * 2.01, freq * 3.02, freq * 4.7)):
        s += np.sin(2 * np.pi * f * tt) * np.exp(-tt * (3.2 + k * 1.4)) / (k + 1.6)
    return s * env(n, 0.004, dur) * gain


def tick(gain=1.0):
    n = int(0.055 * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * 1450 * tt) * 0.5 + rng.normal(0, .35, n)) * np.exp(-tt * 90) * gain


def whoosh(dur=0.5):
    n = int(dur * SR)
    noise = rng.normal(0, 1, n)
    # cheap one-pole lowpass sweep
    out = np.zeros(n); y = 0.0; a = 0.02
    for i in range(n):
        a = 0.02 + 0.35 * (i / n)
        y += a * (noise[i] - y); out[i] = y
    return out * np.sin(np.pi * np.arange(n) / n) ** 2


def paper(dur=0.7):
    n = int(dur * SR)
    noise = rng.normal(0, 1, n)
    out = np.zeros(n); y = 0.0
    for i in range(n):
        y += 0.12 * (noise[i] - y); out[i] = y
    crackle = (rng.random(n) > 0.9985) * rng.normal(0, .8, n)
    return (out * 2.6 + crackle) * np.sin(np.pi * np.arange(n) / n) ** 2


def pad(freqs, start, end, gain=0.20, attack=1.2, release=1.4):
    n = int((end - start) * SR); tt = np.arange(n) / SR
    s = np.zeros(n)
    for f in freqs:
        vib = 1 + 0.0015 * np.sin(2 * np.pi * 0.17 * tt + f)
        s += np.sin(2 * np.pi * f * tt * vib) + 0.25 * np.sin(2 * np.pi * f * 2 * tt)
    s /= len(freqs) * 1.25
    return s * env(n, attack, release, 1.0) * gain


# ---------- harmonic bed (scene times follow the narration) ----------
A2, C4, E4, A4, F4, G4 = 110.0, 261.63, 329.63, 440.0, 349.23, 392.0
S = [l["a"] for l in TL["lines"]]          # narration line starts
day1, day2, day3 = S[2], S[3], S[4]
chat, pay, parcels, close = S[5], S[6], S[7], S[8]

add(pad([A2, A2 * 1.5], 0, S[1], .16, .8, .9), 0)
add(pad([A2, C4 / 2, E4 / 2], S[1], day1, .13, .7, .8), S[1])
add(pad([A2, C4, E4], day1, day3 + 1.6, .12, .5, 1.2), day1)
add(pad([A2, E4, A4], day3 + 1.6, chat + .3, .13, .5, .9), day3 + 1.6)
add(pad([A2, A2 * 1.5], chat, pay, .10, .9, .9), chat)        # the quiet "I answered nobody"
add(pad([A2, C4, E4, A4], pay, parcels, .15, .6, 1.4), pay)
add(pad([F4 / 2, A4 / 2, C4], parcels, close, .15, .7, 1.6), parcels)
add(pad([A2, A4], close, DUR, .14, 1.0, 2.0), close)

# ---------- pulse while the days pass ----------
pulse_end = chat - 0.2
for base in (day1 + 0.2, day2 + 0.2, day3 + 0.2):
    for k in range(10):
        at = base + k * 0.375
        if at > pulse_end:
            break
        add(bell(220, 0.28, .05), at)

# ---------- sound events ----------
add(whoosh(.8), 0.1, .10)
add(tick(.5), S[0] + .9, .5)                  # phone wake
add(tick(.7), S[0] + 1.5, .55)
add(whoosh(.7), S[1] - .1, .10)
add(paper(.8), day1 - .18, .18)
for k in range(4):  add(tick(.8), day1 + .45 + k * 0.22, .55)
for k in range(7):  add(tick(.8), day2 + .45 + k * 0.17, .55)
for k in range(5):  add(tick(.8), day3 + .45 + k * 0.19, .55)
add(whoosh(.6), chat - .1, .08)
add(bell(880, 1.8, .30), pay + 2.4)           # payment confirmed
add(bell(1318.5, 1.2, .12), pay + 2.55)
add(paper(.9), parcels - .1, .16)
add(bell(880, 2.4, .34), close + 1.9)         # final chime
add(bell(1108.7, 2.0, .14), close + 2.05)

# ---------- master ----------
mix = mix / max(1e-9, np.max(np.abs(mix))) * 0.7
fade = int(0.25 * SR)
mix[:fade] *= np.linspace(0, 1, fade)
mix[-fade:] *= np.linspace(1, 0, fade)
pcm = (np.clip(mix, -1, 1) * 32767).astype("<i2")
with wave.open(os.path.join(HERE, "mix.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print("mix.wav", round(len(pcm) / SR, 2), "s")
