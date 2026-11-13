"""Generate sound design (rain, taxi engine, wipers, taxi radio jazz) and mix into mix.wav."""
import os
import json
import wave
import subprocess
import numpy as np
import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
FF = imageio_ffmpeg.get_ffmpeg_exe()
SR = 44100

tl = json.load(open(os.path.join(HERE, 'timeline.json'), encoding='utf-8'))
D = tl['duration']
N = int(D * SR) + SR

print(f"Building soundscape for Tungi Taksi ({D:.2f}s)...")

# 1. Procedural Wipers track (stereo, every 1.85s)
wiper_bus = np.zeros((N, 2), dtype=np.float32)
wiper_period = 1.85
num_wipes = int(D / wiper_period)
for w in range(num_wipes):
    t_wipe = w * wiper_period + 0.2
    idx = int(t_wipe * SR)
    if idx + int(0.4 * SR) >= N:
        break
    dur_s = int(0.28 * SR)
    t = np.linspace(0, 1, dur_s, endpoint=False)
    noise = np.random.normal(0, 0.12, dur_s) * np.sin(np.pi * t)**2
    pan = np.linspace(-0.5, 0.5, dur_s) if (w % 2 == 0) else np.linspace(0.5, -0.5, dur_s)
    wiper_bus[idx:idx + dur_s, 0] += noise * (1 - pan) * 0.22
    wiper_bus[idx:idx + dur_s, 1] += noise * (1 + pan) * 0.22

# 2. Money cash rustle sound when passenger throws money on dash at t=26.0s
rustle_t = 27.5
rustle_idx = int(rustle_t * SR)
if rustle_idx + int(0.6 * SR) < N:
    dur_r = int(0.55 * SR)
    t = np.linspace(0, 1, dur_r, endpoint=False)
    cash_sound = np.random.normal(0, 0.2, dur_r) * np.exp(-3 * t)
    wiper_bus[rustle_idx:rustle_idx + dur_r, 0] += cash_sound * 0.25
    wiper_bus[rustle_idx:rustle_idx + dur_r, 1] += cash_sound * 0.25

# 3. Soft Turn Signal click (rele) around t=152s when driver takes a U-turn
turn_sig_start = 154.0
for b in range(12):
    sig_t = turn_sig_start + b * 0.65
    sig_idx = int(sig_t * SR)
    if sig_idx + int(0.04 * SR) < N:
        sig_len = int(0.03 * SR)
        sig = np.sin(2 * np.pi * 1200 * np.linspace(0, 0.03, sig_len)) * np.linspace(1, 0, sig_len)**2
        wiper_bus[sig_idx:sig_idx + sig_len, 0] += sig * 0.08
        wiper_bus[sig_idx:sig_idx + sig_len, 1] += sig * 0.04

# Save sfx_proc.wav
sfx_proc_wav = os.path.join(HERE, 'sfx_proc.wav')
with wave.open(sfx_proc_wav, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((wiper_bus.clip(-1, 1) * 32767).astype('<i2').tobytes())
print("sfx_proc.wav created!")

# 4. Composite Mix with FFmpeg
# Background music is not included in the repo. Point SERIES_MUSIC at any mp3/wav you have the rights to;
# without it a silent bed is used so the rest of the mix still renders.
MUSIC_SRC = os.environ.get('SERIES_MUSIC', '')
MUSIC_IN = ['-i', MUSIC_SRC] if MUSIC_SRC and os.path.exists(MUSIC_SRC) else ['-f', 'lavfi', '-t', f'{D:.2f}', '-i', f'anullsrc=r={SR}:cl=stereo']

filt = (
    # Rain on car roof & glass (softer, cozy urban rain)
    f"anoisesrc=c=pink:r={SR}:a=0.15,lowpass=f=2400,highpass=f=280,volume=0.38[rain_l];"
    f"anoisesrc=c=pink:r={SR}:a=0.15,lowpass=f=2700,highpass=f=330,volume=0.38[rain_r];"
    f"[rain_l][rain_r]amerge=inputs=2,atrim=0:{D:.2f}[rain];"
    
    # Low smooth taxi motor hum
    f"anoisesrc=c=brown:r={SR}:a=0.18,lowpass=f=100,volume=0.35,atrim=0:{D:.2f},aformat=channel_layouts=stereo[engine];"
    
    # Taxi radio jazz music (warm, vintage cabin sound)
    f"[2:a]aloop=loop=-1:size=2e+09,atrim=0:{D:.2f},lowpass=f=1100,volume=0.34,afade=t=in:d=3,afade=t=out:st={D - 4:.2f}:d=4,aformat=channel_layouts=stereo[music_raw];"
    
    # Sidechain compression: duck music under speech
    f"[0:a]aformat=channel_layouts=stereo,asplit=2[nar][key];"
    f"[music_raw][key]sidechaincompress=threshold=0.03:ratio=4:attack=25:release=350[music_ducked];"
    
    # Mix sfx & ambience
    f"[1:a]volume=0.70[proc_sfx];"
    f"[rain][engine][proc_sfx]amix=inputs=3:normalize=0[ambience];"
    
    # Final master sum
    f"[nar][music_ducked][ambience]amix=inputs=3:normalize=0:duration=first,alimiter=limit=0.96,loudnorm=I=-15:TP=-1.5:LRA=10[out]"
)

out_mix = os.path.join(HERE, 'mix.wav')
cmd = [
    FF, '-y', '-loglevel', 'error',
    '-i', os.path.join(HERE, 'narration.wav'),
    '-i', sfx_proc_wav,
    *MUSIC_IN,
    '-filter_complex', filt,
    '-map', '[out]',
    '-ar', str(SR),
    out_mix
]
subprocess.run(cmd, check=True)
print(f"Master mix.wav successfully generated! File: {out_mix}")
