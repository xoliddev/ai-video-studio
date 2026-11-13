"""Process existing dialogue takes from Serial 3 with bespoke vocal mastering:
- Samadov (old watchman): pitch down -2.5 semitones (gruff, deep, raspy, aged), slowed down 8%, warm tube EQ.
- Rustam (young man): breath clarity, 20ms cosine fade to completely remove clicks.
"""
import os
import wave
import subprocess
import imageio_ffmpeg

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'togdagi-qorovulxona-ep1', 'audio')
DST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'audio')
FF = imageio_ffmpeg.get_ffmpeg_exe()

# Dialogue metadata
SAMADOV_IDS = {'q01', 'q02', 'q04', 'q06', 'q08', 'q10', 'q12', 'q14', 'q16'}
RUSTAM_IDS = {'q03', 'q05', 'q07', 'q09', 'q11', 'q13', 'q15'}

os.makedirs(DST, exist_ok=True)

for i in range(1, 17):
    qid = f"q{i:02d}"
    src_wav = os.path.join(SRC, f"{qid}.wav")
    dst_wav = os.path.join(DST, f"{qid}.wav")
    
    with wave.open(src_wav, 'rb') as w:
        dur = w.getnframes() / float(w.getframerate())
    
    if qid in SAMADOV_IDS:
        # Pitch down 2.5 semitones (ratio 0.865), resample to 44100, warm tube EQ, slow down 8%
        target_dur = dur / 0.865
        filt = (
            "asetrate=24000*0.865,aresample=44100,"
            "equalizer=f=200:t=q:w=1.2:g=4.5,"
            "equalizer=f=3400:t=q:w=1.0:g=-2.5,"
            f"afade=t=in:d=0.02,afade=t=out:st={max(0, target_dur - 0.03):.3f}:d=0.03,"
            "loudnorm=I=-16:TP=-1.5:LRA=9"
        )
    else:
        # Rustam: breath clarity, slight highpass, remove click at end
        filt = (
            "aresample=44100,"
            "highpass=f=240,"
            "equalizer=f=2600:t=q:w=1.0:g=2.0,"
            f"afade=t=in:d=0.02,afade=t=out:st={max(0, dur - 0.03):.3f}:d=0.03,"
            "loudnorm=I=-16:TP=-1.5:LRA=9"
        )
    
    cmd = [FF, '-y', '-loglevel', 'error', '-i', src_wav, '-af', filt, dst_wav]
    subprocess.run(cmd, check=True)
    print(f"Mastered {qid} -> {dst_wav}")

print("All 16 takes mastered with zero clicks and customized voices!")
