"""Assemble dialogue, generate timeline.json & timeline.js, build narration.wav."""
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

from voice import DIALOGUE

def build_timeline():
    lines = []
    current_time = 3.5  # 3.5s rain & night city jazz intro

    for idx, item in enumerate(DIALOGUE):
        wav_p = os.path.join(AUD, f"{item['id']}.wav")
        with wave.open(wav_p, 'rb') as w:
            dur = w.getnframes() / float(w.getframerate())
        
        # Atmospheric & emotional pauses
        if item['id'] == 't01':
            pause = 2.4 # Car door opens, wet passenger sits in, door thuds shut
        elif item['id'] == 't03':
            pause = 1.6 # Taxi accelerates into rainy city traffic
        elif item['id'] == 't06':
            pause = 2.0 # Deep sigh before Akmal aka speaks
        elif item['id'] == 't09':
            pause = 2.5 # Heavy silence about his son's painful words
        elif item['id'] == 't11':
            pause = 1.8 # Sad realization about lost time
        elif item['id'] == 't12':
            pause = 2.0 # Silence before revealing the locked door
        elif item['id'] == 't13':
            pause = 1.5 
        elif item['id'] == 't15':
            pause = 2.2 # Emotional silence looking at the toy car
        elif item['id'] == 't16':
            pause = 1.2
        elif item['id'] == 't17':
            pause = 1.0
        else:
            pause = 1.1 # Natural conversational pause
        
        start_t = current_time
        end_t = current_time + dur
        current_time = end_t + pause

        lines.append({
            "id": item['id'],
            "char": item['char'],
            "voice": item['voice'],
            "text": item['text'],
            "a": round(start_t, 3),
            "b": round(end_t, 3),
            "dur": round(dur, 3)
        })

    total_duration = round(current_time + 6.0, 3) # Outro title card
    
    tl = {
        "title": "Tungi Taksi: Oynadagi Yomg'ir — 1-Qism",
        "subtitle": "Soat 02:40 dagi mijoz",
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

    print(f"Timeline created! Total duration: {total_duration}s ({total_duration/60:.2f} mins)")
    return tl

def build_narration(tl):
    total_samples = int(tl['duration'] * SR) + SR
    nar_bus = np.zeros(total_samples, dtype=np.float32)

    for line in tl['lines']:
        wav_p = os.path.join(AUD, f"{line['id']}.wav")
        cmd = [FF, '-loglevel', 'error', '-i', wav_p, '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-']
        raw = subprocess.run(cmd, capture_output=True, check=True).stdout
        audio = np.frombuffer(raw, np.float32)
        
        idx = int(line['a'] * SR)
        end_idx = idx + len(audio)
        if end_idx <= total_samples:
            nar_bus[idx:end_idx] += audio
        else:
            avail = total_samples - idx
            nar_bus[idx:total_samples] += audio[:avail]

    nar_wav = os.path.join(HERE, 'narration.wav')
    peak = np.abs(nar_bus).max() or 1.0
    nar_bus = nar_bus * (0.95 / peak)
    with wave.open(nar_wav, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((nar_bus.clip(-1, 1) * 32767).astype('<i2').tobytes())
    print("narration.wav created!")
    return nar_wav

if __name__ == '__main__':
    tl = build_timeline()
    build_narration(tl)
