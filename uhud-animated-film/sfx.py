"""Battle sound design -> sfx.wav (stereo, same length as the narration).

Sounds are Mixkit SFX (free licence) in sfx/. Events are placed on the scene timeline so they match
what the animation shows (charge and clash, arrow volleys, falling standards, the spear, Khalid's
cavalry, the chaos). The mix ducks this track under the narration.
"""
import json, os, subprocess, random
import numpy as np
import imageio_ffmpeg

ROOT = os.path.dirname(os.path.abspath(__file__))
FF = imageio_ffmpeg.get_ffmpeg_exe()
SR = 44100
tl = json.loads(open(os.path.join(ROOT, 'timeline.js'), encoding='utf-8').read().split('=', 1)[1].rstrip().rstrip(';'))
S = {s['id']: s for s in tl['scenes']}
N = int(tl['duration'] * SR) + SR
out = np.zeros((N, 2), np.float32)
rnd = random.Random(7)


def load(name, filt=None):
    """Decode sfx/<name>.mp3 to float stereo, optionally through an ffmpeg filter (lowpass, pitch...)."""
    cmd = [FF, '-loglevel', 'error', '-i', os.path.join(ROOT, 'sfx', name + '.mp3')]
    if filt:
        cmd += ['-af', filt]
    cmd += ['-f', 'f32le', '-ac', '2', '-ar', str(SR), '-']
    a = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).reshape(-1, 2)
    peak = np.abs(a).max() or 1
    return a / peak


SWORDS = [load(n) for n in ['2762', '2763', '2764', '2795', '2160', '2765', '2797', '2794', '2775', '2799']]
SWORDS_FAR = [load(n, 'lowpass=f=1800,volume=0.8') for n in ['2762', '2763', '2795', '2765', '2794']]
SHOUTS = [load(n) for n in ['2175', '2171', '2172', '2170']]
SHOUTS_FAR = [load(n, 'lowpass=f=1500') for n in ['2175', '2171', '2172']]
ARROW = [load(n) for n in ['2767', '2771', '1491']]
ARROW_HIT = load('2769', 'lowpass=f=3000')
NEIGH = [load('85'), load('76')]
NEIGH_FAR = [load('85', 'lowpass=f=1200'), load('76', 'lowpass=f=1200')]
GALLOP = load('77')
GALLOP_FAR = load('77', 'lowpass=f=600')
CROWD = load('458')
CROWD_FAR = load('458', 'lowpass=f=700')
MARCH = load('461', 'lowpass=f=900')
SPEAR = load('2771', 'asetrate=44100*0.62,aresample=44100')
SCRAPE = load('2799', 'asetrate=44100*0.8,aresample=44100,lowpass=f=2500')


def put(clip, t, gain=1.0, pan=0.0):
    i = int(t * SR)
    if i >= N or t < 0:
        return
    c = clip[:N - i] * gain
    lg, rg = np.cos((pan + 1) * np.pi / 4) * 1.414, np.sin((pan + 1) * np.pi / 4) * 1.414
    out[i:i + len(c), 0] += c[:, 0] * lg
    out[i:i + len(c), 1] += c[:, 1] * rg


def bed(clip, a, b, gain, fade=1.5, env=None):
    """Loop a clip from a to b with fades; env(t_rel) can shape the level over time."""
    n = int((b - a) * SR)
    if n <= 0:
        return
    reps = np.concatenate([np.roll(clip, -rnd.randrange(len(clip)), axis=0) for _ in range(n // len(clip) + 2)])[:n]
    t = np.arange(n) / SR
    g = np.minimum(1, np.minimum(t / fade, (b - a - t) / fade)).clip(0, 1) * gain
    if env is not None:
        g = g * env(t)
    i = int(a * SR)
    out[i:i + n] += reps[:N - i] * g[:N - i, None]


def scatter(pool, a, b, every, gain, jitter=.6, pan=.8):
    t = a
    while t < b:
        put(rnd.choice(pool), t, gain * rnd.uniform(.6, 1.0), rnd.uniform(-pan, pan))
        t += every * rnd.uniform(1 - jitter, 1 + jitter)


def L(sc, n):  # line start/end (absolute) like L()/L.E() in film.js
    s = S[sc]; return s['lines'][n]['a'] if n < len(s['lines']) else s['b']


def E(sc, n):
    s = S[sc]; return s['lines'][n]['b'] if n < len(s['lines']) else s['b']


# --- march: the army on the move
s = S['march']
bed(MARCH, s['a'], s['b'], .25)
bed(GALLOP_FAR, s['a'], L('march', 1) + 2, .18)
cut = L('march', 1) + 2.0          # close shot of Khalid's cavalry
bed(GALLOP, cut, s['b'], .55, fade=.8)
put(NEIGH[0], cut + 1.0, .45, .3)

# --- archers: calm before the battle, the Quraysh army murmurs far away
s = S['archers']
bed(CROWD_FAR, s['a'], s['b'] + 1, .12)
put(NEIGH_FAR[0], s['a'] + 4, .25, .6)
put(NEIGH_FAR[1], L('archers', 2) + 1.5, .3, .5)

# --- battle: charge, clash, arrow volleys, standards fall
s = S['battle']; a = s['a']
bed(CROWD, a, s['b'] + .5, .55, fade=1.2, env=lambda t: np.clip(.35 + t / 2.2 * .65, 0, 1))
bed(GALLOP_FAR, a, a + 3, .3)
for k in range(6):                               # the two lines meet at ~2 s
    put(rnd.choice(SWORDS), a + 2.0 + k * .07, .9, rnd.uniform(-.6, .6))
put(SHOUTS[0], a + 1.8, .6, -.3); put(SHOUTS[1], a + 2.1, .6, .4)
scatter(SWORDS, a + 2.4, s['b'], .32, .6)
scatter(SHOUTS, a + 2.5, s['b'], 1.6, .45)
for v in range(14):                              # volleys from the hill (film: start 1 + v, flight 1.3 s)
    st = a + 1 + v
    if st > s['b']:
        break
    put(rnd.choice(ARROW), st, .45, .7)
    put(ARROW_HIT, st + 1.25, .25, .5)
for b in range(3):                               # Quraysh standards fall
    ft = L('battle', 1) + .4 + b * 1.1
    put(SWORDS[3], ft, .8, .2); put(SHOUTS[0], ft + .3, .5, .3)

# --- Hamzah: battle far off, then the spear, then silence
s = S['hamzah']; a = s['a']
cut = L('hamzah', 2) + max(2.3, (E('hamzah', 2) - L('hamzah', 2)) * .5)
bed(CROWD_FAR, a - .5, cut, .3, fade=1.0)
scatter(SWORDS_FAR, a + .5, L('hamzah', 2), .7, .3)
scatter(SHOUTS_FAR, a + 1, L('hamzah', 2), 2.5, .3)
put(SPEAR, L('hamzah', 2) + .8, .9, -.2)
put(SCRAPE, cut + .4, .5, 0)

# --- spoils: the Quraysh flee, the field goes quiet
s = S['spoils']; a = s['a']
bed(CROWD_FAR, a, E('spoils', 0) + 3, .3, fade=2, env=lambda t: np.clip(1 - t / 9, 0, 1))
bed(GALLOP_FAR, a + .5, a + 8, .3, fade=2)
put(NEIGH_FAR[1], a + 2, .3, .7)

# --- Khalid: hooves build under the map, then the cavalry charge
s = S['khalid']; a = s['a']
cut = L('khalid', 1) + 3.2
bed(GALLOP_FAR, L('khalid', 0) + .5, cut + .5, .5, env=lambda t: np.clip(.25 + t / 8, 0, 1))
bed(GALLOP, cut, s['b'] + .5, .7, fade=.6)
bed(GALLOP, cut + .4, s['b'] + .5, .5, fade=.6)
put(NEIGH[1], cut + .6, .6, -.3); put(NEIGH[0], cut + 3.5, .5, .4)
put(SHOUTS[1], cut + 1.2, .55, .2); put(SHOUTS[2], cut + 2.4, .5, -.4)
bed(CROWD, L('khalid', 2), s['b'] + 1, .5, fade=2)

# --- chaos: everything at once; it softens when the light of Paradise rises
s = S['chaos']; a = s['a']
para = L('chaos', 2) - .4
soft = lambda t, a=a: np.where(a + t < para, 1, np.clip(1 - (a + t - para) / 3 * .75, .25, 1))
bed(CROWD, a - .5, s['b'], .6, fade=.8, env=soft)
bed(GALLOP_FAR, a, para + 1, .3)
scatter(SWORDS, a + .2, para, .22, .5)
scatter(SWORDS_FAR, para, s['b'] - 1, .8, .2)
scatter(SHOUTS, a + .3, para, 1.0, .5)
scatter(ARROW, a + .2, L('chaos', 1) + 4, .45, .35)
put(NEIGH[0], a + 3, .5, .6); put(NEIGH[1], a + 9, .45, -.5)
put(SHOUTS[0], L('chaos', 0) + .3, .8, 0)            # the false cry spreads

# --- regroup: arrows still falling as they climb, battle far below
s = S['regroup']; a = s['a']
bed(CROWD_FAR, a - .5, s['b'], .25, env=lambda t: np.clip(1 - t / 25, .3, 1))
scatter(ARROW, L('regroup', 0), L('regroup', 2), 1.1, .35)
scatter(SWORDS_FAR, a, L('regroup', 2), 1.4, .2)

# --- Abu Sufyan: the army below, then it leaves
s = S['abusufyan']
bed(CROWD_FAR, s['a'], s['b'], .2, env=lambda t, d=L('abusufyan', 4) - s['a']: np.where(t < d, 1, np.clip(1 - (t - d) / 6, 0, 1)))
bed(MARCH, L('abusufyan', 4), s['b'], .2, fade=2)

# --- part 1 extras: Makkah gathers an army, the believers march out
s = S['makkah']
bed(CROWD_FAR, s['a'], s['b'] + .5, .18, fade=2, env=lambda t, d=L('makkah', 1) - s['a']: np.clip(.4 + (t - d) / 4 * .6, .4, 1))
bed(MARCH, L('makkah', 1), s['b'] + .5, .12, fade=2)
s = S['split']
bed(MARCH, s['a'], s['b'], .22, fade=2)
put(NEIGH_FAR[0], s['a'] + 6, .2, -.5)

peak = np.abs(out).max()
out *= min(1, .89 / peak) if peak else 1
pcm = (out.clip(-1, 1) * 32767).astype('<i2')
import wave
with wave.open(os.path.join(ROOT, 'sfx.wav'), 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('sfx.wav', round(N / SR, 1), 's, peak before norm', round(float(peak), 2))
