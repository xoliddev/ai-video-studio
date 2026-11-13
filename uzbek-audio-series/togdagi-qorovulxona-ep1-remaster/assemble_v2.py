"""Assemble dialogue timeline, generate narration.wav, sfx.wav, and mix.wav for V2."""
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
    "q01": {"shot": 1, "text": "Tog'da qish boshqacha bo'ladi. Bo'ron uvillashi xuddi qadimgi sharpalarning faryodiga o'xshaydi. Bu balandlikda odam yo yolg'izlikka o'rganadi... yoki aqldan ozadi.", "char": "samadov"},
    "q02": {"shot": 2, "text": "Bu qahratonda qanday qilib tirik qolish mumkin?! Kim u?!", "char": "samadov"},
    "q03": {"shot": 3, "text": "Yordam bering... Iltimos, oching! Mashinam jarga quladi... Ular... ular ortimdan kelyapti!", "char": "rustam"},
    "q04": {"shot": 4, "text": "Kir, tezroq! Kir ichkariga. Eshikni zanjirla. Olovga yaqinroq o'tir, mana issiq choy.", "char": "samadov"},
    "q05": {"shot": 5, "text": "Rahmat... Qo'llarimni sezmayapman. Lekin siz eshikni mustahkamroq qulflang. Ular bu yerga yetib kelishdi.", "char": "rustam"},
    "q06": {"shot": 2, "text": "O'zingni bos, yigit. Bu dovonda bo'rilardan boshqa hech qanday tirik jon yo'q. Kim seni ta'qib qiladi?", "char": "samadov"},
    "q07": {"shot": 5, "text": "Ular bo'rilar emas! Ular odamlar. Uch kishi. Qora kiyingan, qo'llarida qurol bor. Ular butun qor bo'ylab izimdan kelishyapti.", "char": "rustam"},
    "q08": {"shot": 2, "text": "Nega? Oddiy yo'lovchining orqasidan uchta qurolli odam tushmaydi. Kimning yo'lini kesding?", "char": "samadov"},
    "q09": {"shot": 6, "text": "Men ularning qora daftarchasini ko'rib qoldim. O'n ikki yil oldin tog'da g'oyib bo'lgan o'sha samolyot haqidagi haqiqatni.", "char": "rustam"},
    "q10": {"shot": 7, "text": "Nima deding?! Qaysi samolyot?!", "char": "samadov"},
    "q11": {"shot": 6, "text": "Shimoliy reys. Yuz qirqta yo'lovchisi bilan g'oyib bo'lgan o'sha mashhur samolyot... Siz bilmaysiz, u texnik nosozlik emasdi. U ataylab portlatilgan!", "char": "rustam"},
    "q12": {"shot": 7, "text": "Men bilmaymanmi?.. O'sha samolyotning birinchi uchuvchisi... mening yagona o'g'lim edi.", "char": "samadov"},
    "q13": {"shot": 5, "text": "Nima?! Siz... siz o'sha polkovnik Samadovmisiz?!", "char": "rustam"},
    "q14": {"shot": 8, "text": "Ha. Men o'n ikki yildan beri mana shu kulbada o'tirib, o'g'limning qotillari qachon bu tog'dan o'tishini kutardim.", "char": "samadov"},
    "q15": {"shot": 9, "text": "Eshityapsizmi?.. Qor g'irchillayapti. Ular eshik orqasida!", "char": "rustam"},
    "q16": {"shot": 10, "text": "Sen qimirlama, Rustam bolam! Qurolga teginma, bularni o'zim kutib olaman!", "char": "samadov"}
}

def build():
    lines = []
    current_time = 5.5 # Atmospheric howling blizzard intro

    for i in range(1, 17):
        qid = f"q{i:02d}"
        wav_p = os.path.join(AUD, f"{qid}.wav")
        with wave.open(wav_p, 'rb') as w:
            dur = w.getnframes() / float(w.getframerate())
        
        # Atmospheric pauses
        if qid == 'q01':
            pause = 3.8 # 3 heavy loud knocks GURS! GURS! GURS!
        elif qid == 'q02':
            pause = 2.0 # Desperate stranger voice outside
        elif qid == 'q03':
            pause = 3.0 # Door burst, blizzard rush, collapse
        elif qid == 'q05':
            pause = 2.2 # Tea poured
        elif qid == 'q08':
            pause = 2.0 
        elif qid == 'q09':
            pause = 2.4 # Black notebook revelation
        elif qid == 'q10':
            pause = 1.6
        elif qid == 'q11':
            pause = 3.8 # Shocking silence: "That pilot was my only son"
        elif qid == 'q12':
            pause = 2.0
        elif qid == 'q14':
            pause = 3.4 # Snow footsteps outside approaching
        elif qid == 'q15':
            pause = 1.8 # Rifle cocking clack
        else:
            pause = 1.5
        
        start_t = current_time
        end_t = current_time + dur
        current_time = end_t + pause

        info = SHOT_MAP[qid]
        lines.append({
            "id": qid,
            "char": info['char'],
            "shot": info['shot'],
            "text": info['text'],
            "a": round(start_t, 3),
            "b": round(end_t, 3),
            "dur": round(dur, 3)
        })

    total_duration = round(current_time + 1.8, 3)  # Tight outro after last line (no dead silence)
    
    tl = {
        "title": "Tog'dagi Qorovulxona — 1-Qism (Cinematic Cut)",
        "subtitle": "Bo'ron va Begona",
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

    print(f"Timeline V2 created! Duration: {total_duration}s ({total_duration/60:.2f} mins)")

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
    print("narration.wav created!")
    return tl

if __name__ == '__main__':
    build()
