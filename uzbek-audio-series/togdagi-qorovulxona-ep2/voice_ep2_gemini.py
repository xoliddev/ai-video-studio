"""Episode 2 Voice Generation — GEMINI TTS ONLY (Charon / Puck / Fenrir)
'Tog'dagi Qorovulxona — 2-Qism: Ostonadagi To'qnashuv'

Characters:
- Samadov (Charon): 65yo veteran colonel, pitched down -2.5st, warm tube EQ = deep raspy authority
- Rustam (Puck): 24yo scared informant, breath-clear highpass
- Boshliq (Fenrir): Cold, merciless mercenary leader, slight pitch down -1st, metallic mid-boost
"""
import sys
import os
import subprocess
import wave
import numpy as np
import imageio_ffmpeg

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'shared'))
from gemini_tts import tts

HERE = os.path.dirname(os.path.abspath(__file__))
AUD_RAW = os.path.join(HERE, 'audio_raw')
AUD = os.path.join(HERE, 'audio')
FF = imageio_ffmpeg.get_ffmpeg_exe()
SR = 44100
os.makedirs(AUD_RAW, exist_ok=True)
os.makedirs(AUD, exist_ok=True)

DIALOGUE = [
    {"id": "e2_01", "char": "samadov", "voice": "Charon",
     "text": "Eshikni sindirishdi... Qimirlama, Rustam!"},
    {"id": "e2_02", "char": "boshliq", "voice": "Fenrir",
     "text": "Miltiqni tushir, chol. Bu yerda buyruqni men beraman."},
    {"id": "e2_03", "char": "samadov", "voice": "Charon",
     "text": "Mening ostonamga qurol bilan bostirib kirgan odam buyruq berolmaydi. Yana bir qadam bossang, qo'rg'oshin ko'kragingga kiradi."},
    {"id": "e2_04", "char": "boshliq", "voice": "Fenrir",
     "text": "Qaribsan, polkovnik Samadov. Haliyam o'sha eski gvardiyaning o'jar tabiati. O'g'ling Temur ham o'sha samolyot kabinasida xuddi shunday gapirgan edi."},
    {"id": "e2_05", "char": "rustam", "voice": "Puck",
     "text": "Polkovnik, unga quloq solmang! Ular tirik qoldirmaydi, hech kimni tirik qoldirmaydi!"},
    {"id": "e2_06", "char": "samadov", "voice": "Charon",
     "text": "Demak, o'g'limning samolyotini portlatgan vijdonsiz qotil sen ekansanda?! Yuz qirqta begunoh yo'lovchining uvoli tutmadimi seni?!"},
    {"id": "e2_07", "char": "boshliq", "voice": "Fenrir",
     "text": "Bu shaxsiy masala emasdi, polkovnik. Shunchaki katta buyruq. O'sha reysda xoinlikni fosh qiluvchi komissiya uchayotgan edi. Ular yerga sog'-omon qo'nishi mumkin emasdi."},
    {"id": "e2_08", "char": "boshliq", "voice": "Fenrir",
     "text": "Va bugun ham o'sha qoidamiz o'zgarmagan. Bu sirni bilgan hech kim bu tog'dan tirik tushmaydi!"},
    {"id": "e2_09", "char": "rustam", "voice": "Puck",
     "text": "Daftarchada barcha buyurtmachilarning ismi bor! Ular orasida general Karimov ham bor, polkovnik!"},
    {"id": "e2_10", "char": "samadov", "voice": "Charon",
     "text": "Karimov?.. Demak, sotqin eng tepada o'tirgan ekan."},
    {"id": "e2_11", "char": "boshliq", "voice": "Fenrir",
     "text": "Ortiqcha gapirdingiz. Yigitlar! Ikkalasini ham joyida yo'qotinglar."},
    {"id": "e2_12", "char": "rustam", "voice": "Puck",
     "text": "Polkovnik, otishyapti!!"},
    {"id": "e2_13", "char": "samadov", "voice": "Charon",
     "text": "Yot pastga, Rustam! Qorong'uda jang qilamiz!!"},
]

def clean_raw(data, sr):
    """Trim trailing 180ms Gemini TTS noise burst + 35ms cosine fade"""
    drop = int(0.18 * sr)
    if len(data) > drop + int(0.2 * sr):
        data = data[:-drop].copy()
    flen = int(0.035 * sr)
    fade = 0.5 * (1 + np.cos(np.linspace(0, np.pi, flen)))
    data[-flen:] = (data[-flen:] * fade).astype(np.int16)
    flen_in = int(0.015 * sr)
    fade_in = 0.5 * (1 - np.cos(np.linspace(0, np.pi, flen_in)))
    data[:flen_in] = (data[:flen_in] * fade_in).astype(np.int16)
    return data

def generate_all():
    for item in DIALOGUE:
        raw_wav = os.path.join(AUD_RAW, f"{item['id']}_gemini_raw.wav")
        clean_wav = os.path.join(AUD_RAW, f"{item['id']}_clean.wav")
        final_wav = os.path.join(AUD, f"{item['id']}.wav")

        # Generate with Gemini TTS
        if not os.path.exists(raw_wav) or os.path.getsize(raw_wav) < 1000:
            print(f"Generating TTS {item['id']} ({item['char']}: {item['voice']})...")
            tts(item['text'], raw_wav, voice=item['voice'])

        # Clean trailing noise
        with wave.open(raw_wav, 'rb') as w:
            sr = w.getframerate()
            data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        cleaned = clean_raw(data, sr)
        with wave.open(clean_wav, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
            w.writeframes(cleaned.tobytes())

        dur = len(cleaned) / sr

        # Character vocal mastering via FFmpeg
        if item['char'] == 'samadov':
            fade_st = max(0, dur / 0.865 - 0.04)
            filt = (
                "asetrate=24000*0.865,aresample=44100,"
                "equalizer=f=200:t=q:w=1.2:g=4.5,"
                "equalizer=f=3400:t=q:w=1.0:g=-2.5,"
                f"afade=t=in:d=0.015,afade=t=out:st={fade_st:.3f}:d=0.04,"
                "volume=1.35"
            )
        elif item['char'] == 'rustam':
            fade_st = max(0, dur - 0.04)
            filt = (
                "aresample=44100,"
                "highpass=f=240,"
                "equalizer=f=2600:t=q:w=1.0:g=2.0,"
                f"afade=t=in:d=0.015,afade=t=out:st={fade_st:.3f}:d=0.04,"
                "volume=1.3"
            )
        else:  # boshliq
            fade_st = max(0, dur / 0.94 - 0.04)
            filt = (
                "asetrate=24000*0.94,aresample=44100,"
                "equalizer=f=260:t=q:w=1.0:g=3.0,"
                "equalizer=f=1600:t=q:w=1.0:g=3.5,"
                "equalizer=f=4200:t=q:w=0.8:g=-2.0,"
                f"afade=t=in:d=0.015,afade=t=out:st={fade_st:.3f}:d=0.04,"
                "volume=1.4"
            )

        subprocess.run([FF, '-y', '-loglevel', 'error', '-i', clean_wav, '-af', filt, final_wav], check=True)

        with wave.open(final_wav, 'rb') as w:
            fdata = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
            fsr = w.getframerate()
            tail_rms = np.sqrt(np.mean(fdata[-int(0.05*fsr):].astype(float)**2))
            print(f"  Mastered {item['id']} ({item['char']}): {len(fdata)/fsr:.2f}s, tail RMS={tail_rms:.1f}")

if __name__ == '__main__':
    generate_all()
    print("\nALL 13 EPISODE 2 DIALOGUE TAKES GENERATED WITH GEMINI TTS!")
