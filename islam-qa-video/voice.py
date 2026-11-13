"""Uzbek voice-over with gemini-3.8-flash-tts -> narration.wav + timeline.js.

One TTS request per segment (question + answer together) to stay inside the free daily quota.
The question/answer boundary is found as the longest pause in the clip.
"""
import array, hashlib, json, os, subprocess, sys, wave
import imageio_ffmpeg
from gemini_tts import tts

ROOT = os.path.dirname(os.path.abspath(__file__))
FF = imageio_ffmpeg.get_ffmpeg_exe()
SR = 44100
spec = json.load(open(os.path.join(ROOT, 'script.json'), encoding='utf-8'))
CACHE = os.path.join(ROOT, 'audio')
os.makedirs(CACHE, exist_ok=True)


def text_of(seg):
    return seg['say'] if 'say' in seg else seg['ask'] + '\n\n' + seg['answer']


def path(text):
    return os.path.join(CACHE, hashlib.md5(f"{spec['voice']}|{text}".encode()).hexdigest()[:16] + '.wav')


def synth(text):
    p = path(text)
    if not os.path.exists(p):
        tts(text, p + '.tmp', voice=spec['voice'])
        os.replace(p + '.tmp', p)
    return p


def load(text):
    src = path(text)
    wav = src[:-4] + '_44k.wav'
    if not os.path.exists(wav):
        subprocess.run([FF, '-y', '-loglevel', 'error', '-i', src, '-ac', '1', '-ar', str(SR), wav], check=True)
    with wave.open(wav) as w:
        a = array.array('h', w.readframes(w.getnframes()))
    # every Gemini clip ends with a short full-scale noise burst: cut it off
    tail = int(.5 * SR)
    burst = next((i for i in range(max(0, len(a) - tail), len(a)) if abs(a[i]) >= 30000), None)
    if burst is not None:
        a = a[:max(0, burst - int(.03 * SR))]
    th, m = 300, int(.05 * SR)
    lo = next((i for i, v in enumerate(a) if abs(v) > th), 0)
    hi = next((i for i in range(len(a) - 1, -1, -1) if abs(a[i]) > th), len(a) - 1)
    a = a[max(0, lo - m): min(len(a), hi + m)]
    fi, fo = int(.025 * SR), int(.06 * SR)
    for i in range(min(fi, len(a))):
        a[i] = int(a[i] * i / fi)
    for i in range(min(fo, len(a))):
        a[-1 - i] = int(a[-1 - i] * i / fo)
    return a


def pauses(a, win=.02, th=350, min_len=.18):
    """[(start_s, end_s)] of quiet stretches."""
    n = int(win * SR)
    out, start = [], None
    for k in range(0, len(a) - n, n):
        loud = max(abs(v) for v in a[k:k + n]) > th
        t = k / SR
        if not loud and start is None:
            start = t
        elif loud and start is not None:
            if t - start >= min_len:
                out.append((start, t))
            start = None
    return out


def silence(sec):
    return array.array('h', bytes(2 * int(round(sec * SR))))


def main():
    segs = spec['segments']
    for i, s in enumerate(segs, 1):
        synth(text_of(s))
        print(f'tts {i}/{len(segs)}', flush=True)
    if '--tts-only' in sys.argv:
        return

    out = array.array('h')
    t = lambda: len(out) / SR
    tl = []
    out.extend(silence(0.8))
    for s in segs:
        a = load(text_of(s))
        start = t()
        entry = {'id': s['id'], 'a': round(start, 3)}
        if 'ask' in s:
            # question ends at the longest pause near where its share of the text predicts
            dur = len(a) / SR
            exp = dur * len(s['ask']) / (len(s['ask']) + len(s['answer']))
            ps = [p for p in pauses(a) if exp * .7 < p[0] < exp * 1.3]
            q_end = max(ps, key=lambda p: p[1] - p[0]) if ps else (dur * .3, dur * .3)
            cut = int(q_end[0] * SR) + int(.05 * SR)
            resume = int(q_end[1] * SR) - int(.05 * SR)
            out.extend(a[:cut])
            entry['q_end'] = round(t(), 3)
            out.extend(silence(0.9))           # let the question sink in
            entry['ans'] = round(t(), 3)
            out.extend(a[resume:])
            entry['ans_end'] = round(t(), 3)
            print(s['id'], 'question pause', [round(x, 2) for x in q_end], 'clip', round(dur, 2))
        else:
            out.extend(a)
        out.extend(silence(1.0 if s['id'] != 'outro' else 1.8))
        entry['b'] = round(t(), 3)
        tl.append(entry)
    total = t()
    with wave.open(os.path.join(ROOT, 'narration.wav'), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes())
    data = {'duration': round(total, 3), 'segments': tl, 'script': segs}
    open(os.path.join(ROOT, 'timeline.js'), 'w', encoding='utf-8').write(
        'window.TL = ' + json.dumps(data, ensure_ascii=False, indent=1) + ';\n')
    print('duration', round(total, 2))


main()
