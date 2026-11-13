"""Mix the reel: narration + music (muffled until the turn, full after it, ducked under the voice) + SFX cues."""
import json, os, subprocess, wave
import numpy as np
import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
FF = imageio_ffmpeg.get_ffmpeg_exe()
SR = 44100
tl = json.load(open(os.path.join(HERE, 'timeline.json'), encoding='utf-8'))
cues = json.load(open(os.path.join(HERE, 'sfx_cues.json'), encoding='utf-8'))
D = tl['duration']
TURN = tl['lines'][3]['a']          # "Keling, buni boshqacha qilamiz."
GROOVE = 15.0                       # where the groove kicks in inside the track
MUSIC = os.path.join(HERE, 'music', 'm473.mp3')

# --- SFX bus from the cue sheet
N = int(D * SR) + SR
bus = np.zeros((N, 2), np.float32)
cache = {}
for c in cues['cues']:
    if c['id'] not in cache:
        raw = subprocess.run([FF, '-loglevel', 'error', '-i', os.path.join(HERE, 'sfx', c['id'] + '.mp3'), '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-'],
                             capture_output=True, check=True).stdout
        a = np.frombuffer(raw, np.float32).reshape(-1, 2)
        cache[c['id']] = a / (np.abs(a).max() or 1)
    a = cache[c['id']]
    if c['dur']:
        n = int(c['dur'] * SR); a = a[:n].copy()
        f = min(len(a), int(.08 * SR)); a[-f:] *= np.linspace(1, 0, f)[:, None]
    i = int(c['t'] * SR)
    if i >= N: continue
    a = a[:N - i] * c['g']
    pan = c['pan']
    bus[i:i + len(a), 0] += a[:, 0] * min(1, 1 - pan)
    bus[i:i + len(a), 1] += a[:, 1] * min(1, 1 + pan)
peak = np.abs(bus).max()
bus *= .9 / peak if peak > .9 else 1
with wave.open(os.path.join(HERE, 'sfx.wav'), 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((bus.clip(-1, 1) * 32767).astype('<i2').tobytes())

# --- final mix
off = max(0, GROOVE - TURN)
before = f"clip(({TURN:.3f}-t)/0.15,0,1)"
after = f"clip((t-{TURN - .05:.3f})/0.15,0,1)"
ST = 'aformat=channel_layouts=stereo'
filt = (
    f"[1:a]atrim=0:{D + 1:.2f},asetpts=PTS-STARTPTS,{ST},asplit=2[ma][mb];"
    f"[ma]lowpass=f=650,volume='0.55*{before}':eval=frame[m1];"
    f"[mb]volume='0.5*{after}':eval=frame[m2];"
    f"[m1][m2]amix=inputs=2:normalize=0,afade=t=out:st={D - 3:.2f}:d=3[mus];"
    f"[0:a]aresample={SR},{ST},asplit=2[nar][key];"
    f"[mus][key]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=350[musd];"
    f"[2:a]{ST},volume=0.65[fx];"
    f"[nar][musd][fx]amix=inputs=3:normalize=0:duration=first,alimiter=limit=0.95,loudnorm=I=-14:TP=-1.5:LRA=11[out]"
)
subprocess.run([FF, '-y', '-loglevel', 'error', '-i', os.path.join(HERE, 'narration.wav'), '-ss', f'{off:.3f}', '-i', MUSIC,
                '-i', os.path.join(HERE, 'sfx.wav'), '-filter_complex', filt, '-map', '[out]', '-ar', str(SR),
                os.path.join(HERE, 'mix.wav')], check=True)
print('mix.wav', round(D, 2), 's; music offset', round(off, 2), 's; cues', len(cues['cues']))
