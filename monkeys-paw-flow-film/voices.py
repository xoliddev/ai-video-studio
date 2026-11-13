"""Dialogue lines for The Monkey's Paw -> one WAV per line (Gemini TTS on Vertex, Cloud credit).

python voices.py            # renders every line in LINES that is not cached yet
python voices.py --test     # one sample line per character
"""
import os, sys, json, wave, base64, subprocess
# uztts: the author's Uzbek Gemini-TTS helper (Vertex AI + gcloud token); not part of this repo
sys.path.insert(0, os.environ.get('UZTTS_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uz-tts-tool')))
import uztts  # Gemini, GcloudToken, clean, load_env

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'voice')
MODEL = 'gemini-3.8-flash-tts'

# character -> prebuilt Gemini voice
CAST = {
    'MR_WHITE': 'Iapetus',
    'MRS_WHITE': 'Sulafat',
    'HERBERT': 'Puck',
    'MORRIS': 'Algenib',
    'STRANGER': 'Charon',
}

TEST = {
    'MR_WHITE': "Kerak bo'lmasa, Morris, menga bering.",
    'MRS_WHITE': "O'zingiz uchta tilagingizni tiladingizmi, serjant?",
    'HERBERT': "Imperator bo'lishni tilang, ota! Ana unda onam ham sizga buyruq berolmaydi.",
    'MORRIS': "Bir keksa darvesh unga sehr o'qigan. Uch kishining har biri uchtadan tilak tilashi mumkin.",
    'STRANGER': "Men Mo va Megginz fabrikasidan keldim. Afsuski... baxtsiz hodisa yuz berdi.",
}


def engine(voice):
    env = uztts.load_env()
    return uztts.Gemini([], MODEL, voice, '', 'vertex', env.get('GOOGLE_CLOUD_PROJECT'), env.get('GOOGLE_CLOUD_ACCOUNT'))


def render(key, char, text):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f'{key}.wav')
    if os.path.exists(path):
        return path
    pcm = engine(CAST[char]).synth(text)  # synth() already trims the end-of-clip noise burst
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm.tobytes())
    print('ok', key, char, f'{len(pcm)/48000:.1f}s')
    return path


if __name__ == '__main__':
    if '--test' in sys.argv:
        for char, text in TEST.items():
            render(f'test_{char}', char, text)
