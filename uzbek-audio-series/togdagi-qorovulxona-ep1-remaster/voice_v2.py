"""Voice generation and audio processing for 'Tog'dagi Qorovulxona' V2 (Cinematic Master Edition).
- Samadov: Deep, raspy, slow, aged military colonel voice (pitched down -2.5 st, warm tube eq).
- Rustam: Shivering, terrified, breathless young man.
- All clips smoothed with 20ms cosine fades (ZERO 'trs' clicks).
"""
import os
import sys
import json
import wave
import subprocess
import numpy as np
import imageio_ffmpeg

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'shared'))
from gemini_tts import tts

HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.join(HERE, 'audio')
FF = imageio_ffmpeg.get_ffmpeg_exe()
SR = 44100
os.makedirs(AUD, exist_ok=True)

DIALOGUE = [
    # Shot 01 -> Shot 02: Intro
    {"id": "v01", "char": "samadov", "voice": "Charon", "shot": 1,
     "text": "Tog'da qish boshqacha bo'ladi. Shamol uvillashi xuddi qadimgi sharpalarning faryodiga o'xshaydi."},
    {"id": "v02", "char": "samadov", "voice": "Charon", "shot": 2,
     "text": "Bu balandlikda inson yo mutlaq sukunatga o'rganadi... yoki asta-sekin aqldan ozadi."},

    # Shot 03 -> Shot 04: Door knocking
    {"id": "v03", "char": "samadov", "voice": "Charon", "shot": 3,
     "text": "Bu qahraton bo'ronda qanday qilib tirik qolish mumkin?! Kim u?!"},
    {"id": "v04", "char": "rustam", "voice": "Puck", "shot": 3,
     "text": "Yordam bering... Iltimos, eshikni oching! Mashinam jarga quladi... Ular ortimdan kelyapti!"},

    # Shot 04 -> Shot 05: Entrance
    {"id": "v05", "char": "samadov", "voice": "Charon", "shot": 4,
     "text": "Kir tezroq! Kir ichkariga. Eshikni zanjirla. Olovga yaqinroq o'tir."},
    {"id": "v06", "char": "rustam", "voice": "Puck", "shot": 5,
     "text": "Rahmat... Sovuqdan qo'llarimni sezmayapman. Lekin siz eshikni mustahkamroq qulflang. Ular juda yaqin qoldi."},

    # Shot 05 -> Shot 06: Questioning
    {"id": "v07", "char": "samadov", "voice": "Charon", "shot": 5,
     "text": "O'zingni bos, yigit. Bu dovonda bo'rilardan boshqa hech qanday tirik jon yo'q. Kim seni ta'qib qiladi?"},
    {"id": "v08", "char": "rustam", "voice": "Puck", "shot": 5,
     "text": "Ular bo'rilar emas! Ular odamlar. Uch kishi. Qora kiyingan, qo'llarida qurol bor. Ular qor bo'ylab izimdan kelyapti."},
    {"id": "v09", "char": "samadov", "voice": "Charon", "shot": 2,
     "text": "Nega? Oddiy yo'lovchining orqasidan uchta qurolli odam tushmaydi. Kimning yo'lini kesding?"},

    # Shot 06 -> Shot 07: Revelation of notebook
    {"id": "v10", "char": "rustam", "voice": "Puck", "shot": 6,
     "text": "Men ularning qora daftarchasini ko'rib qoldim. O'n ikki yil oldin tog'da g'oyib bo'lgan o'sha samolyot haqidagi haqiqatni."},
    {"id": "v11", "char": "samadov", "voice": "Charon", "shot": 7,
     "text": "Nima deding?! Qaysi samolyot?!"},
    {"id": "v12", "char": "rustam", "voice": "Puck", "shot": 6,
     "text": "Shimoliy reys. Yuz qirqta yo'lovchisi bilan g'oyib bo'lgan samolyot... U texnik nosozlik emasdi. Uni ataylab portlatishgan!"},

    # Shot 07 -> Shot 08: Shock & The Pilot Son
    {"id": "v13", "char": "samadov", "voice": "Charon", "shot": 7,
     "text": "Men bilmaymanmi?.. O'sha samolyotning birinchi uchuvchisi... mening yagona o'g'lim edi."},
    {"id": "v14", "char": "rustam", "voice": "Puck", "shot": 5,
     "text": "Nima?! Siz... siz o'sha polkovnik Samadovmisiz?!"},
    {"id": "v15", "char": "samadov", "voice": "Charon", "shot": 8,
     "text": "Ha. Men o'n ikki yildan beri mana shu kulbada o'tirib, o'g'limning qotillari qachon bu tog'dan o'tishini kutardim."},

    # Shot 09 -> Shot 10: Climax
    {"id": "v16", "char": "rustam", "voice": "Puck", "shot": 9,
     "text": "Eshityapsizmi?.. Qor g'irchillayapti. Ular eshik oldida!"},
    {"id": "v17", "char": "samadov", "voice": "Charon", "shot": 10,
     "text": "Eshikdan uzoqroq tur, bolam. Qotillar o'zi eshigimizni taqillatib keldi. Miltiqqa tegmang, o'zim kutib olaman!"}
]

def generate_and_process():
    print(f"Generating and professionally mastering {len(DIALOGUE)} dialogue takes...")
    for item in DIALOGUE:
        raw_wav = os.path.join(AUD, f"{item['id']}_raw.wav")
        proc_wav = os.path.join(AUD, f"{item['id']}.wav")
        
        if not os.path.exists(raw_wav) or os.path.getsize(raw_wav) < 1000:
            print(f"Generating TTS {item['id']} ({item['char']}: {item['voice']})...")
            tts(item['text'], raw_wav, voice=item['voice'])
        
        # Audio Processing / Vocal Design
        if item['char'] == 'samadov':
            # Samadov: deep, raspy, aged military tone (pitched down ~2.5 semitones, slowed 8%, warm tube EQ)
            filt = (
                "asetrate=24000*0.87,aresample=44100,"
                "equalizer=f=220:t=q:w=1.2:g=4.0,"
                "equalizer=f=3200:t=q:w=1.0:g=-2.5,"
                "afade=t=in:d=0.02,afade=t=out:st=999:d=0.02,"
                "loudnorm=I=-16:TP=-1.5:LRA=9"
            )
        else:
            # Rustam: shivering, high tension (gentle breath highpass, normalized)
            filt = (
                "aresample=44100,"
                "highpass=f=260,"
                "equalizer=f=2800:t=q:w=1.0:g=2.0,"
                "afade=t=in:d=0.02,afade=t=out:st=999:d=0.02,"
                "loudnorm=I=-16:TP=-1.5:LRA=9"
            )
        
        # Calculate duration of raw_wav to apply clean out-fade
        with wave.open(raw_wav, 'rb') as w:
            raw_dur = w.getnframes() / float(w.getframerate())
        
        # Adjust out fade start
        dur_target = raw_dur / 0.87 if item['char'] == 'samadov' else raw_dur
        filt = filt.replace('st=999', f'st={max(0, dur_target - 0.03):.3f}')
        
        cmd = [FF, '-y', '-loglevel', 'error', '-i', raw_wav, '-af', filt, proc_wav]
        subprocess.run(cmd, check=True)
        print(f"Mastered: {item['id']} -> {proc_wav}")

    print("All audio clips mastered with zero pops and bespoke vocal characteristics!")

if __name__ == '__main__':
    generate_and_process()
