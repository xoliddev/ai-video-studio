"""Gemini TTS helper using requests: text -> 24 kHz mono 16-bit WAV.
Rotates through the keys in GEMINI_API_KEYS (env or .env). Fast failover, 15s timeout.
"""
import base64
import json
import os
import threading
import time
import wave
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = 'gemini-3.8-flash-tts'
STYLE = ""


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


def _mark_exhausted(key, reason="quota"):
    with _lock:
        if key not in _exhausted:
            _exhausted.add(key)
            idx = KEYS.index(key) + 1 if key in KEYS else '?'
            print(f'Key #{idx} {reason}, switching ({len(KEYS) - len(_exhausted)} left)', flush=True)


session = requests.Session()


def tts(text, out_wav, voice='Charon', style=STYLE, model=MODEL):
    body = {
        'contents': [{'parts': [{'text': style + text}]}],
        'generationConfig': {
            'responseModalities': ['AUDIO'],
            'speechConfig': {'voiceConfig': {'prebuiltVoiceConfig': {'voiceName': voice}}}
        },
    }
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    attempt = 0

    while True:
        key = api_key()
        headers = {'Content-Type': 'application/json', 'x-goog-api-key': key}
        try:
            r = session.post(url, json=body, headers=headers, timeout=15)
            if r.status_code == 200:
                data = r.json()
                pcm = base64.b64decode(data['candidates'][0]['content']['parts'][0]['inlineData']['data'])
                with wave.open(out_wav, 'wb') as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(24000)
                    w.writeframes(pcm)
                return out_wav
            elif r.status_code == 429:
                txt = r.text
                if 'PerDay' in txt or 'Quota' in txt or 'ResourceExhausted' in txt:
                    _mark_exhausted(key, 'daily quota reached')
                    continue
                else:
                    attempt += 1
                    time.sleep(3 * attempt)
                    continue
            else:
                _mark_exhausted(key, f'HTTP {r.status_code}: {r.text[:80]}')
                continue
        except requests.exceptions.RequestException as e:
            attempt += 1
            if attempt >= 3:
                _mark_exhausted(key, f'connection error: {e}')
                attempt = 0
            time.sleep(2)
