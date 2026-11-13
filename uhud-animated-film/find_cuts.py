"""Gemini sometimes read the style instruction aloud (~14-16 s) before the line.
Find, per clip, the pause that follows the instruction and store the cut point in audio_uz/cuts.json."""
import json, os, wave, array, math, hashlib

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = json.load(open(os.path.join(ROOT, 'script_uz.json'), encoding='utf-8'))


def path(t):
    return os.path.join(ROOT, 'audio_uz', hashlib.md5(f"{spec['voice']}|{t}".encode()).hexdigest()[:16] + '.wav')


def analyse(p):
    w = wave.open(p); sr = w.getframerate(); a = array.array('h', w.readframes(w.getnframes()))
    f = int(sr * .02)
    rms = [math.sqrt(sum(x * x for x in a[i:i + f:3]) / (f / 3)) for i in range(0, len(a) - f, f)]
    gaps, run = [], 0
    for i, r in enumerate(rms):
        if r < 250: run += 1
        else:
            if run >= 10: gaps.append(((i - run) * .02, run * .02))
            run = 0
    return len(a) / sr, gaps


# checked by transcribing the clip openings; the automatic pick cut off the first sentence here
OVERRIDE = {"Qochayotgan qurayshliklar ortg": 14.6}
cuts = {}
for sc in spec['scenes']:
    for line in sc['lines']:
        dur, gaps = analyse(path(line))
        expected = len(line) / 12.5 + 1.0
        cut = 0.0
        if dur > expected + 7:
            cand = [g for g in gaps if 13.0 <= g[0] <= 18.2 and g[0] + g[1] < dur - .8]
            if cand:
                # long pause, and what's left should be about as long as the line needs
                g = max(cand, key=lambda g: g[1] - .25 * abs(dur - g[0] - g[1] - expected))
                cut = round(g[0] + g[1] - .08, 2)
        cut = OVERRIDE.get(line[:30], cut)
        cuts[line] = cut
        print(f'{dur:5.1f}s  cut {cut:5.2f}  rest {dur - cut:5.1f}s  exp {expected:4.1f}  {line[:50]}')
json.dump(cuts, open(os.path.join(ROOT, 'audio_uz', 'cuts.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
