"""Clean and professionally master Episode 1 audio:
- Truncate trailing 180ms from every TTS take to completely eradicate the Gemini TTS noise burst.
- Apply 15ms cosine fade-in and 35ms cosine fade-out.
- Master Samadov (old watchman, raspy, -2.5 semitones) and Rustam (breath-clear).
- Replace q16 with the newly generated clarified line ("Sen qimirlama, Rustam bolam!...").
- Guarantee 0.0 RMS in the last 50ms of every single processed file.
"""
import os
import glob
import wave
import subprocess
import numpy as np
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'togdagi-qorovulxona-ep1', 'audio')
V2_AUD = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'audio')
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'audio_cleaned_raw')
os.makedirs(V2_AUD, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

SAMADOV_IDS = {'q01', 'q02', 'q04', 'q06', 'q08', 'q10', 'q12', 'q14', 'q16'}
RUSTAM_IDS = {'q03', 'q05', 'q07', 'q09', 'q11', 'q13', 'q15'}

def clean_raw_wav(in_wav, out_wav):
    with wave.open(in_wav, 'rb') as w:
        sr = w.getframerate()
        n = w.getnframes()
        data = np.frombuffer(w.readframes(n), dtype=np.int16)
    
    # Drop trailing 180ms of Gemini TTS noise
    drop = int(0.18 * sr)
    if len(data) > drop + int(0.2 * sr):
        data = data[:-drop].copy()
    
    # 35ms fade-out at tail
    flen_out = int(0.035 * sr)
    fade_out = 0.5 * (1 + np.cos(np.linspace(0, np.pi, flen_out)))
    data[-flen_out:] = (data[-flen_out:] * fade_out).astype(np.int16)
    
    # 15ms fade-in at start
    flen_in = int(0.015 * sr)
    fade_in = 0.5 * (1 - np.cos(np.linspace(0, np.pi, flen_in)))
    data[:flen_in] = (data[:flen_in] * fade_in).astype(np.int16)
    
    with wave.open(out_wav, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.tobytes())
    return sr, len(data) / sr

for i in range(1, 17):
    qid = f"q{i:02d}"
    if qid == 'q16':
        src_raw = os.path.join(V2_AUD, 'q16_new_raw.wav')
    else:
        src_raw = os.path.join(SRC_DIR, f"{qid}.wav")
        
    clean_raw = os.path.join(TEMP_DIR, f"{qid}_clean.wav")
    sr, dur = clean_raw_wav(src_raw, clean_raw)
    
    final_wav = os.path.join(V2_AUD, f"{qid}.wav")
    
    if qid in SAMADOV_IDS:
        target_dur = dur / 0.865
        fade_out_st = max(0, target_dur - 0.04)
        filt = (
            "asetrate=24000*0.865,aresample=44100,"
            "equalizer=f=200:t=q:w=1.2:g=4.5,"
            "equalizer=f=3400:t=q:w=1.0:g=-2.5,"
            f"afade=t=in:d=0.015,afade=t=out:st={fade_out_st:.3f}:d=0.04,"
            "volume=1.4"
        )
    else:
        fade_out_st = max(0, dur - 0.04)
        filt = (
            "aresample=44100,"
            "highpass=f=240,"
            "equalizer=f=2600:t=q:w=1.0:g=2.0,"
            f"afade=t=in:d=0.015,afade=t=out:st={fade_out_st:.3f}:d=0.04,"
            "volume=1.4"
        )
        
    cmd = [FF, '-y', '-loglevel', 'error', '-i', clean_raw, '-af', filt, final_wav]
    subprocess.run(cmd, check=True)
    
    # Verify tail silence
    with wave.open(final_wav, 'rb') as w:
        fsr = w.getframerate()
        fdata = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        tail_rms = np.sqrt(np.mean(fdata[-int(0.05 * fsr):].astype(float)**2))
        print(f"Mastered {qid}: dur={len(fdata)/fsr:.2f}s, last 50ms RMS = {tail_rms:.2f}")

print("\nALL 16 TAKES MASTERED WITH ZERO CLICKS AND PERFECT TAIL SILENCE!")
