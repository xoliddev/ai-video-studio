"""Voice the reel in 4 Gemini requests (saves quota), then split each take into its lines.

python voice.py gen [group...]   -> audio/g1.wav ... (cached)
python voice.py split            -> audio/lines.json (line start/end inside each take), narration.wav, timeline.json
"""
import json, os, sys, wave, array, math, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
from gemini_tts import tts
import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
FF = imageio_ffmpeg.get_ffmpeg_exe()
VOICE = 'Puck'
STYLE = 'Say in a cheerful, energetic, upbeat voice:\n\n'
GROUPS = [
    ["Mijoz chek tashladi: «To'ladim, jo'natib yuboring!»",
     "Summa to'g'ri, sana to'g'ri, hatto belgisi ham bor...",
     "...faqat hisobingizga bir so'm ham tushmagan."],
    ["Soxta chekni ko'z bilan ajratish qiyin.",
     "Keling, bu ishni botga topshiramiz.",
     "Mijoz to'g'ridan-to'g'ri botning ichida to'laydi."],
    ["Bot pulni rasmdan emas, to'lov tizimining o'zidan tekshiradi.",
     "Kimdir baribir rasm tashlasa — bot muloyimgina to'lov tugmasini yuboradi."],
    ["Sizga esa faqat puli tushgan buyurtma keladi. Qolgani — kutish ro'yxatida.",
     "Bu ham loyihalarimizdan biri. Keyingisida — kechasi ham sotadigan AI!"],
]
AUD = os.path.join(HERE, 'audio')
os.makedirs(AUD, exist_ok=True)


def gen(which):
    for gi in which:
        p = os.path.join(AUD, f'g{gi + 1}.wav')
        if os.path.exists(p):
            print('cached', p); continue
        tts('\n\n'.join(GROUPS[gi]), p + '.tmp', voice=VOICE, style=STYLE)
        os.replace(p + '.tmp', p)
        print('ok', p)


SR = 44100
LEAD, TAIL = 0.45, 3.2
# pause before line i (0-based, across all groups); the turn and the outro get room to breathe
PAUSE = {4: 1.0, 5: 0.35, 9: 0.6}
DEFAULT_PAUSE = 0.28
# takes where Gemini did not read the style line aloud (checked by transcription)
START = {4: 0.0}


def read(p):
    out = subprocess.run([FF, '-loglevel', 'error', '-i', p, '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True, check=True).stdout
    return array.array('h', out)


def gaps_of(a, min_len=.14):
    f = int(SR * .02); n = len(a) // f
    gaps, run = [], 0
    for j in range(n):
        seg = a[j * f:(j + 1) * f:3]
        r = math.sqrt(sum(v * v for v in seg) / len(seg))
        if r < 250: run += 1
        else:
            if run * .02 >= min_len: gaps.append(((j - run) * .02, run * .02))
            run = 0
    return gaps


def split():
    lines, clips = [], []
    for gi, texts in enumerate(GROUPS):
        a = read(os.path.join(AUD, f'g{gi + 1}.wav'))
        dur = len(a) / SR
        # the take ends with a full-scale noise burst
        burst = next((i for i in range(max(0, len(a) - SR), len(a)) if abs(a[i]) >= 30000), len(a))
        end = burst / SR - .03
        g = gaps_of(a)
        # Gemini speaks the style line first; content starts after the long pause that follows it
        lead = [x for x in g if 1.8 <= x[0] <= 4.2 and x[1] >= .4]
        start = lead[0][0] + lead[0][1] - .04 if lead else 0
        start = START.get(gi + 1, start)
        inner = [x for x in g if start + .5 < x[0] < end - .5]
        total = sum(len(t) for t in texts)
        bounds, acc = [start], 0
        for t in texts[:-1]:
            acc += len(t)
            want = start + (end - start) * acc / total
            best = min(inner, key=lambda x: abs(x[0] + x[1] / 2 - want) - x[1] * 1.5)
            inner.remove(best)
            bounds.append(best[0] + best[1] / 2)
        bounds.append(end)
        for li, t in enumerate(texts):
            s = a[int(bounds[li] * SR):int(bounds[li + 1] * SR)]
            th, m = 300, int(.04 * SR)
            lo = next((i for i, v in enumerate(s) if abs(v) > th), 0)
            hi = next((i for i in range(len(s) - 1, -1, -1) if abs(s[i]) > th), len(s) - 1)
            s = s[max(0, lo - m):hi + m]
            fi, fo = int(.02 * SR), int(.06 * SR)
            for i in range(min(fi, len(s))): s[i] = int(s[i] * i / fi)
            for i in range(min(fo, len(s))): s[-1 - i] = int(s[-1 - i] * i / fo)
            clips.append(s); lines.append(t)
            print(f'g{gi + 1} line {li + 1}: {bounds[li]:.2f}-{bounds[li + 1]:.2f}s ({len(s) / SR:.2f}s)  {t[:45]}')
    out = array.array('h', bytes(2 * int(LEAD * SR)))
    tl = []
    for i, (t, s) in enumerate(zip(lines, clips)):
        if i:
            out.extend(array.array('h', bytes(2 * int(PAUSE.get(i, DEFAULT_PAUSE) * SR))))
        a0 = len(out) / SR
        out.extend(s)
        tl.append({'text': t, 'a': round(a0, 3), 'b': round(len(out) / SR, 3)})
    out.extend(array.array('h', bytes(2 * int(TAIL * SR))))
    with wave.open(os.path.join(HERE, 'narration.wav'), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes())
    data = {'duration': round(len(out) / SR, 3), 'lines': tl}
    json.dump(data, open(os.path.join(HERE, 'timeline.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(HERE, 'timeline.js'), 'w', encoding='utf-8').write('window.TL = ' + json.dumps(data, ensure_ascii=False) + ';\n')
    print('narration', round(len(out) / SR, 2), 's')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'gen'
    if cmd == 'gen':
        gen([int(x) - 1 for x in sys.argv[2:]] or range(len(GROUPS)))
    elif cmd == 'split':
        split()
