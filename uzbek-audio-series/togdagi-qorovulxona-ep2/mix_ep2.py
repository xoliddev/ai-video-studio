"""Cinematic Sound Design & Master Mix for Episode 2:
'Tog'dagi Qorovulxona — 2-Qism: Ostonadagi To'qnashuv'
- Direct blizzard wind blowing into the broken cabin doorway.
- Splintered wood door breach, tactical combat boot crunch.
- Shotgun cock, pistol slide rack, rifle selector clicks.
- Psychological horror/dread cello drone.
- Climax shootout: lantern shatter, fire eruption, 12-gauge shotgun blast, SMG burst, shell casing drops.
- Clean vocal mix with zero tail pops.
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

print(f"Synthesizing Episode 2 Soundscape ({D:.2f}s / {D/60:.2f} mins)...")
sfx_bus = np.zeros((N, 2), dtype=np.float32)

# 1. Door Crash & Breach at t=4.5s (Heavy kick, wood splintering, iron lock snap)
kick_idx = int(4.5 * SR)
if kick_idx + int(2.5 * SR) < N:
    klen = int(2.5 * SR)
    t = np.linspace(0, 2.5, klen, endpoint=False)
    # Heavy low-end impact
    kick = np.sin(2 * np.pi * 75 * t) * np.exp(-12 * t) * 1.2
    # Splintering wood
    splinter = np.random.normal(0, 0.6, klen) * np.exp(-6 * t) * (1 + np.sin(2 * np.pi * 850 * t))
    # Iron lock snap
    snap = np.sin(2 * np.pi * 3600 * t[:int(0.05*SR)]) * np.exp(-70 * t[:int(0.05*SR)]) * 0.8
    sfx_bus[kick_idx:kick_idx + klen, 0] += (kick + splinter) * 0.85
    sfx_bus[kick_idx:kick_idx + klen, 1] += (kick + splinter) * 0.85
    sfx_bus[kick_idx:kick_idx + len(snap), 0] += snap
    sfx_bus[kick_idx:kick_idx + len(snap), 1] += snap * 0.7

# 2. Tactical Combat Boots Stepping on snowy floorboards (t=9.8s to 13.5s)
for step, st_time in enumerate([10.2, 11.4, 12.6]):
    sidx = int(st_time * SR)
    slen = int(0.35 * SR)
    if sidx + slen < N:
        st = np.linspace(0, 0.35, slen, endpoint=False)
        step_thud = np.sin(2 * np.pi * 120 * st) * np.exp(-25 * st) * 0.4
        snow_crunch = np.random.normal(0, 0.35, slen) * np.exp(-18 * st) * 0.35
        sfx_bus[sidx:sidx + slen, 0] += (step_thud + snow_crunch) * 0.5
        sfx_bus[sidx:sidx + slen, 1] += (step_thud + snow_crunch) * 0.65

# 3. Double-barrel shotgun cocking (t=18.5s)
rc_idx = int(18.5 * SR)
if rc_idx + int(0.35 * SR) < N:
    t = np.linspace(0, 0.35, int(0.35 * SR), endpoint=False)
    click = np.sin(2 * np.pi * 1900 * t[:int(0.05*SR)]) * np.exp(-50 * t[:int(0.05*SR)]) * 0.6
    sfx_bus[rc_idx:rc_idx + len(click), 0] += click
    sfx_bus[rc_idx:rc_idx + len(click), 1] += click
    rc2 = rc_idx + int(0.12 * SR)
    sfx_bus[rc2:rc2 + len(click), 0] += click * 0.9
    sfx_bus[rc2:rc2 + len(click), 1] += click * 0.9

# 4. Suppressed pistol slide rack (t=83.5s)
sp_idx = int(83.5 * SR)
if sp_idx + int(0.35 * SR) < N:
    t = np.linspace(0, 0.35, int(0.35 * SR), endpoint=False)
    p_metal = np.sin(2 * np.pi * 2800 * t[:int(0.06*SR)]) * np.exp(-40 * t[:int(0.06*SR)]) * 0.5
    sfx_bus[sp_idx:sp_idx + len(p_metal), 0] += p_metal * 0.5
    sfx_bus[sp_idx:sp_idx + len(p_metal), 1] += p_metal * 0.85

# 5. Mercenaries weapon selectors click (t=131.0s)
sel_idx = int(131.0 * SR)
for k, off in enumerate([0.0, 0.18]):
    idx = sel_idx + int(off * SR)
    if idx + int(0.04 * SR) < N:
        t = np.linspace(0, 0.04, int(0.04 * SR), endpoint=False)
        ck = np.sin(2 * np.pi * 3200 * t) * np.exp(-60 * t) * 0.45
        sfx_bus[idx:idx + len(ck), 0] += ck * 0.6
        sfx_bus[idx:idx + len(ck), 1] += ck * 0.7

# 6. Climax Shootout Sequence (t=140.0s to 152.0s)
# 6a. Lantern Shatter & Fire Eruption at t=140.2s
lant_idx = int(140.2 * SR)
if lant_idx + int(2.5 * SR) < N:
    t = np.linspace(0, 2.5, int(2.5 * SR), endpoint=False)
    glass = np.random.normal(0, 0.7, len(t)) * np.exp(-22 * t) * (1 + np.sin(2 * np.pi * 4200 * t))
    fire_whoosh = np.random.normal(0, 0.5, len(t)) * np.exp(-3.5 * t)
    sfx_bus[lant_idx:lant_idx + len(t), 0] += (glass * 0.6 + fire_whoosh * 0.7)
    sfx_bus[lant_idx:lant_idx + len(t), 1] += (glass * 0.6 + fire_whoosh * 0.7)

# 6b. Samadov 12-Gauge Shotgun Blast (KA-BOOM!) at t=141.6s
gun_idx = int(141.6 * SR)
if gun_idx + int(3.5 * SR) < N:
    t = np.linspace(0, 3.5, int(3.5 * SR), endpoint=False)
    boom = np.sin(2 * np.pi * 52 * t) * np.exp(-3.2 * t) * 1.5
    transient = np.random.normal(0, 1.2, len(t)) * np.exp(-18 * t)
    sfx_bus[gun_idx:gun_idx + len(t), 0] += (boom + transient) * 0.95
    sfx_bus[gun_idx:gun_idx + len(t), 1] += (boom + transient) * 0.95

# 6c. Submachine Gun Burst (DA-DA-DA-DA!) at t=143.2s
smg_idx = int(143.2 * SR)
for shot in range(5):
    s_time = smg_idx + int(shot * 0.11 * SR)
    if s_time + int(0.25 * SR) < N:
        t = np.linspace(0, 0.25, int(0.25 * SR), endpoint=False)
        burst_hit = (np.sin(2 * np.pi * 130 * t) * 0.7 + np.random.normal(0, 0.8, len(t)) * 0.5) * np.exp(-28 * t)
        sfx_bus[s_time:s_time + len(t), 0] += burst_hit * 0.75
        sfx_bus[s_time:s_time + len(t), 1] += burst_hit * 0.85

# 6d. Shell Casings Falling on Floorboards (t=144.5s to 146.5s)
for drop_t in [144.6, 144.9, 145.3, 145.8]:
    didx = int(drop_t * SR)
    if didx + int(0.12 * SR) < N:
        t = np.linspace(0, 0.12, int(0.12 * SR), endpoint=False)
        ting = (np.sin(2 * np.pi * 4800 * t) * 0.4 + np.sin(2 * np.pi * 6200 * t) * 0.3) * np.exp(-55 * t)
        sfx_bus[didx:didx + len(ting), 0] += ting * 0.35
        sfx_bus[didx:didx + len(ting), 1] += ting * 0.4

# 7. Psychological Dread Drone (deep 44 Hz sub + 112 Hz eerie cello)
t_all = np.arange(N) / SR
drone_base = (
    np.sin(2 * np.pi * 44.0 * t_all) * 0.32 +
    np.sin(2 * np.pi * 92.5 * t_all) * 0.24 +
    np.sin(2 * np.pi * 138.0 * t_all) * 0.16
)
# Swells during dramatic confrontations
swell = np.ones(N, dtype=np.float32) * 0.3
for (t_start, t_end, peak_val) in [(4.0, 18.0, 0.8), (55.0, 75.0, 0.85), (105.0, 135.0, 0.95), (138.0, 157.0, 1.0)]:
    idx_s, idx_e = int(t_start * SR), int(t_end * SR)
    if idx_s < N:
        idx_e = min(N, idx_e)
        w_len = idx_e - idx_s
        window = np.sin(np.pi * np.linspace(0, 1, w_len))**2
        swell[idx_s:idx_e] += window * (peak_val - 0.3)

dread_drone = drone_base * swell * 0.20
sfx_bus[:, 0] += dread_drone * 0.85
sfx_bus[:, 1] += dread_drone * 0.95

# Save sfx_proc.wav
sfx_proc_wav = os.path.join(HERE, 'sfx_proc.wav')
with wave.open(sfx_proc_wav, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((sfx_bus.clip(-1, 1) * 32767).astype('<i2').tobytes())
print("sfx_proc.wav for Episode 2 created!")

# 8. Composite Mix with FFmpeg (Howling Open Blizzard + Foley + Drone + Speech)
filt = (
    # Howling Blizzard Wind (stronger than ep1 because door is smashed open!)
    f"anoisesrc=c=pink:r={SR}:a=0.22,lowpass=f=1200,highpass=f=90,volume=0.48[wind_l];"
    f"anoisesrc=c=pink:r={SR}:a=0.22,lowpass=f=1350,highpass=f=110,volume=0.48[wind_r];"
    f"[wind_l][wind_r]amerge=inputs=2,atrim=0:{D:.2f}[wind];"
    
    # Mountain sub rumble
    f"anoisesrc=c=brown:r={SR}:a=0.18,lowpass=f=80,volume=0.36,atrim=0:{D:.2f},aformat=channel_layouts=stereo[rumble];"
    
    # Mix ambient wind & rumble with sfx
    f"[1:a]volume=0.92[sfx];"
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
print(f"Master mix.wav for Episode 2 generated! File: {out_mix}")
