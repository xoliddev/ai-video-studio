"""Generate sound design (blizzard wind, fireplace, door thuds, footsteps, rifle cocking, gunshot) and mix into mix.wav."""
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

print(f"Building soundscape for Tog'dagi Qorovulxona ({D:.2f}s)...")

sfx_bus = np.zeros((N, 2), dtype=np.float32)

# 1. Fireplace Crackle (continuous micro pops)
for _ in range(int(D * 4)):
    pt = np.random.uniform(0, D)
    pidx = int(pt * SR)
    if pidx + int(0.02 * SR) < N:
        plen = int(0.015 * SR)
        pop = np.random.normal(0, 0.25, plen) * np.linspace(1, 0, plen)**3
        pan = np.random.uniform(-0.4, 0.4)
        sfx_bus[pidx:pidx + plen, 0] += pop * (1 - pan) * 0.18
        sfx_bus[pidx:pidx + plen, 1] += pop * (1 + pan) * 0.18

# 2. Heavy Door Knocking at t=20.8s (3 loud gursillash)
knock_t = 20.8
for k in range(3):
    kt = knock_t + k * 0.75
    kidx = int(kt * SR)
    if kidx + int(0.25 * SR) < N:
        klen = int(0.2 * SR)
        t = np.linspace(0, 0.2, klen, endpoint=False)
        # Deep wood impact
        thud = np.sin(2 * np.pi * 95 * t) * np.exp(-18 * t) * 0.65
        thud += np.random.normal(0, 0.3, klen) * np.exp(-25 * t) * 0.35
        sfx_bus[kidx:kidx + klen, 0] += thud * 0.75
        sfx_bus[kidx:kidx + klen, 1] += thud * 0.75

# 3. Snow Crunching Footsteps outside (t=136.0s to 142.0s)
for step in range(6):
    st = 136.0 + step * 0.95
    sidx = int(st * SR)
    if sidx + int(0.3 * SR) < N:
        slen = int(0.25 * SR)
        t = np.linspace(0, 0.25, slen, endpoint=False)
        crunch = np.random.normal(0, 0.25, slen) * np.sin(np.pi * t / 0.25)**2
        sfx_bus[sidx:sidx + slen, 0] += crunch * 0.28
        sfx_bus[sidx:sidx + slen, 1] += crunch * 0.32

# 4. Rifle cocking at t=148.5s
rc_idx = int(148.5 * SR)
if rc_idx + int(0.3 * SR) < N:
    rlen = int(0.25 * SR)
    t = np.linspace(0, 0.25, rlen, endpoint=False)
    click1 = np.sin(2 * np.pi * 2200 * t[:int(0.04*SR)]) * np.exp(-50 * t[:int(0.04*SR)]) * 0.5
    sfx_bus[rc_idx:rc_idx + len(click1), 0] += click1
    sfx_bus[rc_idx:rc_idx + len(click1), 1] += click1
    
    # Second mechanical snap
    rc2 = rc_idx + int(0.12 * SR)
    sfx_bus[rc2:rc2 + len(click1), 0] += click1 * 0.8
    sfx_bus[rc2:rc2 + len(click1), 1] += click1 * 0.8

# 5. Gunshot and Mountain Echo at t=151.0s
gs_idx = int(151.0 * SR)
if gs_idx + int(2.5 * SR) < N:
    gslen = int(2.5 * SR)
    t = np.linspace(0, 2.5, gslen, endpoint=False)
    shot = np.random.normal(0, 0.8, gslen) * np.exp(-12 * t)
    # Deep boom
    boom = np.sin(2 * np.pi * 65 * t) * np.exp(-4 * t) * 0.8
    gunshot = shot + boom
    sfx_bus[gs_idx:gs_idx + gslen, 0] += gunshot * 0.7
    sfx_bus[gs_idx:gs_idx + gslen, 1] += gunshot * 0.7

sfx_proc_wav = os.path.join(HERE, 'sfx_proc.wav')
with wave.open(sfx_proc_wav, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((sfx_bus.clip(-1, 1) * 32767).astype('<i2').tobytes())
print("sfx_proc.wav created!")

# 6. Composite Mix
# Background music is not included in the repo. Point SERIES_MUSIC at any mp3/wav you have the rights to;
# without it a silent bed is used so the rest of the mix still renders.
MUSIC_SRC = os.environ.get('SERIES_MUSIC', '')
MUSIC_IN = ['-i', MUSIC_SRC] if MUSIC_SRC and os.path.exists(MUSIC_SRC) else ['-f', 'lavfi', '-t', f'{D:.2f}', '-i', f'anullsrc=r={SR}:cl=stereo']

filt = (
    # Howling Blizzard Wind (deep & mid stereo swells)
    f"anoisesrc=c=pink:r={SR}:a=0.22,lowpass=f=950,highpass=f=90,volume=0.48[wind_l];"
    f"anoisesrc=c=pink:r={SR}:a=0.22,lowpass=f=1100,highpass=f=110,volume=0.48[wind_r];"
    f"[wind_l][wind_r]amerge=inputs=2,atrim=0:{D:.2f}[wind];"
    
    # Low mountain rumble
    f"anoisesrc=c=brown:r={SR}:a=0.20,lowpass=f=80,volume=0.38,atrim=0:{D:.2f},aformat=channel_layouts=stereo[rumble];"
    
    # Cinematic music (dark cello/drone)
    f"[2:a]aloop=loop=-1:size=2e+09,atrim=0:{D:.2f},lowpass=f=900,volume=0.36,afade=t=in:d=3,afade=t=out:st={D - 4:.2f}:d=4,aformat=channel_layouts=stereo[music_raw];"
    
    # Sidechain ducking under speech
    f"[0:a]aformat=channel_layouts=stereo,asplit=2[nar][key];"
    f"[music_raw][key]sidechaincompress=threshold=0.03:ratio=4:attack=25:release=350[music_ducked];"
    
    # Mix sfx & ambience
    f"[1:a]volume=0.85[proc_sfx];"
    f"[wind][rumble][proc_sfx]amix=inputs=3:normalize=0[ambience];"
    
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
