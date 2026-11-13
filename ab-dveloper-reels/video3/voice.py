"""Voices for episode 3: narrator (4 takes, cheerful style), the customer's voice message and the AI seller's reply.

python voice.py gen     -> audio/g1..g4.wav, audio/cust.wav, audio/ai.wav (cached)
python voice.py split   -> narration.wav, timeline.json, timeline.js
"""
import json, os, sys, wave, array, math, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
from gemini_tts import tts
import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
FF = imageio_ffmpeg.get_ffmpeg_exe()
AUD = os.path.join(HERE, 'audio')
SR = 44100
NARRATOR, CUSTOMER, AI = 'Puck', 'Leda', 'Achird'
STYLE = 'Say in a cheerful, energetic, upbeat voice:\n\n'

# each line: (text on screen, text spoken); numbers and "AI" are spelled out for the voice
N = lambda text, say=None: (text, say or text)
GROUPS = [
    [N("Soat 23:47. LIBOS yopiq, sotuvchi allaqachon uxlayapti.", "Soat yigirma uch qirq yetti. LIBOS yopiq, sotuvchi allaqachon uxlayapti."),
     N("Shu payt mijozdan ovozli xabar keladi.")],
    [N("Javobni esa AI beradi. Bir necha soniyada, o'zbek tilida.", "Javobni esa sun'iy intellekt beradi. Bir necha soniyada, o'zbek tilida."),
     N("U katalogni biladi, ombordagi qoldiqni ko'radi va mijozni to'g'ri mahsulotga olib boradi.")],
    [N("Mijoz botning ichida to'laydi. Chek emas, haqiqiy to'lov."),
     N("Ertalab sotuvchi uyg'onadi: tunda uchta buyurtma, hammasi to'langan.")],
    [N("Do'kon Telegram ichida. To'lovni bot tekshiradi. Savdoni esa AI qiladi.", "Do'kon Telegram ichida. To'lovni bot tekshiradi. Savdoni esa sun'iy intellekt qiladi."),
     N("LIBOS seriyasi shu bilan yakunlandi. Keyingi loyiha qaysi soha uchun bo'lsin? Izohda yozing!")],
]
EXTRA = {
    'cust': (CUSTOMER, N("Assalomu alaykum! Kecha ko'rgan zaytun ko'ylak hali bormi? Menga M razmer kerak edi.")),
    'ai': (AI, N("Va alaykum assalom! Ha, zaytun rangli zig'ir ko'ylak M razmerda bor, narxi 189 000 so'm. Hoziroq buyurtma qilishingiz mumkin!",
                 "Va alaykum assalom! Ha, zaytun rangli zig'ir ko'ylak M razmerda bor, narxi — yuz sakson to'qqiz ming so'm. Hoziroq buyurtma qilishingiz mumkin!")),
}
# playback order: narrator lines by (group, line), the two voice messages by key
ORDER = [(0, 0), (0, 1), 'cust', (1, 0), 'ai', (1, 1), (2, 0), (2, 1), (3, 0), (3, 1)]
PAUSE_BEFORE = {'cust': .5, (1, 0): .45, 'ai': .9, (1, 1): .5, (3, 0): .55, (3, 1): .6}
DEFAULT_PAUSE, LEAD, TAIL = .3, .9, 3.2
START = {2: 0.0}      # takes where the style line was not spoken (checked by transcription)
os.makedirs(AUD, exist_ok=True)


def gen():
    for gi, lines in enumerate(GROUPS):
        p = os.path.join(AUD, f'g{gi + 1}.wav')
        if not os.path.exists(p):
            tts('\n\n'.join(s for _, s in lines), p + '.tmp', voice=NARRATOR, style=STYLE); os.replace(p + '.tmp', p)
        print('ok', p)
    for k, (voice, (_, say)) in EXTRA.items():
        p = os.path.join(AUD, f'{k}.wav')
        if not os.path.exists(p):
            tts(say, p + '.tmp', voice=voice, style=''); os.replace(p + '.tmp', p)
        print('ok', p)


def read(p):
    return array.array('h', subprocess.run([FF, '-loglevel', 'error', '-i', p, '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True, check=True).stdout)


def gaps_of(a, min_len=.14):
    f = int(SR * .02); gaps, run = [], 0
    for j in range(len(a) // f):
        seg = a[j * f:(j + 1) * f:3]
        if math.sqrt(sum(v * v for v in seg) / len(seg)) < 250: run += 1
        else:
            if run * .02 >= min_len: gaps.append(((j - run) * .02, run * .02))
            run = 0
    return gaps


def tidy(s):
    """trim silence and fade the edges so cuts don't click"""
    th, m = 300, int(.04 * SR)
    lo = next((i for i, v in enumerate(s) if abs(v) > th), 0)
    hi = next((i for i in range(len(s) - 1, -1, -1) if abs(s[i]) > th), len(s) - 1)
    s = s[max(0, lo - m):hi + m]
    fi, fo = int(.02 * SR), int(.06 * SR)
    for i in range(min(fi, len(s))): s[i] = int(s[i] * i / fi)
    for i in range(min(fo, len(s))): s[-1 - i] = int(s[-1 - i] * i / fo)
    return s


def end_of(a):
    # every Gemini take ends with a full-scale noise burst
    burst = next((i for i in range(max(0, len(a) - SR), len(a)) if abs(a[i]) >= 30000), len(a))
    return burst / SR - .03


def split():
    clips = {}
    for gi, lines in enumerate(GROUPS):
        a = read(os.path.join(AUD, f'g{gi + 1}.wav')); end = end_of(a); g = gaps_of(a)
        lead = [x for x in g if 1.8 <= x[0] <= 4.2 and x[1] >= .4]
        start = START.get(gi + 1, lead[0][0] + lead[0][1] - .04 if lead else 0)
        inner = [x for x in g if start + .5 < x[0] < end - .5]
        total = sum(len(s) for _, s in lines); bounds, acc = [start], 0
        for _, s in lines[:-1]:
            acc += len(s); want = start + (end - start) * acc / total
            best = min(inner, key=lambda x: abs(x[0] + x[1] / 2 - want) - x[1] * 1.5); inner.remove(best)
            bounds.append(best[0] + best[1] / 2)
        bounds.append(end)
        for li in range(len(lines)):
            clips[(gi, li)] = tidy(a[int(bounds[li] * SR):int(bounds[li + 1] * SR)])
            print(f'g{gi + 1} line {li + 1}: {bounds[li]:.2f}-{bounds[li + 1]:.2f}s  {lines[li][0][:50]}')
    for k in EXTRA:
        a = read(os.path.join(AUD, f'{k}.wav'))
        clips[k] = tidy(a[:int(end_of(a) * SR)])
    out = array.array('h', bytes(2 * int(LEAD * SR))); tl = []
    for i, key in enumerate(ORDER):
        if i: out.extend(array.array('h', bytes(2 * int(PAUSE_BEFORE.get(key, DEFAULT_PAUSE) * SR))))
        a0 = len(out) / SR; out.extend(clips[key])
        text = EXTRA[key][1][0] if isinstance(key, str) else GROUPS[key[0]][key[1]][0]
        tl.append({'text': text, 'who': key if isinstance(key, str) else 'narrator', 'a': round(a0, 3), 'b': round(len(out) / SR, 3)})
    out.extend(array.array('h', bytes(2 * int(TAIL * SR))))
    with wave.open(os.path.join(HERE, 'narration.wav'), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes())
    data = {'duration': round(len(out) / SR, 3), 'lines': tl}
    json.dump(data, open(os.path.join(HERE, 'timeline.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(HERE, 'timeline.js'), 'w', encoding='utf-8').write('window.TL = ' + json.dumps(data, ensure_ascii=False) + ';\n')
    for l in tl: print(f"{l['a']:6.2f}-{l['b']:6.2f} {l['who']:8s} {l['text'][:60]}")
    print('narration', round(len(out) / SR, 2), 's')


if __name__ == '__main__':
    {'gen': gen, 'split': split}[sys.argv[1] if len(sys.argv) > 1 else 'gen']()
