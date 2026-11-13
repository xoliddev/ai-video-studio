"""Uzbek narration with Gemini TTS (Iapetus) -> narration.wav, timeline.js, subtitles.srt, script.md."""
import json, os, re, subprocess, wave, array, hashlib, math
from concurrent.futures import ThreadPoolExecutor
import imageio_ffmpeg
from gemini_tts import tts

ROOT = os.path.dirname(os.path.abspath(__file__))
FF = imageio_ffmpeg.get_ffmpeg_exe()
SR = 44100
LEAD, TAIL, GAP = 1.2, 1.2, 0.5
spec = json.load(open(os.path.join(ROOT, 'script_uz.json'), encoding='utf-8'))
CACHE = os.path.join(ROOT, 'audio_uz')
os.makedirs(CACHE, exist_ok=True)
_cuts = os.path.join(CACHE, 'cuts.json')
CUTS = json.load(open(_cuts, encoding='utf-8')) if os.path.exists(_cuts) else {}


def subtitle(say):
    """Spoken salawat is shortened to (s.a.v.) on screen."""
    s = re.sub(r' sollallohu alayhi vasallam(ning|ni|ga|dan)?', lambda m: ' (s.a.v.)' + (m.group(1) or ''), say)
    return s


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
    # drop the style instruction Gemini sometimes read aloud (cut points from find_cuts.py)
    a = a[int(CUTS.get(text, 0) * SR):]
    # every Gemini clip ends with a ~0.13 s full-scale noise burst; cut it off before it starts
    tail = int(.5 * SR)
    burst = next((i for i in range(len(a) - tail, len(a)) if abs(a[i]) >= 30000), None)
    if burst is not None:
        a = a[:max(0, burst - int(.03 * SR))]
    th, m = 300, int(.05 * SR)
    lo = next((i for i, v in enumerate(a) if abs(v) > th), 0)
    hi = next((i for i in range(len(a) - 1, -1, -1) if abs(a[i]) > th), len(a) - 1)
    a = a[max(0, lo - m): min(len(a), hi + m)]
    # short fades so the hard cuts don't click against the silence between lines
    fi, fo = int(.025 * SR), int(.06 * SR)
    for i in range(min(fi, len(a))):
        a[i] = int(a[i] * i / fi)
    for i in range(min(fo, len(a))):
        a[-1 - i] = int(a[-1 - i] * i / fo)
    return a


def silence(sec):
    return array.array('h', bytes(2 * int(round(sec * SR))))


def main():
    texts = [l for sc in spec['scenes'] for l in sc['lines']]
    with ThreadPoolExecutor(4) as ex:
        for i, _ in enumerate(ex.map(synth, texts), 1):
            print(f'tts {i}/{len(texts)}', flush=True)

    out = array.array('h')
    timeline, srt = [], []
    t = lambda: len(out) / SR
    for sc in spec['scenes']:
        start = t()
        out.extend(silence(sc.get('lead', LEAD)))
        lines = []
        for li, say in enumerate(sc['lines']):
            a = t()
            out.extend(load(say))
            lines.append({'text': subtitle(say), 'a': round(a, 3), 'b': round(t(), 3)})
            srt.append((a, t(), subtitle(say)))
            if li < len(sc['lines']) - 1:
                out.extend(silence(GAP))
        out.extend(silence(sc.get('tail', TAIL)))
        timeline.append({'id': sc['id'], 'caption': sc.get('caption', ''), 'a': round(start, 3), 'b': round(t(), 3), 'lines': lines})
    total = t()

    with wave.open(os.path.join(ROOT, 'narration.wav'), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes())
    with open(os.path.join(ROOT, 'timeline.js'), 'w', encoding='utf-8') as f:
        f.write('window.TL = ' + json.dumps({'duration': round(total, 3), 'scenes': timeline}, ensure_ascii=False, indent=1) + ';\n')

    def ts(x):
        ms = int(round(x * 1000)); return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'
    with open(os.path.join(ROOT, 'subtitles_uz.srt'), 'w', encoding='utf-8') as f:
        for i, (a, b, txt) in enumerate(srt, 1):
            f.write(f'{i}\n{ts(a)} --> {ts(b)}\n{txt}\n\n')
    with open(os.path.join(ROOT, 'script_uz.md'), 'w', encoding='utf-8') as f:
        f.write(f"# {spec['title']}\n\nDiktor matni (o'zbekcha). Umumiy davomiylik: {int(total // 60)}:{int(total % 60):02d}\n\n")
        for sc in spec['scenes']:
            f.write(f"## {sc['id']}\n\n" + ''.join(f'{l}\n\n' for l in sc['lines']))
    print('duration', round(total, 2))


main()
