"""Assemble timeline and narration for Episode 2:
'Tog'dagi Qorovulxona — 2-Qism: Ostonadagi To'qnashuv'
Duration: ~157.1s (2.62 mins).
Zero clicks, professional cinematic pacing.
"""
import json
import os
import subprocess
import wave
import numpy as np
import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.join(HERE, 'audio')
FF = imageio_ffmpeg.get_ffmpeg_exe()
SR = 44100

SHOT_MAP = {
    "e2_01": {"shot": 1, "speaker": "POLKOVNIK SAMADOV", "char": "samadov", "text": "Eshikni sindirishdi... Qimirlama, Rustam!"},
    "e2_02": {"shot": 2, "speaker": "QORA NIQOBLI BOSHLIQ", "char": "boshliq", "text": "Miltiqni tushir, chol. Bu yerda buyruqni men beraman."},
    "e2_03": {"shot": 3, "speaker": "POLKOVNIK SAMADOV", "char": "samadov", "text": "Mening ostonamga qurol bilan bostirib kirgan odam buyruq berolmaydi. Yana bir qadam bossang, ko'kragingga qo'rg'oshin kiradi."},
    "e2_04": {"shot": 4, "speaker": "QORA NIQOBLI BOSHLIQ", "char": "boshliq", "text": "Qaribsan, polkovnik Samadov... Haliyam o'sha eski gvardiyaning o'jar tabiati. O'g'ling Temur ham o'sha samolyot kabinasida xuddi shunday gapirgan edi."},
    "e2_05": {"shot": 5, "speaker": "RUSTAM (BEGONA)", "char": "rustam", "text": "Polkovnik, unga quloq solmang! Ular tirik qoldirmaydi, hech kimni tirik qoldirmaydi!"},
    "e2_06": {"shot": 6, "speaker": "POLKOVNIK SAMADOV", "char": "samadov", "text": "Demak, o'g'limning samolyotini portlatgan vijdonsiz qotil sen ekansanda?! Yuz qirqta begunoh yo'lovchining uvoli tutmadimi seni?!"},
    "e2_07": {"shot": 7, "speaker": "QORA NIQOBLI BOSHLIQ", "char": "boshliq", "text": "Bu shaxsiy masala emasdi, polkovnik. Shunchaki katta buyruq. O'sha reysda xoinlikni fosh qiluvchi komissiya uchayotgan edi. Ular yerga sog'-omon qo'nishi mumkin emasdi."},
    "e2_08": {"shot": 7, "speaker": "QORA NIQOBLI BOSHLIQ", "char": "boshliq", "text": "Va bugun ham o'sha qoidamiz o'zgarmagan: bu sirni bilgan hech kim bu tog'dan tirik tushmaydi!"},
    "e2_09": {"shot": 8, "speaker": "RUSTAM (BEGONA)", "char": "rustam", "text": "Daftarchada barcha buyurtmachilarning ismi bor... Ular orasida general Karimov ham bor, polkovnik!"},
    "e2_10": {"shot": 3, "speaker": "POLKOVNIK SAMADOV", "char": "samadov", "text": "Karimov?.. Demak, sotqin eng tepada o'tirgan ekan..."},
    "e2_11": {"shot": 9, "speaker": "QORA NIQOBLI BOSHLIQ", "char": "boshliq", "text": "Ortiqcha gapirdingiz. Yigitlar, ikkalasini ham joyida yo'qotinglar!"},
    "e2_12": {"shot": 5, "speaker": "RUSTAM (BEGONA)", "char": "rustam", "text": "Polkovnik, otishyapti!!"},
    "e2_13": {"shot": 10, "speaker": "POLKOVNIK SAMADOV", "char": "samadov", "text": "Yot pastga, Rustam! Qorong'uda jang qilamiz!!"}
}

PAUSES = {
    "e2_01": 5.0, # Door crash echo, heavy tactical boots in snow
    "e2_02": 4.5, # Samadov double-barrel shotgun rack
    "e2_03": 5.5, # Leader cold mocking smile
    "e2_04": 5.2, # Shivering breathing in silence
    "e2_05": 5.8, # Grief & burning rage in Samadov's eyes
    "e2_06": 5.2, # Pistol cock click & red laser
    "e2_07": 4.0, # Cold mercenary cadence
    "e2_08": 5.0, # Notebook reveal tension
    "e2_09": 6.0, # Shocking silence: General Karimov!
    "e2_10": 4.5, # Mercenary leader order
    "e2_11": 2.8, # Rustam terrified scream
    "e2_12": 2.2, # Samadov combat leap
    "e2_13": 16.5 # Epic Climax Shootout & Outro
}

def build():
    lines = []
    current_time = 6.0 # Intro with title card & splintering door impact

    for i in range(1, 14):
        qid = f"e2_{i:02d}"
        wav_p = os.path.join(AUD, f"{qid}.wav")
        with wave.open(wav_p, 'rb') as w:
            dur = w.getnframes() / float(w.getframerate())
        
        start_t = current_time
        end_t = current_time + dur
        pause = PAUSES.get(qid, 2.5)
        current_time = end_t + pause

        info = SHOT_MAP[qid]
        lines.append({
            "id": qid,
            "speaker": info['speaker'],
            "char": info['char'],
            "shot": info['shot'],
            "text": info['text'],
            "a": round(start_t, 3),
            "b": round(end_t, 3),
            "dur": round(dur, 3)
        })

    total_duration = round(current_time, 3)

    tl = {
        "title": "Tog'dagi Qorovulxona — 2-Qism (Cinematic Master)",
        "subtitle": "Ostonadagi To'qnashuv",
        "duration": total_duration,
        "fps": 24,
        "width": 1080,
        "height": 1920,
        "lines": lines
    }

    with open(os.path.join(HERE, 'timeline.json'), 'w', encoding='utf-8') as f:
        json.dump(tl, f, indent=2, ensure_ascii=False)

    with open(os.path.join(HERE, 'timeline.js'), 'w', encoding='utf-8') as f:
        f.write('window.TL = ' + json.dumps(tl, ensure_ascii=False, indent=2) + ';')

    print(f"Timeline Episode 2 created! Total duration: {total_duration}s ({total_duration/60:.2f} mins)")

    # Build narration.wav
    total_samples = int(total_duration * SR) + SR
    nar_bus = np.zeros(total_samples, dtype=np.float32)

    for line in lines:
        wav_p = os.path.join(AUD, f"{line['id']}.wav")
        cmd = [FF, '-loglevel', 'error', '-i', wav_p, '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-']
        raw = subprocess.run(cmd, capture_output=True, check=True).stdout
        audio = np.frombuffer(raw, np.float32)
        idx = int(line['a'] * SR)
        avail = min(len(audio), total_samples - idx)
        nar_bus[idx:idx + avail] += audio[:avail]

    nar_wav = os.path.join(HERE, 'narration.wav')
    peak = np.abs(nar_bus).max() or 1.0
    nar_bus = nar_bus * (0.95 / peak)
    with wave.open(nar_wav, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((nar_bus.clip(-1, 1) * 32767).astype('<i2').tobytes())
    print("narration.wav for Episode 2 created!")

if __name__ == '__main__':
    build()
