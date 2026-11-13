"""Generate bespoke cinematic sound design for V2:
- Raging mountain blizzard wind (stereo organic pink noise bandpass).
- Fireplace warmth & subtle crackles.
- Door pounding, footsteps, rifle cocking, gunshot.
- Atmospheric psychological dread drone (subdued, haunting, dark tension, never loud or grating).
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

print(f"Building soundscape V2 ({D:.2f}s)...")
sfx_bus = np.zeros((N, 2), dtype=np.float32)

# 1. Fireplace Crackle (gentle, warm pops)
for _ in range(int(D * 3)):
    pt = np.random.uniform(0, D)
    pidx = int(pt * SR)
    if pidx + int(0.02 * SR) < N:
        plen = int(0.012 * SR)
        pop = np.random.normal(0, 0.22, plen) * np.linspace(1, 0, plen)**3
        pan = np.random.uniform(-0.35, 0.35)
        sfx_bus[pidx:pidx + plen, 0] += pop * (1 - pan) * 0.16
        sfx_bus[pidx:pidx + plen, 1] += pop * (1 + pan) * 0.16

# 2. Door Pounding at t=22.35s (realistic multi-layered wood fist pound + iron latch rattle)
# The door-pound sample (mono 16-bit, 44.1 kHz) is not redistributed in this repo: drop your own into audio/.
door_p_wav = os.path.join(HERE, 'audio', 'sfx_door_pound.wav')
if os.path.exists(door_p_wav):
    with wave.open(door_p_wav, 'rb') as dw:
        dp_n = dw.getnframes()
        dp_data = np.frombuffer(dw.readframes(dp_n), dtype=np.int16).astype(np.float32) / 32767.0
else:
    print('audio/sfx_door_pound.wav not found: skipping the door pound')
    dp_data = np.zeros(0, dtype=np.float32)

dp_idx = int(22.35 * SR)
if dp_idx + len(dp_data) < N:
    sfx_bus[dp_idx:dp_idx + len(dp_data), 0] += dp_data * 1.05
    sfx_bus[dp_idx:dp_idx + len(dp_data), 1] += dp_data * 0.72

# 3. Door burst open rush of storm at t=33.5s
burst_idx = int(33.5 * SR)
if burst_idx + int(2.0 * SR) < N:
    blen = int(1.8 * SR)
    t = np.linspace(0, 1.8, blen, endpoint=False)
    whoosh = np.random.normal(0, 0.45, blen) * np.exp(-2.2 * t)
    sfx_bus[burst_idx:burst_idx + blen, 0] += whoosh * 0.55
    sfx_bus[burst_idx:burst_idx + blen, 1] += whoosh * 0.55

# 4. Snow Crunching Footsteps outside (t=145.0s to 151.0s)
for step in range(6):
    st = 145.0 + step * 0.95
    sidx = int(st * SR)
    if sidx + int(0.3 * SR) < N:
        slen = int(0.25 * SR)
        t = np.linspace(0, 0.25, slen, endpoint=False)
        crunch = np.random.normal(0, 0.28, slen) * np.sin(np.pi * t / 0.25)**2
        sfx_bus[sidx:sidx + slen, 0] += crunch * 0.32
        sfx_bus[sidx:sidx + slen, 1] += crunch * 0.35

# 5. Rifle Cocking Click at t=156.8s
rc_idx = int(156.8 * SR)
if rc_idx + int(0.3 * SR) < N:
    rlen = int(0.25 * SR)
    t = np.linspace(0, 0.25, rlen, endpoint=False)
    click1 = np.sin(2 * np.pi * 2100 * t[:int(0.04*SR)]) * np.exp(-45 * t[:int(0.04*SR)]) * 0.55
    sfx_bus[rc_idx:rc_idx + len(click1), 0] += click1
    sfx_bus[rc_idx:rc_idx + len(click1), 1] += click1
    rc2 = rc_idx + int(0.12 * SR)
    sfx_bus[rc2:rc2 + len(click1), 0] += click1 * 0.85
    sfx_bus[rc2:rc2 + len(click1), 1] += click1 * 0.85

# 6. Gunshot & Mountain Echo at t=159.5s
gs_idx = int(159.5 * SR)
if gs_idx + int(2.5 * SR) < N:
    gslen = int(2.5 * SR)
    t = np.linspace(0, 2.5, gslen, endpoint=False)
    shot = np.random.normal(0, 0.85, gslen) * np.exp(-14 * t)
    boom = np.sin(2 * np.pi * 60 * t) * np.exp(-3.5 * t) * 0.85
    gunshot = shot + boom
    sfx_bus[gs_idx:gs_idx + gslen, 0] += gunshot * 0.75
    sfx_bus[gs_idx:gs_idx + gslen, 1] += gunshot * 0.75

# 7. Psychological Dread Drone (Subtle, ominous, shuddering dark cello frequencies)
# 45 Hz sub-bass + 115 Hz dissonant cello drone, swelling at key moments
t_all = np.arange(N) / SR
drone_base = (
    np.sin(2 * np.pi * 48.0 * t_all) * 0.35 +
    np.sin(2 * np.pi * 96.5 * t_all) * 0.25 +
    np.sin(2 * np.pi * 145.2 * t_all) * 0.18
)
# Swells during: Door knocking (t=20..30), Revelation of flight (t=95..120), Armed shadows (t=140..165)
swell = np.ones(N, dtype=np.float32) * 0.25
for (t_start, t_end, peak_val) in [(20.0, 32.0, 0.7), (95.0, 125.0, 0.8), (142.0, 165.0, 0.95)]:
    idx_s, idx_e = int(t_start * SR), int(t_end * SR)
    if idx_s < N:
        idx_e = min(N, idx_e)
        w_len = idx_e - idx_s
        window = np.sin(np.pi * np.linspace(0, 1, w_len))**2
        swell[idx_s:idx_e] += window * (peak_val - 0.25)

dread_drone = drone_base * swell * 0.18 # Kept very subtle and atmospheric!
sfx_bus[:, 0] += dread_drone * 0.85
sfx_bus[:, 1] += dread_drone * 0.95

# Save sfx_proc.wav
sfx_proc_wav = os.path.join(HERE, 'sfx_proc.wav')
with wave.open(sfx_proc_wav, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((sfx_bus.clip(-1, 1) * 32767).astype('<i2').tobytes())
print("sfx_proc.wav created!")

# 8. Composite Mix with FFmpeg (Organic Blizzard Wind + Speech + Procedural SFX)
filt = (
    # Howling Mountain Wind (soft, deep, immersive)
    f"anoisesrc=c=pink:r={SR}:a=0.18,lowpass=f=920,highpass=f=80,volume=0.38[wind_l];"
    f"anoisesrc=c=pink:r={SR}:a=0.18,lowpass=f=1050,highpass=f=100,volume=0.38[wind_r];"
    f"[wind_l][wind_r]amerge=inputs=2,atrim=0:{D:.2f}[wind];"
    
    # Mountain sub rumble
    f"anoisesrc=c=brown:r={SR}:a=0.15,lowpass=f=75,volume=0.32,atrim=0:{D:.2f},aformat=channel_layouts=stereo[rumble];"
    
    # Combine ambient wind & rumble with procedural sfx
    f"[1:a]volume=0.88[sfx];"
    f"[wind][rumble][sfx]amix=inputs=3:normalize=0[ambience];"
    
    # Duck ambience under dialogue
    f"[0:a]aformat=channel_layouts=stereo,asplit=2[nar][key];"
    f"[ambience][key]sidechaincompress=threshold=0.04:ratio=3:attack=30:release=400[amb_ducked];"
    
    # Master output
    f"[nar][amb_ducked]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.96,loudnorm=I=-15:TP=-1.5:LRA=10[out]"
)

out_mix = os.path.join(HERE, 'mix.wav')
cmd = [
    FF, '-y', '-loglevel', 'error',
    '-i', os.path.join(HERE, 'narration.wav'),
    '-i', sfx_proc_wav,
    '-filter_complex', filt,
    '-map', '[out]',
    '-ar', str(SR),
    out_mix
]
subprocess.run(cmd, check=True)
print(f"Master mix.wav V2 generated! File: {out_mix}")
