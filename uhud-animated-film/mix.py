"""Mix narration with a soft ambience bed (wind + low drone) and, if sfx.wav exists, the battle sound
effects ducked under the voice. No music."""
import json, os, subprocess
import imageio_ffmpeg

ROOT = os.path.dirname(os.path.abspath(__file__))
FF = imageio_ffmpeg.get_ffmpeg_exe()
tl = json.loads(open(os.path.join(ROOT, 'timeline.js'), encoding='utf-8').read().split('=', 1)[1].rstrip().rstrip(';'))
S = {s['id']: s for s in tl['scenes']}
D = tl['duration']
SFX = os.path.join(ROOT, 'sfx.wav')
has_sfx = os.path.exists(SFX)


def window(a, b, f=2.0):
    return f'clip((t-{a:.2f})/{f},0,1)*clip(({b:.2f}-t)/{f},0,1)'


battle = '+'.join([window(S['battle']['a'], S['battle']['b']), window(S['khalid']['a'] + 9, S['chaos']['b'])])
night = '+'.join([window(S[k]['a'], S[k]['b'], 3) for k in ('title', 'madinah', 'martyrs')])
ST = 'aformat=channel_layouts=stereo'

filt = (
    f"anoisesrc=d={D}:c=brown:r=44100:a=0.5,lowpass=f=520,highpass=f=70,"
    f"volume='(0.30-0.15*({night}))*(0.6+0.4*sin(2*PI*0.07*t))':eval=frame,{ST}[wind];"
    f"aevalsrc='0.5*sin(2*PI*55*t)+0.3*sin(2*PI*82.41*t)+0.2*sin(2*PI*110*t)':d={D}:s=44100,"
    f"volume='0.045*(0.7+0.3*sin(2*PI*0.03*t))':eval=frame,{ST}[drone];"
    f"anoisesrc=d={D}:c=brown:r=44100:a=0.8,lowpass=f=160,tremolo=f=3.5:d=0.4,"
    f"volume='{0.25 if has_sfx else 0.55}*({battle})':eval=frame,{ST}[rumble];"
)
if has_sfx:
    # the voice drives a compressor on the effects so speech always stays on top
    filt += (
        f"[0:a]aresample=44100,{ST},asplit=2[nar][key];"
        f"[1:a]aresample=44100,{ST},volume=0.8[fx];"
        f"[fx][key]sidechaincompress=threshold=0.02:ratio=6:attack=15:release=450[fxd];"
        f"[nar][wind][drone][rumble][fxd]amix=inputs=5:normalize=0:duration=first,"
    )
    inputs = ['-i', os.path.join(ROOT, 'narration.wav'), '-i', SFX]
else:
    filt += f"[0:a]aresample=44100,{ST}[nar];[nar][wind][drone][rumble]amix=inputs=4:normalize=0:duration=first,"
    inputs = ['-i', os.path.join(ROOT, 'narration.wav')]
filt += "alimiter=limit=0.95,loudnorm=I=-16:TP=-1.5:LRA=11[out]"

subprocess.run([FF, '-y', '-loglevel', 'error', *inputs, '-filter_complex', filt,
                '-map', '[out]', '-ac', '2', '-ar', '44100', os.path.join(ROOT, 'mix.wav')], check=True)
print('mix.wav ok', D, '(with sfx)' if has_sfx else '')
