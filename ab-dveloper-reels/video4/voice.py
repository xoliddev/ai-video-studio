"""Narration for video 4: `Bitta buyurtmaning sayohati`.

python voice.py gen    # create cached Gemini takes
python voice.py split  # remove the occasional spoken style prompt and assemble narration.wav
"""
import array
import json
import math
import os
import subprocess
import sys
import wave

import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
from gemini_tts import tts

FF = imageio_ffmpeg.get_ffmpeg_exe()
AUD = os.path.join(HERE, 'audio')
SR = 44100
VOICE = 'Puck'
STYLE = 'Speak in a warm, curious, cinematic Uzbek documentary voice. Sound relaxed and quietly amazed:\n\n'

GROUPS = [
    [
        'Bu — bitta buyurtma.',
        "Lekin u hech qachon yolg'iz yurmaydi.",
    ],
    [
        "U avval qahvaxonani uyg'otadi.",
        "Keyin pulni topadi.",
        "Rasmni emas — haqiqiy to'lovni.",
    ],
    [
        'Keyin eng yaqin kuryerni.',
        "Bularning hammasi bir-birini tanib turadi.",
    ],
    [
        "Shuning uchun yaxshi tizim shovqin qilmaydi.",
        "U shunchaki ishni o'z vaqtida bitiradi.",
    ],
]

# A group where Gemini does not read the English style line can be set here after
# we verify the take. The automatic silence detector handles the usual case.
START = {1: 0.0, 2: 7.7, 3: 0.0, 4: 0.0}
# Verified from a separate transcription pass. Explicit sentence boundaries are
# more reliable than deriving them from character count for these short takes.
MANUAL_BOUNDS = {
    1: [0.0, 1.80, 5.97],
    2: [7.70, 10.50, 12.70, 17.61],
    3: [0.0, 2.10, 6.49],
    4: [0.0, 3.20, 6.01],
}
DEFAULT_PAUSE, LEAD, TAIL = .34, .75, 2.5
os.makedirs(AUD, exist_ok=True)


def gen():
    for i, lines in enumerate(GROUPS, 1):
        path = os.path.join(AUD, f'g{i}.wav')
        if not os.path.exists(path):
            tts('\n\n'.join(lines), path + '.tmp', voice=VOICE, style=STYLE)
            os.replace(path + '.tmp', path)
        print('ok', path)


def read(path):
    raw = subprocess.run(
        [FF, '-loglevel', 'error', '-i', path, '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'],
        capture_output=True,
        check=True,
    ).stdout
    return array.array('h', raw)


def gaps_of(a, minimum=.14):
    frame = int(SR * .02)
    gaps, run = [], 0
    for j in range(len(a) // frame):
        seg = a[j * frame:(j + 1) * frame:3]
        rms = math.sqrt(sum(v * v for v in seg) / len(seg))
        if rms < 250:
            run += 1
        else:
            if run * .02 >= minimum:
                gaps.append(((j - run) * .02, run * .02))
            run = 0
    return gaps


def trim_and_fade(a):
    threshold = 300
    margin = int(.04 * SR)
    lo = next((i for i, value in enumerate(a) if abs(value) > threshold), 0)
    hi = next((i for i in range(len(a) - 1, -1, -1) if abs(a[i]) > threshold), len(a) - 1)
    a = a[max(0, lo - margin):hi + margin]
    for i in range(min(int(.02 * SR), len(a))):
        a[i] = int(a[i] * i / int(.02 * SR))
    for i in range(min(int(.06 * SR), len(a))):
        a[-1 - i] = int(a[-1 - i] * i / int(.06 * SR))
    return a


def end_of(a):
    # Gemini often appends a full-scale artifact right at the end.
    burst = next((i for i in range(max(0, len(a) - SR), len(a)) if abs(a[i]) >= 30000), len(a))
    return burst / SR - .03


def split():
    clips = []
    for gi, lines in enumerate(GROUPS, 1):
        take = read(os.path.join(AUD, f'g{gi}.wav'))
        end = end_of(take)
        gaps = gaps_of(take)
        style_gap = [g for g in gaps if 1.8 <= g[0] <= 4.2 and g[1] >= .4]
        start = START.get(gi, style_gap[0][0] + style_gap[0][1] - .04 if style_gap else 0)
        if gi in MANUAL_BOUNDS:
            bounds = MANUAL_BOUNDS[gi]
        else:
            inner = [g for g in gaps if start + .45 < g[0] < end - .5]
            total_chars = sum(len(line) for line in lines)
            bounds, chars = [start], 0
            for line in lines[:-1]:
                chars += len(line)
                target = start + (end - start) * chars / total_chars
                chosen = min(inner, key=lambda g: abs(g[0] + g[1] / 2 - target) - g[1] * 1.5)
                inner.remove(chosen)
                bounds.append(chosen[0] + chosen[1] / 2)
            bounds.append(end)
        for li, line in enumerate(lines):
            clip = trim_and_fade(take[int(bounds[li] * SR):int(bounds[li + 1] * SR)])
            clips.append((line, clip))
            print(f'g{gi} / {li + 1}: {bounds[li]:.2f}–{bounds[li + 1]:.2f}s  {line}')

    out = array.array('h', bytes(2 * int(LEAD * SR)))
    lines = []
    for i, (text, clip) in enumerate(clips):
        if i:
            out.extend(array.array('h', bytes(2 * int(DEFAULT_PAUSE * SR))))
        a = len(out) / SR
        out.extend(clip)
        lines.append({'text': text, 'who': 'narrator', 'a': round(a, 3), 'b': round(len(out) / SR, 3)})
    out.extend(array.array('h', bytes(2 * int(TAIL * SR))))
    with wave.open(os.path.join(HERE, 'narration.wav'), 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(out.tobytes())
    data = {'duration': round(len(out) / SR, 3), 'lines': lines}
    with open(os.path.join(HERE, 'timeline.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    with open(os.path.join(HERE, 'timeline.js'), 'w', encoding='utf-8') as f:
        f.write('window.TL = ' + json.dumps(data, ensure_ascii=False) + ';\n')
    print('narration', round(len(out) / SR, 2), 's')


if __name__ == '__main__':
    {'gen': gen, 'split': split}[sys.argv[1] if len(sys.argv) > 1 else 'gen']()
