"""Assemble dialogue, generate timeline.json, build narration.wav, sfx.wav, and mix.wav."""
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

# Dialogue data with timing gaps
# Let's inspect the exact audio files and their lengths
from voice import DIALOGUE

def build_timeline():
    lines = []
    # Intro atmospheric lead
    current_time = 3.5  # 3.5s of rain and wipers before the driver speaks

    for idx, item in enumerate(DIALOGUE):
        wav_p = os.path.join(AUD, f"{item['id']}.wav")
        with wave.open(wav_p, 'rb') as w:
            dur = w.getnframes() / float(w.getframerate())
        
        # Pause after this line
        # Dramatic pauses:
        if item['id'] == 'd01':
            pause = 2.2 # Pause after intro: car decelerates, passenger opens door, gets in
        elif item['id'] == 'd03':
            pause = 1.8 # Car accelerates back onto highway
        elif item['id'] == 'd07':
            pause = 1.5 # Driver turns to look
        elif item['id'] == 'd11':
            pause = 1.4 # Mysterious pause about fingers
        elif item['id'] == 'd15':
            pause = 2.0 # Shock/suspicion
        elif item['id'] == 'd18':
            pause = 1.2 # "Hozir to'xtataman!"
        elif item['id'] == 'd19':
            pause = 1.5 # "Avval o'ng qo'lingizga qarang"
        elif item['id'] == 'd20':
            pause = 1.8 # Watch is gone shock
        elif item['id'] == 'd21':
            pause = 1.5 # "Hatto ichki cho'ntagingizdagi hamyon ham sezmadi"
        elif item['id'] == 'd23':
            pause = 0.8 
        elif item['id'] == 'd25':
            pause = 1.2 # Distant sirens wailing loudly
        else:
            pause = 0.9 # Natural conversational pause
        
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

    total_duration = round(current_time + 6.0, 3) # 6s outro with siren & cliffhanger title card
    
    tl = {
        "title": "Sirli Yo'lovchi — 1-Qism",
        "author": "Roald Dahl asari asosida",
        "duration": total_duration,
        "fps": 30,
        "width": 1080,
        "height": 1920,
        "lines": lines
    }

    with open(os.path.join(HERE, 'timeline.json'), 'w', encoding='utf-8') as f:
        json.dump(tl, f, indent=2, ensure_ascii=False)
    
    print(f"Timeline created! Total duration: {total_duration}s ({total_duration/60:.2f} mins)")
    return tl

def build_narration(tl):
    total_samples = int(tl['duration'] * SR) + SR
    nar_bus = np.zeros(total_samples, dtype=np.float32)

    for line in tl['lines']:
        wav_p = os.path.join(AUD, f"{line['id']}.wav")
        # Load through ffmpeg resampled to SR (44100 mono)
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

    # Save narration.wav
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
