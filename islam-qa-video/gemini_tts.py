"""Small Gemini TTS helper: text -> 24 kHz mono 16-bit WAV.

Keys come from GEMINI_API_KEYS=k1,k2,... (environment or .env). When a key hits its daily quota the next one is used;
model, voice and style stay identical so every clip sounds the same.
"""
import base64, json, os, threading, time, urllib.request, urllib.error, wave

ROOT = os.path.dirname(os.path.abspath(__file__))
MODEL = 'gemini-3.8-flash-tts'
# Note: Gemini may read this instruction aloud; find_cuts.py trims it from the clips.
STYLE = ''  # no prefix: Gemini reads style instructions aloud


def _load_keys():
    """GEMINI_API_KEYS (comma-separated) or GEMINI_API_KEY: taken from the environment first,
    otherwise from the nearest .env file found by walking up from this folder."""
    def split(v):
        return [x.strip() for x in v.split(',') if x.strip()]
    for name in ('GEMINI_API_KEYS', 'GEMINI_API_KEY'):
        if os.environ.get(name, '').strip():
            return split(os.environ[name])
    d = ROOT
    while True:
        p = os.path.join(d, '.env')
        if os.path.exists(p):
            for line in open(p, encoding='utf-8'):
                k, _, v = line.strip().partition('=')
                if k in ('GEMINI_API_KEYS', 'GEMINI_API_KEY') and v.strip():
                    return split(v)
        if os.path.dirname(d) == d:
            break
        d = os.path.dirname(d)
    raise RuntimeError('set GEMINI_API_KEYS (or GEMINI_API_KEY) in the environment or in a .env file')


KEYS = _load_keys()
_exhausted = set()
_lock = threading.Lock()


def api_key():
    with _lock:
        for k in KEYS:
            if k not in _exhausted:
                return k
    raise RuntimeError('all Gemini API keys have used up their daily quota')


def _mark_exhausted(key):
    with _lock:
        if key not in _exhausted:
            _exhausted.add(key)
            print(f'key #{KEYS.index(key) + 1} reached its daily quota, switching ({len(KEYS) - len(_exhausted)} left)', flush=True)


def tts(text, out_wav, voice='Charon', style=STYLE, model=MODEL):
    body = {
        'contents': [{'parts': [{'text': style + text}]}],
        'generationConfig': {'responseModalities': ['AUDIO'],
                             'speechConfig': {'voiceConfig': {'prebuiltVoiceConfig': {'voiceName': voice}}}},
    }
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    attempt = 0
    while True:
        key = api_key()
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST',
                                     headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
        try:
            data = json.load(urllib.request.urlopen(req, timeout=180))
            pcm = base64.b64decode(data['candidates'][0]['content']['parts'][0]['inlineData']['data'])
            with wave.open(out_wav, 'wb') as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
            return out_wav
        except urllib.error.HTTPError as e:
            msg = e.read().decode('utf-8', 'replace')
            if e.code == 429 and 'PerDay' in msg:
                _mark_exhausted(key)
                continue
            attempt += 1
            if e.code in (429, 500, 503) and attempt < 6:
                time.sleep(10 * attempt); continue
            raise RuntimeError(f'Gemini TTS {e.code}: {msg[:300]}')
        except (urllib.error.URLError, TimeoutError, ConnectionError, KeyError):
            attempt += 1
            if attempt >= 6:
                raise
            time.sleep(8 * attempt)
