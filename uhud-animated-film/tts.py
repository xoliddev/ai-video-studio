"""Generate narration with edge-tts, then build timeline.js, narration.wav, subtitles.srt and script.md.

English is read by the narrator voice; {key} placeholders in a line's "say" text are spliced in from a
native Arabic voice (ARABIC below). Arabic terms are spelled in pausal form so no case endings are added.
"""
import asyncio, json, os, re, subprocess, wave, array, hashlib, math
import edge_tts, imageio_ffmpeg

ROOT = os.path.dirname(os.path.abspath(__file__))
FF = imageio_ffmpeg.get_ffmpeg_exe()
SR = 44100
LEAD, TAIL, GAP, SEG_GAP = 1.2, 1.2, 0.45, 0.10
AR_VOICE, AR_RATE = 'ar-SA-HamedNeural', '-8%'
ARABIC = {
    'saw': 'صَلَّى اللّٰهُ عَلَيْهِ وَسَلَّمْ',
    'muhammad_saw': 'مُحَمَّدْ صَلَّى اللّٰهُ عَلَيْهِ وَسَلَّمْ',
    'hamzah': 'حَمْزَهْ بِنْ عَبْدِ الْمُطَّلِبْ',
    'hamza': 'حَمْزَهْ',
    'khalid': 'خَالِدْ بِنْ وَلِيدْ',
    'abusufyan': 'أَبُو سُفْيَانْ',
    'ibnjubayr': 'عَبْدُ اللهِ بِنْ جُبَيْرْ',
    'ibnubayy': 'عَبْدُ اللهِ بِنْ أُبَيّْ',
    'wahshi': 'وَحْشِيّْ',
    'anas': 'أَنَسْ بِنْ نَضْرْ',
    'nusaybah': 'نُسَيْبَهْ بِنْتْ كَعْبْ',
    'ulhubal': 'اُعْلُ هُبَلْ',
    'uzza': 'الْعُزَّى',
    'uhud': 'أُحُدْ',
    'badr': 'بَدْرْ',
    'makkah': 'مَكَّهْ',
    'madinah': 'الْمَدِينَهْ',
    'quraysh': 'قُرَيْشْ',
    'shawwal': 'شَوَّالْ',
}

spec = json.load(open(os.path.join(ROOT, 'script.json'), encoding='utf-8'))
CACHE = os.path.join(ROOT, 'audio')
os.makedirs(CACHE, exist_ok=True)


def norm(line):
    return line if isinstance(line, dict) else {'text': line, 'say': line}


def segments(say):
    """'In {madinah}, the ...' -> [('en','In'), ('ar', '...'), ('en', ', the ...')]"""
    out = []
    for i, part in enumerate(re.split(r'\{(\w+)\}', say)):
        if i % 2:
            out.append((AR_VOICE, ARABIC[part], AR_RATE))
        elif re.search(r'\w', part):
            out.append((spec['voice'], part.strip(' ,.!'), spec['rate']))
    return out


def cache_path(voice, text, rate):
    return os.path.join(CACHE, hashlib.md5(f'{voice}|{rate}|{text}'.encode()).hexdigest()[:16] + '.mp3')


async def synth(voice, text, rate, sem):
    p = cache_path(voice, text, rate)
    async with sem:
        for attempt in range(4):
            if os.path.exists(p):
                return
            try:
                await edge_tts.Communicate(text, voice, rate=rate).save(p)
            except Exception:
                if os.path.exists(p):
                    os.remove(p)
                if attempt == 3:
                    raise
                await asyncio.sleep(2)


def load(voice, text, rate):
    mp3 = cache_path(voice, text, rate)
    wav = mp3[:-4] + '.wav'
    if not os.path.exists(wav):
        subprocess.run([FF, '-y', '-loglevel', 'error', '-i', mp3, '-ac', '1', '-ar', str(SR), wav], check=True)
    with wave.open(wav) as w:
        a = array.array('h', w.readframes(w.getnframes()))
    # trim edge silence, keep a short margin
    th, m = 400, int(.04 * SR)
    lo = next((i for i, v in enumerate(a) if abs(v) > th), 0)
    hi = next((i for i in range(len(a) - 1, -1, -1) if abs(a[i]) > th), len(a) - 1)
    a = a[max(0, lo - m): min(len(a), hi + m)]
    # match loudness between the two voices
    rms = math.sqrt(sum(v * v for v in a[::4]) / max(1, len(a[::4])))
    g = 3200 / rms if rms > 0 else 1
    return array.array('h', (max(-32767, min(32767, int(v * g))) for v in a))


def silence(sec):
    return array.array('h', bytes(2 * int(round(sec * SR))))


async def main():
    jobs = {cache_path(*s): s for sc in spec['scenes'] for l in sc['lines'] for s in segments(norm(l)['say'])}
    sem = asyncio.Semaphore(6)
    await asyncio.gather(*(synth(*s, sem) for s in jobs.values()))

    out = array.array('h')
    timeline, srt = [], []
    t = lambda: len(out) / SR
    for sc in spec['scenes']:
        start = t()
        out.extend(silence(sc.get('lead', LEAD)))
        lines = []
        for li, line in enumerate(sc['lines']):
            l = norm(line)
            a = t()
            for si, s in enumerate(segments(l['say'])):
                if si:
                    out.extend(silence(SEG_GAP))
                out.extend(load(*s))
            lines.append({'text': l['text'], 'a': round(a, 3), 'b': round(t(), 3)})
            srt.append((a, t(), l['text']))
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
    with open(os.path.join(ROOT, 'subtitles.srt'), 'w', encoding='utf-8') as f:
        for i, (a, b, txt) in enumerate(srt, 1):
            f.write(f'{i}\n{ts(a)} --> {ts(b)}\n{txt}\n\n')

    with open(os.path.join(ROOT, 'script.md'), 'w', encoding='utf-8') as f:
        f.write(f"# {spec['title']}\n\nNarration script (English). Total length: {int(total // 60)}:{int(total % 60):02d}\n\n")
        for sc in timeline:
            f.write(f"## {sc['id'].title()}  ({int(sc['a'] // 60)}:{int(sc['a'] % 60):02d})\n\n")
            for l in sc['lines']:
                f.write(f"{l['text']}\n\n")
    print('duration', round(total, 2), 'sec;', len(srt), 'lines')

asyncio.run(main())
