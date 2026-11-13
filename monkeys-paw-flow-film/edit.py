"""Assemble the film from clips/NN_v*.mp4 (newest take per shot) -> maymun_panjasi.mp4

python edit.py              # with the clips' own (Flow) sound
python edit.py --audio mix.wav   # replace the sound with a finished mix of the same length
"""
import os, re, sys, json, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
# ffmpeg/ffprobe from PATH unless FFMPEG / FFPROBE point somewhere else
FF, FP = os.environ.get('FFMPEG', 'ffmpeg'), os.environ.get('FFPROBE', 'ffprobe')
# drawtext fonts (Bookman Old Style on Windows); override with TITLE_FONT / TITLE_FONT_BOLD
FONT = os.environ.get('TITLE_FONT', 'C\\:/Windows/Fonts/BOOKOS.TTF')
FONTB = os.environ.get('TITLE_FONT_BOLD', 'C\\:/Windows/Fonts/BOOKOSB.TTF')
ACT_BREAKS = {10, 16, 21}           # fade to black after these shots
FADE = 0.6

def takes():
    best = {}
    for f in os.listdir(os.path.join(HERE, 'clips')):
        m = re.fullmatch(r'(\d\d)_v(\d+)\.mp4', f)
        if m:
            n, v = int(m[1]), int(m[2])
            if v > best.get(n, (0, ''))[0]:
                best[n] = (v, f)
    return [(n, os.path.join(HERE, 'clips', best[n][1])) for n in sorted(best)]

def dur(p):
    return float(subprocess.run([FP, '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p], capture_output=True, text=True).stdout)

def main():
    audio = sys.argv[sys.argv.index('--audio') + 1] if '--audio' in sys.argv else None
    shots = takes()
    args, filt, cat, t, timeline = [], [], [], 0.0, []
    last = shots[-1][0]
    for i, (n, p) in enumerate(shots):
        d = dur(p)
        args += ['-i', p]
        vin = FADE if (i == 0 or shots[i - 1][0] in ACT_BREAKS) else 0
        vout = FADE if n in ACT_BREAKS else (2.0 if n == last else 0)
        if i == 0: vin = 1.5
        v = f'[{i}:v]fps=24,scale=1280:720,setsar=1,format=yuv420p'
        if vin: v += f',fade=t=in:st=0:d={vin}'
        if vout: v += f',fade=t=out:st={d - vout:.3f}:d={vout}'
        a = f'[{i}:a]aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d={max(vin, 0.02)},afade=t=out:st={d - max(vout, 0.04):.3f}:d={max(vout, 0.04)}'
        filt += [v + f'[v{i}]', a + f'[a{i}]']
        cat.append(f'[v{i}][a{i}]')
        timeline.append({'shot': n, 'file': os.path.basename(p), 'start': round(t, 3), 'dur': round(d, 3)})
        t += d
    total = t
    filt.append(''.join(cat) + f'concat=n={len(shots)}:v=1:a=1[cv][ca]')
    # titles: credit over the opening shot, film title over the last one
    credit = "W. W. Jacobs hikoyasi asosida"
    title = "MAYMUN PANJASI"
    t0 = timeline[0]['dur']
    tl = timeline[-1]['start']
    alpha = lambda a, b: f"if(lt(t,{a}),0,if(lt(t,{a}+1),t-{a},if(lt(t,{b}-1),1,if(lt(t,{b}),{b}-t,0))))"
    filt.append(
        f"[cv]drawtext=fontfile='{FONT}':text='{credit}':fontsize=30:fontcolor=white:x=(w-tw)/2:y=h*0.80:alpha='{alpha(1.8, t0 - 0.5)}',"
        f"drawtext=fontfile='{FONTB}':text='{title}':fontsize=78:fontcolor=white:x=(w-tw)/2:y=(h-th)/2:alpha='{alpha(tl + 2.0, total - 0.3)}'[vout]")
    if audio:
        args += ['-i', audio]
        amap = f'{len(shots)}:a'
    else:
        filt.append('[ca]loudnorm=I=-16:TP=-1.5:LRA=11[aout]')
        amap = '[aout]'
    out = os.path.join(HERE, 'maymun_panjasi.mp4')
    cmd = [FF, '-y', '-loglevel', 'error', *args, '-filter_complex', ';'.join(filt), '-map', '[vout]', '-map', amap,
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
           '-movflags', '+faststart', '-shortest', out]
    subprocess.run(cmd, check=True)
    json.dump(timeline, open(os.path.join(HERE, 'timeline.json'), 'w'), indent=1)
    print(f'{out}  {total:.1f}s  {len(shots)} shots')

if __name__ == '__main__':
    main()
