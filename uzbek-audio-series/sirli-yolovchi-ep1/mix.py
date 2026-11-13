"""Generate atmospheric sound design (rain, engine, wipers, sfx, police sirens, music)
and mix everything into mix.wav.
"""
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

print(f"Building soundscape for duration: {D:.2f}s...")

# 1. Procedural Wipers track (stereo, every 1.8s)
print("Generating windshield wiper clicks and swooshes...")
wiper_bus = np.zeros((N, 2), dtype=np.float32)
wiper_period = 1.85
num_wipes = int(D / wiper_period)
for w in range(num_wipes):
    t_wipe = w * wiper_period + 0.3
    idx = int(t_wipe * SR)
    if idx + int(0.4 * SR) >= N:
        break
    
    # Swoosh 1 (left to right)
    dur_s = int(0.28 * SR)
    t = np.linspace(0, 1, dur_s, endpoint=False)
    # Bandpassed noise burst + tone
    noise = np.random.normal(0, 0.15, dur_s) * np.sin(np.pi * t)**2
    pan = np.linspace(-0.6, 0.6, dur_s) if (w % 2 == 0) else np.linspace(0.6, -0.6, dur_s)
    
    wiper_bus[idx:idx + dur_s, 0] += noise * (1 - pan) * 0.28
    wiper_bus[idx:idx + dur_s, 1] += noise * (1 + pan) * 0.28
    
    # Soft rubber click at turning point
    click_len = int(0.02 * SR)
    click = np.random.normal(0, 0.25, click_len) * np.linspace(1, 0, click_len)**3
    wiper_bus[idx + dur_s - click_len:idx + dur_s, 0] += click * 0.2
    wiper_bus[idx + dur_s - click_len:idx + dur_s, 1] += click * 0.2

# 2. Police Siren at the climax (from t=152.0 to end)
print("Generating distant rising police siren...")
siren_start_t = 153.0
siren_idx = int(siren_start_t * SR)
if siren_idx < N:
    siren_len = N - siren_idx
    t_siren = np.arange(siren_len) / SR
    # European wail siren: 650 Hz to 950 Hz cycling every 1.5s
    freq = 780.0 + 180.0 * np.sin(2 * np.pi * t_siren / 1.4)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    siren_raw = np.sin(phase) * 0.18
    # Fade in
    fade_len = int(2.5 * SR)
    if len(siren_raw) > fade_len:
        siren_raw[:fade_len] *= np.linspace(0, 1, fade_len)
    
    # Add slight echo/reverb through stereo separation
    delay = int(0.04 * SR)
    siren_stereo = np.zeros((siren_len, 2), dtype=np.float32)
    siren_stereo[:, 0] = siren_raw * 0.85
    siren_stereo[delay:, 1] = siren_raw[:-delay] * 0.75 if delay < siren_len else siren_raw * 0.75
    
    wiper_bus[siren_idx:, :] += siren_stereo

# 3. Match strike SFX at t=37.0 (when Yo'lovchi lights cigarette)
match_t = 38.0
match_idx = int(match_t * SR)
if match_idx + int(0.5 * SR) < N:
    dur_m = int(0.45 * SR)
    t = np.linspace(0, 1, dur_m, endpoint=False)
    # Scratching noise
    scratch = np.random.normal(0, 0.4, dur_m) * np.exp(-4 * t)
    wiper_bus[match_idx:match_idx + dur_m, 0] += scratch * 0.35
    wiper_bus[match_idx:match_idx + dur_m, 1] += scratch * 0.35

# 4. Save custom sfx bed (wiper, sirens, match) to sfx_proc.wav
sfx_proc_wav = os.path.join(HERE, 'sfx_proc.wav')
with wave.open(sfx_proc_wav, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((wiper_bus.clip(-1, 1) * 32767).astype('<i2').tobytes())
print("sfx_proc.wav created!")

# 5. Composite Mix with FFmpeg
# Inputs:
# 0: Narration (narration.wav)
# 1: Procedural SFX (wipers, sirens, match)
# 2: Rain background (synthesized pink noise stereo bandpass)
# 3: Car engine cabin rumble (brown noise lowpass)
# 4: Cinematic music (looped m74.mp3 or m473.mp3 with sidechain)
# Background music is not included in the repo. Point SERIES_MUSIC at any mp3/wav you have the rights to;
# without it a silent bed is used so the rest of the mix still renders.
MUSIC_SRC = os.environ.get('SERIES_MUSIC', '')
MUSIC_IN = ['-i', MUSIC_SRC] if MUSIC_SRC and os.path.exists(MUSIC_SRC) else ['-f', 'lavfi', '-t', f'{D:.2f}', '-i', f'anullsrc=r={SR}:cl=stereo']

print("Synthesizing rain, engine and mastering mix with FFmpeg...")
filt = (
    # Rain ambience (stereo, continuous)
    f"anoisesrc=c=pink:r={SR}:a=0.18,lowpass=f=2600,highpass=f=260,volume=0.45[rain_l];"
    f"anoisesrc=c=pink:r={SR}:a=0.18,lowpass=f=2900,highpass=f=310,volume=0.45[rain_r];"
    f"[rain_l][rain_r]amerge=inputs=2,atrim=0:{D:.2f}[rain];"
    
    # Engine rumble inside car cabin (low frequency)
    f"anoisesrc=c=brown:r={SR}:a=0.22,lowpass=f=110,volume=0.40,atrim=0:{D:.2f},aformat=channel_layouts=stereo[engine];"
    
    # Music looped & filtered to sound deep, atmospheric, dark noir
    f"[2:a]aloop=loop=-1:size=2e+09,atrim=0:{D:.2f},lowpass=f=800,volume=0.38,afade=t=in:d=3,afade=t=out:st={D - 4:.2f}:d=4,aformat=channel_layouts=stereo[music_raw];"
    
    # Duck music under narration speech
    f"[0:a]aformat=channel_layouts=stereo,asplit=2[nar][key];"
    f"[music_raw][key]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=350[music_ducked];"
    
    # Sum SFX: rain + engine + procedural (wipers/siren)
    f"[1:a]volume=0.75[proc_sfx];"
    f"[rain][engine][proc_sfx]amix=inputs=3:normalize=0[ambience];"
    
    # Final master sum: speech (nar) + ducked music + ambience -> limiter -> loudnorm (-15 LUFS)
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
