"""Narration for video 5 — takes are generated in GROUPS so the prosody flows,
then split on the silences Gemini leaves between sentences.

Voice: Vertex AI (gcloud ADC), model gemini-2.5-pro-tts, voice Charon.
python voice.py           # build takes (cached) + narration.wav + timeline.json
python voice.py force     # rebuild takes
"""
import array, base64, json, math, os, subprocess, sys, time, urllib.request, wave

HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.join(HERE, "audio")
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")  # your GCP project with Vertex AI enabled
REGION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
MODEL = "gemini-2.5-pro-tts"
VOICE = "Charon"
STYLE = ("Read the following as a calm, warm, cinematic Uzbek documentary narrator. "
         "Speak slowly, with quiet confidence and short natural pauses. Do not sound like an advertisement:\n\n")
SR = 24000
LEAD = 0.60

GROUPS = [
    [("Uch kun telefonimga qaramadim.", 0.75), ("Do'kon yopiq edi. Men to'yda edim.", 0.55)],
    [("Birinchi kuni: to'rt buyurtma.", 0.40), ("Ikkinchi kuni: yetti.", 0.40), ("Uchinchi kuni: besh.", 0.65)],
    [("Men hech kimga javob yozmadim.", 0.55), ("Savollarga tizim javob berdi. Pul ham o'tdi.", 0.60)],
    [("Qaytganimda peshtaxtada o'n oltita paket bor edi.", 0.90), ("Men hech narsa qilmadim.", 0.55),
     ("Shuning uchun ishladi.", 1.60)],
]


def token():
    return subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, shell=True).stdout.strip()


def tts(text, out):
    body = {"contents": [{"role": "user", "parts": [{"text": STYLE + text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}}
    url = (f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{REGION}"
           f"/publishers/google/models/{MODEL}:generateContent")
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + token()})
    with urllib.request.urlopen(req, timeout=240) as r:
        data = json.loads(r.read())
    pcm = base64.b64decode(data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)


def read(path):
    with wave.open(path, "rb") as w:
        return array.array("h", w.readframes(w.getnframes()))


def rms_frames(a, frame=0.02):
    n = int(SR * frame)
    out = []
    for i in range(0, len(a) - n, n):
        seg = a[i:i + n:3]
        out.append(math.sqrt(sum(v * v for v in seg) / max(1, len(seg))))
    return out, frame


def gaps(a, minimum=0.22):
    frames, step = rms_frames(a)
    res, run = [], 0
    for j, r in enumerate(frames):
        if r < 220:
            run += 1
        else:
            if run * step >= minimum:
                res.append((round((j - run) * step, 3), round(run * step, 3)))
            run = 0
    return res


def clean(a):
    thresh, margin = 300, int(0.04 * SR)
    lo = next((i for i, v in enumerate(a) if abs(v) > thresh), 0)
    burst = next((i for i in range(max(0, len(a) - int(1.0 * SR)), len(a)) if abs(a[i]) >= 30000), len(a))
    hi = next((i for i in range(burst - 1, -1, -1) if abs(a[i]) > thresh), burst - 1)
    a = a[max(0, lo - margin):hi + margin]
    n_in, n_out = int(0.02 * SR), int(0.06 * SR)
    for i in range(min(n_in, len(a))):
        a[i] = int(a[i] * i / n_in)
    for i in range(min(n_out, len(a))):
        a[-1 - i] = int(a[-1 - i] * i / n_out)
    return a


def compress_silence(a, max_gap=0.42, step=0.02):
    """Trim every silence longer than max_gap down to max_gap (keeps prosody, fixes dead air)."""
    fs = int(SR * step)
    frames, _ = rms_frames(a)
    quiet = [r < 220 for r in frames]
    keep, run_start = [], None
    i = 0
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]:
                j += 1
            excess = (j - i) * step - max_gap
            if excess > 0:
                half = int(excess / 2 / step)
                keep.append((i, i + half))
                keep.append((j - half, j))
            i = j
        else:
            i += 1
    if not keep:
        return a
    out = array.array("h")
    prev = 0
    for s, e in keep:
        out.extend(a[prev * fs:s * fs])
        prev = e
    out.extend(a[prev * fs:])
    return out


def bounds_of(a, texts):
    """Cut points: the silence nearest to each sentence's expected share of the take."""
    count = len(texts)
    total = len(a) / SR
    proportional = [total * i / count for i in range(count + 1)]
    found = [g for g in gaps(a) if 0.25 < g[0] < total - 0.3]
    if len(found) < count - 1:
        return proportional
    chars = sum(len(t) for t in texts)
    cuts, used, acc = [], set(), 0
    for t in texts[:-1]:
        acc += len(t)
        target = total * acc / chars
        best, best_i = None, -1
        for j, g in enumerate(found):
            if j in used:
                continue
            d = abs(g[0] + g[1] / 2 - target)
            if best is None or d < best:
                best, best_i = d, j
        if best_i < 0 or best > max(0.8, 0.3 * total / count):
            return proportional
        used.add(best_i)
        cuts.append(found[best_i][0] + found[best_i][1] / 2)
    return [0.0] + cuts + [total]


def main(force=False):
    os.makedirs(AUD, exist_ok=True)
    clips = []
    for gi, group in enumerate(GROUPS, 1):
        path = os.path.join(AUD, f"g{gi}.wav")
        if force or not os.path.exists(path):
            for attempt in range(4):
                try:
                    tts("\n\n".join(t for t, _ in group), path)
                    break
                except Exception as exc:
                    print("retry %s (%d): %s" % (os.path.basename(path), attempt + 1, exc), flush=True)
                    if attempt == 3:
                        raise
                    time.sleep(8 * (attempt + 1))
            print("gen", os.path.basename(path), flush=True)
        take = compress_silence(clean(read(path)))
        b = bounds_of(take, [t for t, _ in group])
        for li, (text, pause) in enumerate(group):
            clip = take[int(b[li] * SR):int(b[li + 1] * SR)]
            clips.append((text, clip, pause))
            print("g%d/%d  %.2f-%.2fs  %s" % (gi, li + 1, b[li], b[li + 1], text), flush=True)

    out = array.array("h", bytes(2 * int(LEAD * SR)))
    lines = []
    for text, clip, pause in clips:
        start = len(out) / SR
        out.extend(clip)
        end = len(out) / SR
        lines.append({"text": text, "who": "narrator", "a": round(start, 3), "b": round(end, 3)})
        out.extend(array.array("h", bytes(2 * int(pause * SR))))

    with wave.open(os.path.join(HERE, "narration.wav"), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR); f.writeframes(out.tobytes())
    data = {"duration": round(len(out) / SR, 3), "lines": lines}
    for name, payload in (("timeline.json", json.dumps(data, ensure_ascii=False, indent=1)),
                          ("timeline.js", "window.TL = " + json.dumps(data, ensure_ascii=False) + ";\n")):
        open(os.path.join(HERE, name), "w", encoding="utf-8").write(payload)
    print("duration", round(len(out) / SR, 2), "s")


if __name__ == "__main__":
    main(force="force" in sys.argv)
