"""Render every shot that has no clip yet, one at a time, through flowkit (each clip is submitted once).
python batch.py            # all missing shots
python batch.py 2 3 5      # only these
"""
import os, sys, json, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
# flowkit.cjs: the author's small Node driver for Google Flow (labs.google/flow); not part of this repo
KIT = os.environ.get('FLOWKIT', 'flowkit.cjs')
LOG = os.path.join(HERE, 'batch.log')

def log(msg):
    line = time.strftime('%H:%M:%S ') + msg
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def main():
    only = {int(a) for a in sys.argv[1:]}
    shots = sorted(f for f in os.listdir(os.path.join(HERE, 'shots')) if f.endswith('.json'))
    fails = 0
    for f in shots:
        n = int(f[:2])
        out = os.path.join(HERE, 'clips', f'{n:02d}_v1.mp4')
        if (only and n not in only) or os.path.exists(out):
            continue
        log(f'shot {n:02d} start')
        r = subprocess.run(['node', KIT, 'run', os.path.join(HERE, 'shots', f), out], capture_output=True, text=True, encoding='utf-8', errors='replace')
        tail = (r.stdout + r.stderr).strip().splitlines()
        ok = r.returncode == 0 and os.path.exists(out)
        log(f'shot {n:02d} {"OK" if ok else "FAIL"}: ' + ' | '.join(tail[-3:]))
        fails = 0 if ok else fails + 1
        if fails >= 2:
            log('two failures in a row: stopping')
            sys.exit(1)
    log('batch done')

if __name__ == '__main__':
    main()
