"""Epic voxel castle build - first-person story timelapse (sound effects only).

Renders a blocky sandbox world with OpenGL (moderngl, headless), pipes the
frames to ffmpeg and muxes a synthesized sound-effect track.

    python castle_video.py                        # full video
    python castle_video.py --preview 10,90,200    # PNG stills
    python castle_video.py --start 40 --end 60    # partial clip
"""
import argparse
import bisect
import math
import os
import subprocess
import time
import wave
from collections import namedtuple

import imageio_ffmpeg
import moderngl
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30
INF = 1.0e9
INTRO_T = 1.0e7
TWO_PI = 2 * math.pi


def smoothstep(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def norm(v):
    v = np.asarray(v, float)
    return v / max(np.linalg.norm(v), 1e-9)


# --------------------------------------------------------------------------
# Textures (16x16 procedural pixel art)
# --------------------------------------------------------------------------
TEX = {}
TEX_LIST = []


def tex(name, rgb, alpha=None):
    rgb = np.clip(rgb, 0, 255)
    if alpha is None:
        alpha = np.full((16, 16), 255.0)
    TEX[name] = len(TEX_LIST)
    TEX_LIST.append(np.dstack([rgb, alpha]).astype(np.uint8))


def make_textures():
    rng = np.random.default_rng(11)
    yy, xx = np.mgrid[0:16, 0:16]

    def noisy(base, var):
        return np.array(base, float)[None, None, :] * rng.uniform(1 - var, 1 + var, (16, 16, 1))

    g = noisy((92, 158, 52), 0.13)
    g[rng.random((16, 16)) < 0.12] *= 0.82
    tex('grass_top', g)
    d = noisy((134, 96, 67), 0.12)
    d[rng.random((16, 16)) < 0.12] = (100, 70, 48)
    d[rng.random((16, 16)) < 0.06] = (156, 116, 86)
    tex('dirt', d)
    gs = d.copy()
    depth = 3 + rng.integers(0, 3, 16)
    gside = noisy((88, 150, 50), 0.12)
    for x in range(16):
        gs[:depth[x], x] = gside[:depth[x], x]
    tex('grass_side', gs)
    s = noisy((128, 128, 128), 0.08)
    s[rng.random((16, 16)) < 0.10] *= 0.85
    tex('stone', s)

    def voronoi(npts):
        pts = rng.uniform(0, 16, (npts, 2))
        ds = []
        for p in pts:
            dx = np.abs(xx + 0.5 - p[0]); dx = np.minimum(dx, 16 - dx)
            dy = np.abs(yy + 0.5 - p[1]); dy = np.minimum(dy, 16 - dy)
            ds.append(np.hypot(dx, dy))
        ds = np.stack(ds)
        srt = np.sort(ds, 0)
        return np.argmin(ds, 0), (srt[1] - srt[0]) < 1.0

    idx, edge = voronoi(9)
    c = rng.uniform(100, 150, 9)[idx][:, :, None] * rng.uniform(0.9, 1.1, (16, 16, 1)) * np.ones(3)
    c[edge] = 72
    tex('cobblestone', c)

    def bricks(base, mortar):
        b = noisy(base, 0.07)
        for y in range(16):
            off = 0 if (y // 4) % 2 == 0 else 4
            for x in range(16):
                if y % 4 == 3 or (x + off) % 8 == 7:
                    b[y, x] = mortar
                elif y % 4 == 0 or (x + off) % 8 == 0:
                    b[y, x] *= 1.12
        return b

    sb = bricks((122, 122, 122), (86, 86, 86))
    tex('stone_bricks', sb)
    moss = sb.copy()
    mm = (np.kron(rng.random((4, 4)), np.ones((4, 4))) + rng.random((16, 16)) * 0.5) > 0.95
    moss[mm] = noisy((78, 112, 52), 0.15)[mm]
    tex('mossy_stone_bricks', moss)
    sm = noisy((168, 168, 168), 0.04)
    sm[(xx == 0) | (xx == 15) | (yy == 0) | (yy == 15)] = (132, 132, 132)
    tex('smooth_stone', sm)

    def planks(base):
        p = noisy(base, 0.05)
        for r in range(4):
            p[r * 4:(r + 1) * 4] *= rng.uniform(0.9, 1.08)
            p[r * 4 + 3] *= 0.72
            p[r * 4:r * 4 + 3, rng.integers(0, 16)] *= 0.74
        p[rng.random((16, 16)) < 0.1] *= 0.88
        return p

    tex('oak_planks', planks((162, 130, 78)))
    tex('spruce_planks', planks((112, 82, 48)))
    tex('dark_oak_planks', planks((70, 46, 22)))

    def log_side(base):
        return np.array(base, float)[None, None, :] * rng.uniform(0.75, 1.1, (1, 16, 1)) * rng.uniform(0.92, 1.08, (16, 16, 1))

    def log_top(bark, inner):
        r = np.hypot(xx - 7.5, yy - 7.5)
        p = noisy(inner, 0.05)
        p[np.floor(r) % 2 == 0] *= 0.86
        p[(xx == 0) | (xx == 15) | (yy == 0) | (yy == 15)] = bark
        return p

    tex('oak_log', log_side((104, 82, 50)))
    tex('oak_log_top', log_top((90, 70, 42), (176, 143, 90)))
    tex('spruce_log', log_side((62, 44, 26)))
    tex('spruce_log_top', log_top((55, 40, 22), (120, 90, 55)))
    tex('leaves', noisy((58, 128, 38), 0.25), np.where(rng.random((16, 16)) < 0.2, 0.0, 255.0))

    gl = np.ones((16, 16, 3)) * np.array([215, 232, 240.0])
    ga = np.full((16, 16), 40.0)
    border = (xx == 0) | (xx == 15) | (yy == 0) | (yy == 15)
    ga[border] = 220
    gl[border] = (190, 210, 220)
    for (x, y) in [(3, 5), (4, 4), (5, 3), (9, 11), (10, 10), (11, 9), (12, 8)]:
        ga[y, x] = 170
        gl[y, x] = (255, 255, 255)
    tex('glass', gl, ga)
    w = noisy((44, 96, 210), 0.1)
    w[(yy + xx // 4) % 6 == 0] *= 1.25
    tex('water', w, np.full((16, 16), 178.0))

    def tiles(base):
        p = noisy(base, 0.08)
        for r in range(4):
            off = 0 if r % 2 == 0 else 4
            p[r * 4] *= 1.12
            p[r * 4 + 3] *= 0.62
            for x in range(16):
                if (x + off) % 8 == 0:
                    p[r * 4:r * 4 + 3, x] *= 0.75
        return p

    tex('roof_red', tiles((158, 48, 38)))
    tex('roof_blue', tiles((52, 72, 128)))
    pal = np.array([(132, 126, 122), (100, 96, 94), (152, 142, 136), (84, 80, 80)], float)
    tex('gravel', pal[rng.integers(0, 4, (16, 16))])
    gd = noisy((248, 208, 64), 0.06)
    gd[(xx == 0) | (yy == 0)] = (255, 244, 150)
    gd[(xx == 15) | (yy == 15)] = (196, 146, 30)
    tex('gold', gd)
    tex('wool_red', noisy((168, 38, 38), 0.07))
    tex('wool_blue', noisy((44, 62, 150), 0.07))
    bn = noisy((160, 30, 32), 0.05)
    gold = np.array([240, 196, 60.0])
    bn[(xx == 0) | (xx == 15) | (yy == 0)] = gold
    dia = np.abs(xx - 7.5) + np.abs(yy - 7.0)
    bn[dia < 4.5] = gold
    bn[dia < 2.2] = (160, 30, 32)
    ba = np.full((16, 16), 255.0)
    ba[(yy >= 13) & (np.abs(xx - 7.5) < (yy - 12) * 2.6)] = 0
    tex('banner', bn, ba)
    fl = noisy((176, 34, 34), 0.05)
    fl[(yy >= 6) & (yy <= 9)] = (240, 200, 60)
    tex('flag', fl)
    tc = np.zeros((16, 16, 3))
    tc[:] = (112, 82, 42)
    tc[0:2] = (255, 248, 200)
    tc[2:4] = (255, 196, 70)
    tex('torch', tc)
    tex('torch_top', np.ones((16, 16, 3)) * np.array([255, 240, 180.0]))
    gs2 = noisy((226, 184, 96), 0.2)
    gs2[rng.random((16, 16)) < 0.3] = (255, 238, 170)
    tex('glowstone', gs2)
    dr = planks((70, 46, 22))
    dr[:, 0] = dr[:, 15] = (40, 26, 12)
    dr[2:6, 4:12] = (34, 30, 28)
    dr[9, 11:13] = (180, 180, 180)
    tex('door', dr)

    def ore(spec):
        o = noisy((128, 128, 128), 0.08)
        m = np.zeros((16, 16), bool)
        for _ in range(5):
            cx, cy = rng.integers(1, 14, 2)
            for dx, dy in [(0, 0), (1, 0), (0, 1), (1, 1)]:
                if rng.random() < 0.8:
                    m[cy + dy, cx + dx] = True
        o[m] = noisy(spec, 0.12)[m]
        return o

    tex('coal_ore', ore((38, 38, 38)))
    tex('iron_ore', ore((216, 172, 140)))
    tex('diamond_ore', ore((90, 236, 228)))

    bs = planks((162, 130, 78))
    cols = [(150, 40, 40), (40, 70, 150), (50, 120, 60), (170, 130, 50), (110, 60, 120), (60, 60, 60)]
    for r0 in (2, 9):
        x = 1
        while x < 15:
            wdt = int(rng.integers(1, 3))
            col = np.array(cols[rng.integers(0, len(cols))], float)
            top = r0 + int(rng.integers(0, 2))
            bs[top:r0 + 5, x:x + wdt] = col * rng.uniform(0.85, 1.1)
            x += wdt
    tex('bookshelf', bs)
    ch = noisy((150, 104, 44), 0.06)
    ch[(xx == 0) | (xx == 15) | (yy == 0) | (yy == 15)] = (80, 52, 20)
    ch[5] = (80, 52, 20)
    tex('chest_side', ch.copy())
    ch[6:9, 7:9] = (190, 190, 190)
    tex('chest_front', ch)
    tex('chest_top', noisy((150, 104, 44), 0.05))
    pl = noisy((232, 228, 220), 0.03)
    pl[:, [3, 8, 12]] *= 0.9
    tex('pillar', pl)
    ct = np.ones((16, 16, 3)) * np.array([245, 240, 235.0])
    for (x, y) in [(3, 4), (8, 3), (12, 6), (5, 10), (10, 11), (7, 7)]:
        ct[y, x] = (200, 30, 40)
    tex('cake_top', ct)
    cs = np.ones((16, 16, 3)) * np.array([236, 214, 170.0])
    cs[0:3] = (245, 240, 235)
    cs[8:10] = (200, 40, 50)
    tex('cake_side', cs)
    fr = np.zeros((16, 16, 3))
    fa = np.zeros((16, 16))
    for x in range(16):
        h = int(rng.integers(5, 15))
        for y in range(16 - h, 16):
            u = (16 - y) / h
            fr[y, x] = lerp(np.array([255, 240, 120.0]), np.array([230, 70, 20.0]), u)
            fa[y, x] = 255
    tex('fire', fr, fa)

    skin = np.array([206, 150, 112.0])
    hair = np.array([72, 44, 24.0])
    tex('skin', noisy(skin, 0.03))
    tex('sleeve', noisy((214, 108, 38), 0.06))

    def tint(img, amt=0.55):
        return img * (1 - amt) + np.array([255, 40, 40.0]) * amt

    zsk = np.array([96, 146, 84.0])
    zf = noisy(zsk, 0.06)
    zf[8:10, 3:5] = (20, 30, 20)
    zf[8:10, 11:13] = (20, 30, 20)
    zf[12, 5:11] = (40, 60, 40)
    zparts = {'zface': zf, 'zskin': noisy(zsk, 0.06), 'zhair': noisy((64, 100, 56), 0.06),
              'zshirt': noisy((40, 150, 156), 0.06), 'zpants': noisy((72, 64, 150), 0.06)}
    for k, v in zparts.items():
        tex(k, v)
        tex(k + '_h', tint(v))

    def sprite(pix):
        rgb = np.zeros((16, 16, 3))
        a = np.zeros((16, 16))
        for (x, y), cc in pix.items():
            if 0 <= x < 16 and 0 <= y < 16:
                rgb[y, x] = cc
                a[y, x] = 255
        return rgb, a

    brown, dark, steel, light = (110, 76, 34), (55, 55, 60), (205, 210, 215), (245, 245, 250)
    p = {}
    for i in range(10):
        p[(5 + i, 10 - i)] = light
        p[(6 + i, 10 - i)] = steel
    for q in [(3, 9), (4, 10), (5, 11), (6, 12)]:
        p[q] = dark
    for q in [(1, 14), (2, 13), (3, 12)]:
        p[q] = brown
    p[(0, 15)] = dark
    tex('sword', *sprite(p))

    def handle(n):
        return {(2 + i, 13 - i): brown for i in range(n)}

    p = handle(9)
    for q in [(5, 2), (6, 1), (7, 1), (8, 1), (9, 1), (10, 2), (11, 2), (12, 3), (13, 4), (13, 5), (14, 6), (14, 7), (14, 8), (14, 9)]:
        p[q] = steel
    for q in [(6, 2), (7, 2), (8, 2), (9, 2), (12, 4), (13, 6), (13, 7)]:
        p[q] = (150, 155, 160)
    tex('pickaxe', *sprite(p))
    p = handle(9)
    for y in range(1, 7):
        for x in range(9, 14 if y < 5 else 13):
            p[(x, y)] = steel if x > 9 else (150, 155, 160)
    tex('axe', *sprite(p))
    p = handle(8)
    for y in range(1, 8):
        for x in range(9, 16):
            if math.hypot(x - 11.5, y - 4) < 2.9:
                p[(x, y)] = steel
    tex('shovel', *sprite(p))
    p = {}
    for y in range(4, 15):
        w2 = 5 - (y - 4) * 0.25
        for x in range(int(7.5 - w2), int(8.5 + w2)):
            p[(x, y)] = (170, 172, 178) if y > 5 else (215, 218, 222)
    for x in range(5, 11):
        p[(x, 5)] = (60, 110, 220)
    for q in [(4, 3), (5, 2), (6, 1), (7, 1), (8, 1), (9, 1), (10, 2), (11, 3)]:
        p[q] = dark
    tex('bucket', *sprite(p))
    tex('rain', np.ones((16, 16, 3)) * np.array([170, 190, 230.0]), np.full((16, 16), 130.0))
    tex('smoke', noisy((205, 205, 205), 0.06))
    for name, col in [('spark_red', (255, 90, 80)), ('spark_gold', (255, 214, 90)),
                      ('spark_blue', (110, 170, 255)), ('spark_green', (120, 255, 140)),
                      ('spark_pink', (255, 120, 230)), ('spark_white', (255, 255, 255))]:
        tex(name, np.ones((16, 16, 3)) * np.array(col, float))
    tex('flower_red', noisy((214, 36, 40), 0.1))
    tex('flower_yellow', noisy((244, 218, 50), 0.1))


F_EMIT, F_BLEND, F_CUT, F_GLOW, F_WATER, F_WUV = 1, 2, 4, 8, 16, 32
TYPES = {}
TYPE_TEX = []
TYPE_FLAGS = []


def deftype(name, top, bottom=None, side=None, front=None, flags=0):
    bottom = bottom or top
    side = side or top
    front = front or side
    TYPES[name] = len(TYPE_TEX)
    TYPE_TEX.append([TEX[top], TEX[bottom], TEX[side], TEX[front]])
    TYPE_FLAGS.append(flags)


def make_types():
    deftype('grass', 'grass_top', 'dirt', 'grass_side')
    deftype('ground', 'grass_top', 'dirt', 'grass_side', flags=F_WUV)
    for n in ['dirt', 'stone', 'cobblestone', 'stone_bricks', 'mossy_stone_bricks', 'smooth_stone',
              'oak_planks', 'spruce_planks', 'dark_oak_planks', 'gravel', 'gold', 'roof_red',
              'roof_blue', 'wool_red', 'coal_ore', 'iron_ore', 'diamond_ore', 'pillar', 'skin']:
        deftype(n, n)
    deftype('carpet_red', 'wool_red')
    deftype('carpet_blue', 'wool_blue')
    deftype('oak_log', 'oak_log_top', 'oak_log_top', 'oak_log')
    deftype('spruce_log', 'spruce_log_top', 'spruce_log_top', 'spruce_log')
    deftype('leaves', 'leaves', flags=F_CUT)
    deftype('glass', 'glass', flags=F_BLEND)
    deftype('glass_lit', 'glass', flags=F_BLEND | F_GLOW)
    deftype('water', 'water', flags=F_BLEND | F_WATER)
    deftype('banner', 'wool_red', 'wool_red', 'banner', flags=F_CUT)
    deftype('flag', 'flag')
    deftype('torch', 'torch_top', 'torch', 'torch', flags=F_EMIT)
    deftype('glowstone', 'glowstone', flags=F_EMIT)
    deftype('fire', 'fire', flags=F_EMIT | F_CUT)
    deftype('fence', 'oak_planks')
    deftype('door', 'dark_oak_planks', 'dark_oak_planks', 'door')
    deftype('bookshelf', 'oak_planks', 'oak_planks', 'bookshelf')
    deftype('chest', 'chest_top', 'chest_top', 'chest_side', 'chest_front')
    deftype('cake', 'cake_top', 'cake_side', 'cake_side')
    deftype('sleeve', 'sleeve', 'skin', 'sleeve')
    for h in ('', '_h'):
        deftype('zhead' + h, 'zhair' + h, 'zskin' + h, 'zskin' + h, 'zface' + h)
        deftype('zbody' + h, 'zshirt' + h)
        deftype('zarm' + h, 'zskin' + h)
        deftype('zleg' + h, 'zpants' + h)
    for n in ['sword', 'pickaxe', 'axe', 'shovel', 'bucket']:
        deftype(n, n, flags=F_CUT)
    deftype('rain', 'rain', flags=F_BLEND | F_EMIT)
    deftype('smoke', 'smoke', flags=F_EMIT)
    for n in ['spark_red', 'spark_gold', 'spark_blue', 'spark_green', 'spark_pink', 'spark_white']:
        deftype(n, n, flags=F_EMIT)
    deftype('flower_red', 'flower_red')
    deftype('flower_yellow', 'flower_yellow')


BLEND_TYPES = {'glass', 'glass_lit', 'water'}
NONSOLID = {'torch', 'glowstone', 'fence', 'flower_red', 'flower_yellow', 'banner', 'flag', 'water',
            'glass', 'glass_lit', 'leaves', 'gravel', 'fire', 'carpet_red', 'carpet_blue', 'cake'}
ITEMS = {'sword', 'pickaxe', 'axe', 'shovel', 'bucket'}

MATERIAL = {}
for _n in ['stone', 'cobblestone', 'stone_bricks', 'mossy_stone_bricks', 'smooth_stone', 'coal_ore',
           'iron_ore', 'diamond_ore', 'pillar', 'roof_red', 'roof_blue']:
    MATERIAL[_n] = 'stone'
for _n in ['oak_planks', 'spruce_planks', 'dark_oak_planks', 'oak_log', 'spruce_log', 'door', 'fence',
           'bookshelf', 'chest', 'torch']:
    MATERIAL[_n] = 'wood'
for _n in ['grass', 'dirt', 'leaves', 'flower_red', 'flower_yellow']:
    MATERIAL[_n] = 'grass'
for _n in ['wool_red', 'carpet_red', 'carpet_blue', 'banner', 'flag', 'cake']:
    MATERIAL[_n] = 'wool'
MATERIAL.update({'gravel': 'gravel', 'glass': 'glass', 'glass_lit': 'glass', 'water': 'water',
                 'gold': 'metal', 'glowstone': 'glass', 'fire': 'wool'})


def tool_for(ty):
    m = MATERIAL.get(ty, 'stone')
    if m == 'wood':
        return 'axe'
    if m in ('grass', 'gravel'):
        return 'leaves' if ty == 'leaves' else 'shovel'
    return 'pickaxe'


def held_for(ty):
    return 'bucket' if ty == 'water' else ty


# --------------------------------------------------------------------------
# World parts
# --------------------------------------------------------------------------
Act = namedtuple('Act', 'kind cell type c s light')


def P(x, y, z, t, light=None):
    return Act(0, (x, y, z), t, (x + .5, y + .5, z + .5), (1, 1, 1), light)


def SH(t, c, s, cell=None, light=None):
    return Act(0, cell, t, tuple(float(v) for v in c), tuple(s), light)


def RM(x, y, z):
    return Act(1, (x, y, z), None, (x + .5, y + .5, z + .5), None, None)


def D(d):
    return [P(x, y, z, t) for (x, y, z), t in d.items()]


def TORCH(x, y, z, dx=0.0, dz=0.0):
    return SH('torch', (x + .5 + dx, y + 0.31, z + .5 + dz), (0.14, 0.62, 0.14), light=(x, y, z, 14))


def angdiff(a, b):
    return (a - b + math.pi) % TWO_PI - math.pi


def wall_type(rng, y):
    if y <= 2:
        return 'cobblestone'
    if y == 11:
        return 'smooth_stone'
    return 'mossy_stone_bricks' if rng.random() < 0.14 else 'stone_bricks'


def tree_cells(x, z, h, rng, y0=1):
    d = {}
    for y in range(y0, y0 + h):
        d[(x, y, z)] = 'oak_log'
    top = y0 + h - 1
    for y in range(top - 2, top + 2):
        r = 2 if y < top else 1
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if dx == 0 and dz == 0 and y <= top:
                    continue
                if abs(dx) == r and abs(dz) == r and (y >= top or rng.random() < 0.5):
                    continue
                d.setdefault((x + dx, y, z + dz), 'leaves')
    return d


def round_tower(cx, cz, R, H, Hr, roof_type, rng, win_rows, y_start=3):
    found, body, roof = {}, {}, {}
    win_angles = [k * math.pi / 4 for k in range(8)]
    rr = R + 2
    for x in range(cx - rr, cx + rr + 1):
        for z in range(cz - rr, cz + rr + 1):
            dx, dz = x - cx, z - cz
            d = math.hypot(dx, dz)
            ang = math.atan2(dz, dx)
            if d <= R + 0.5:
                found[(x, 1, z)] = found[(x, 2, z)] = 'cobblestone'
                outer = d > R - 0.5
                shell = d > R - 1.3
                win = shell and min(abs(angdiff(ang, a)) for a in win_angles) < 0.62 / R
                for y in range(y_start, H + 1):
                    if y == H:
                        body[(x, y, z)] = 'stone_bricks'
                    elif shell:
                        if win and y < H - 4 and any(y in (r, r + 1) for r in win_rows):
                            if outer:
                                body[(x, y, z)] = 'glass_lit'
                            continue
                        body[(x, y, z)] = 'smooth_stone' if y == H - 4 else wall_type(rng, y)
            elif d <= R + 1.5:
                seg = int(math.floor((ang + math.pi) * (R + 1)))
                for y in (H - 1, H):
                    body[(x, y, z)] = 'stone_bricks'
                if seg % 2 == 0:
                    body[(x, H - 2, z)] = 'stone_bricks'
                    body[(x, H + 1, z)] = 'stone_bricks'
    torches = []
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        torches.append((cx + int(round((R - 1) * math.cos(a))), H + 1, cz + int(round((R - 1) * math.sin(a)))))
    base = H + 1
    for k in range(Hr + 1):
        r = (R + 0.7) * (1 - k / Hr)
        for x in range(cx - rr, cx + rr + 1):
            for z in range(cz - rr, cz + rr + 1):
                d = math.hypot(x - cx, z - cz)
                if r < 0.75:
                    if x == cx and z == cz:
                        roof[(x, base + k, z)] = roof_type
                elif r - 1.45 < d <= r:
                    roof[(x, base + k, z)] = roof_type
    tip = (cx, base + Hr + 1, cz)
    roof[tip] = 'gold'
    return found, body, roof, tip, torches


def square_tower(x0, x1, z0, z1, H, roof_type, rng, front_z):
    found, body, roof = {}, {}, {}
    xc, zc = (x0 + x1) // 2, (z0 + z1) // 2
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            edge = x in (x0, x1) or z in (z0, z1)
            corner = x in (x0, x1) and z in (z0, z1)
            found[(x, 1, z)] = found[(x, 2, z)] = 'cobblestone'
            for y in range(3, H + 1):
                if y == H or edge:
                    body[(x, y, z)] = 'smooth_stone' if corner else wall_type(rng, y)
            if edge and (x + z) % 2 == 0:
                body[(x, H + 1, z)] = 'stone_bricks'
    for y in (8, 9, 13, 14):
        body[(xc, y, front_z)] = 'glass_lit'
        body[(x0 if x0 < 0 else x1, y, zc)] = 'glass_lit'
    k, y = 0, H + 1
    while True:
        xa, xb, za, zb = x0 + 1 + k, x1 - 1 - k, z0 + 1 + k, z1 - 1 - k
        if xa > xb or za > zb:
            break
        for yy in (y, y + 1):
            for x in range(xa, xb + 1):
                for z in range(za, zb + 1):
                    if x in (xa, xb) or z in (za, zb) or (xb - xa <= 1):
                        roof[(x, yy, z)] = roof_type
        y += 2
        k += 1
    tip = (xc, y, zc)
    roof[tip] = 'gold'
    return found, body, roof, tip


QX0, QX1, QZ0, QZ1 = -71, -59, -7, 5          # quarry columns (inclusive)
DIAMONDS = [(-65, -9, -2), (-64, -9, -2), (-65, -9, -1)]
KEEP = (-14, 14, -20, 2)
MT = (0, -9)


def ground_boxes():
    holes = [(-40, 41, -40, 41), (QX0, QX1 + 1, QZ0, QZ1 + 1)]
    xs = sorted({-1500, 1500} | {h[0] for h in holes} | {h[1] for h in holes})
    zs = sorted({-1500, 1500} | {h[2] for h in holes} | {h[3] for h in holes})
    out = [SH('ground', (0.5, 0.5, 0.5), (65, 1, 65))]
    for i in range(len(xs) - 1):
        for j in range(len(zs) - 1):
            cx, cz = (xs[i] + xs[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2
            if any(h[0] <= cx < h[1] and h[2] <= cz < h[3] for h in holes):
                continue
            out.append(SH('ground', (cx, 0.5, cz), (xs[i + 1] - xs[i], 1, zs[j + 1] - zs[j])))
    return out


def gen_parts():
    rng = np.random.default_rng(42)
    W = {}
    init = ground_boxes()
    for x in range(-40, 41):
        for z in range(-40, 41):
            m = max(abs(x), abs(z))
            if 33 <= m <= 40:
                ring = 34 <= m <= 39
                init += [P(x, 0, z, 'grass'), P(x, -1, z, 'dirt'), P(x, -2, z, 'dirt'),
                         P(x, -3, z, 'gravel' if ring else 'stone')]
    for x in range(QX0, QX1 + 1):
        for z in range(QZ0, QZ1 + 1):
            for y in range(0, -12, -1):
                if y == 0:
                    t = 'grass'
                elif y >= -2:
                    t = 'dirt'
                else:
                    r = rng.random()
                    t = 'coal_ore' if r < 0.07 else ('iron_ore' if r < 0.10 else 'stone')
                if (x, y, z) in DIAMONDS:
                    t = 'diamond_ore'
                init.append(P(x, y, z, t))
    for i in range(16):
        a = rng.uniform(0, TWO_PI)
        r = rng.uniform(220, 360)
        hx, hz = r * math.cos(a), r * math.sin(a)
        L = int(rng.integers(10, 26))
        w0 = rng.uniform(60, 120)
        ox = oz = 0.0
        for k in range(L):
            f = math.sqrt(1 - k / L)
            ox += rng.uniform(-0.6, 0.6)
            oz += rng.uniform(-0.6, 0.6)
            init.append(SH('ground', (round(hx + ox), 1.5 + k, round(hz + oz)), (max(3, int(w0 * f)), 1, max(3, int(w0 * 0.75 * f)))))
    placed = 0
    while placed < 75:
        a = rng.uniform(0, TWO_PI)
        r = rng.uniform(47, 165)
        x, z = int(r * math.cos(a)), int(r * math.sin(a))
        if max(abs(x), abs(z)) < 46 or (abs(x) < 7 and z > 38):
            continue
        if QX0 - 5 <= x <= QX1 + 5 and QZ0 - 5 <= z <= QZ1 + 5:
            continue
        if -60 <= x <= -36 and -10 <= z <= 10:
            continue
        init += D(tree_cells(x, z, int(rng.integers(4, 7)), rng))
        placed += 1
    for _ in range(110):
        a = rng.uniform(0, TWO_PI)
        r = rng.uniform(44, 120)
        x, z = int(r * math.cos(a)), int(r * math.sin(a))
        if max(abs(x), abs(z)) < 42 or (abs(x) < 5 and z > 38):
            continue
        init.append(SH('flower_red' if rng.random() < 0.5 else 'flower_yellow', (x + .5, 1.2, z + .5), (0.3, 0.4, 0.3)))
    site = [(-10, 12), (8, 18), (16, -6), (-18, -12), (2, -14), (-22, 22), (22, 20), (-4, 24)]
    W['site_trees'] = []
    for (x, z) in site:
        cells = tree_cells(x, z, int(rng.integers(4, 6)), rng)
        init += D(cells)
        W['site_trees'].append(((x, z), list(cells.keys())))
    for (x, z) in [(12, 6), (-14, 2), (20, -20)]:
        cells = []
        for dx in range(2):
            for dz in range(2):
                for y in range(1, 1 + (2 if dx == dz == 0 else 1)):
                    init.append(P(x + dx, y, z + dz, 'cobblestone' if rng.random() < .5 else 'stone'))
                    cells.append((x + dx, y, z + dz))
        W['site_trees'].append(((x, z), cells))
    W['init'] = init

    moat = []
    water = []
    for x in range(-39, 40):
        for z in range(-39, 40):
            if 34 <= max(abs(x), abs(z)) <= 39:
                for y in (0, -1, -2):
                    moat.append(RM(x, y, z))
                water.append(SH('water', (x + .5, -0.15, z + .5), (1, 0.06, 1), cell=(x, -1, z)))
    W['moat'], W['water'] = moat, water
    W['quarry'] = [RM(x, y, z) for x in range(QX0 + 1, QX1) for z in range(QZ0 + 1, QZ1)
                   for y in range(0, -10, -1) if (x, y, z) not in DIAMONDS]
    W['diamonds'] = [RM(*c) for c in DIAMONDS]

    corner_towers = [(-30, -30), (30, -30), (30, 30), (-30, 30)]
    mid_towers = [(0, -30), (30, 0), (-30, 0)]
    tower_disks = [(cx, cz, 6) for cx, cz in corner_towers] + [(cx, cz, 4) for cx, cz in mid_towers]

    def in_gate(x, z):
        return abs(x) <= 11 and z >= 25

    def in_tower(x, z):
        return any(math.hypot(x - cx, z - cz) <= R + 0.5 for cx, cz, R in tower_disks)

    found_ring, found_keep = {}, {}
    walls = {}
    for x in range(-30, 31):
        for z in range(-30, 31):
            m = max(abs(x), abs(z))
            if not (28 <= m <= 30) or in_gate(x, z) or in_tower(x, z):
                continue
            coord = x if abs(z) >= 28 and abs(z) >= abs(x) else z
            found_ring[(x, 1, z)] = found_ring[(x, 2, z)] = 'cobblestone'
            for y in range(3, 13):
                if m == 30 and y in (6, 7) and coord % 6 == 3:
                    continue
                walls[(x, y, z)] = wall_type(rng, y)
            if m == 30 and coord % 2 == 0:
                walls[(x, 13, z)] = 'stone_bricks'
    W['walls'] = D(walls)

    tips, roofs, tower_torches = [], [], []
    W['towers'] = []
    for (cx, cz, R) in [(-30, -30, 6), (0, -30, 4), (30, -30, 6), (30, 0, 4), (30, 30, 6), (-30, 30, 6), (-30, 0, 4)]:
        H, Hr = (22, 12) if R == 6 else (17, 8)
        f, body, roof, tip, tt = round_tower(cx, cz, R, H, Hr, 'roof_blue', rng, [8, 15] if R == 6 else [8, 12])
        found_ring.update(f)
        W['towers'].append(((cx, cz), R, D(body)))
        roofs.append(((cx, cz), R, roof))
        tips.append(tip)
        tower_torches += tt

    W['gate'] = []
    for (x0, x1) in [(-11, -5), (5, 11)]:
        f, body, roof, tip = square_tower(x0, x1, 25, 33, 18, 'roof_red', rng, 33)
        found_ring.update(f)
        W['gate'].append((((x0 + x1) / 2, 29), D(body)))
        roofs.append((((x0 + x1) // 2, 29), 4, roof))
        tips.append(tip)
    gb = {}
    for x in range(-4, 5):
        for z in range(26, 34):
            for y in range(1, 15):
                if (abs(x) <= 2 and y <= 6) or (abs(x) <= 1 and y == 7):
                    continue
                if y <= 2:
                    found_ring[(x, y, z)] = 'cobblestone'
                else:
                    gb[(x, y, z)] = 'smooth_stone' if y in (8, 14) else wall_type(rng, y)
            if (z in (26, 33) and x % 2 == 0) or (x in (-4, 4) and z % 2 == 0):
                gb[(x, 15, z)] = 'stone_bricks'
    W['gate'].append(((0, 30), D(gb)))
    bridge = {}
    for z in range(33, 41):
        for x in range(-2, 3):
            bridge[(x, 0, z)] = 'spruce_log' if abs(x) == 2 else 'spruce_planks'
    for z in (36, 37):
        for x in (-2, 2):
            for y in (-2, -1):
                bridge[(x, y, z)] = 'spruce_log'
    br = D(bridge)
    for z in range(33, 41):
        for x in (-2, 2):
            br.append(SH('fence', (x + .5, 1.5, z + .5), (0.25, 1, 0.25)))
            br.append(SH('fence', (x + .5, 1.85, z + .5), (0.15, 0.15, 1.0)))
    road = []
    for z in range(41, 96):
        for x in range(-2, 3):
            if abs(x) == 2 and rng.random() < 0.35:
                continue
            road.append(SH('gravel', (x + .5, 1.03, z + .5), (1, 0.06, 1), cell=(x, 1, z)))
    W['bridge'], W['road'] = br, road

    X0, X1, Z0, Z1 = KEEP
    kcorners = [(X0, Z0), (X1, Z0), (X0, Z1), (X1, Z1)]

    def near_corner(x, z, r=2.6):
        return any(math.hypot(x - cx, z - cz) <= r for cx, cz in kcorners)

    keep = {}
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            outer = x in (X0, X1) or z in (Z0, Z1)
            inner = (not outer) and (x in (X0 + 1, X1 - 1) or z in (Z0 + 1, Z1 - 1))
            if not (outer or inner):
                keep[(x, 11, z)] = 'oak_planks'
                continue
            if near_corner(x, z):
                continue
            if z in (Z1, Z1 - 1) or z in (Z0, Z0 + 1):
                c, half = x, 10
            else:
                c, half = z + 9, 9
            is_win = abs(c) <= half and abs(c) % 4 in (1, 2)
            door = z in (Z1, Z1 - 1) and abs(x) <= 1
            for y in range(1, 19):
                if door and y <= 5:
                    if z == Z1:
                        keep[(x, y, z)] = 'door'
                    continue
                if y <= 2:
                    found_keep[(x, y, z)] = 'cobblestone'
                    continue
                if is_win and (7 <= y <= 9 or 13 <= y <= 15):
                    if outer:
                        keep[(x, y, z)] = 'glass_lit'
                    continue
                keep[(x, y, z)] = 'smooth_stone' if (y == 17 and outer) else wall_type(rng, y)
            if outer and (x + z) % 2 == 0:
                keep[(x, 19, z)] = 'stone_bricks'
    W['keep'] = D(keep)
    W['turrets'] = []
    for (cx, cz) in kcorners:
        f, body, roof, tip, tt = round_tower(cx, cz, 2, 24, 6, 'roof_red', rng, [14])
        found_keep.update(f)
        W['turrets'].append(((cx, cz), D(body)))
        roofs.append(((cx, cz), 2, roof))
        tips.append(tip)
        tower_torches += tt[:1]
    f, body, mroof, mtip, tt = round_tower(MT[0], MT[1], 6, 46, 16, 'roof_red', rng, [23, 29, 35, 41], y_start=19)
    W['main_tower'] = D(body)
    W['main_tip'] = mtip
    tips.append(mtip)
    tower_torches += tt
    W['found_ring'], W['found_keep'] = D(found_ring), D(found_keep)

    kroof = {}
    for k in range(12):
        zl, zh = Z0 + 1 + k, Z1 - 1 - k
        if zl > zh:
            break
        y = 19 + k
        for x in range(X0 + 1, X1):
            for z in sorted({zl, zh}):
                if math.hypot(x - MT[0], z - MT[1]) <= 6.8 or near_corner(x, z, 3.6):
                    continue
                kroof[(x, y, z)] = 'roof_red'
            if x in (X0 + 1, X1 - 1):
                for z in range(zl + 1, zh):
                    if not near_corner(x, z, 3.6):
                        kroof[(x, y, z)] = 'spruce_planks'
    roofs.insert(len(roofs), ((0, -9), 9, kroof))
    roofs.append((MT, 6, mroof))
    W['roofs'] = [(c, R, D(d)) for c, R, d in roofs]

    court = []
    for z in range(32, 2, -1):
        for x in range(-2, 3):
            court.append(SH('gravel', (x + .5, 1.03, z + .5), (1, 0.06, 1), cell=(x, 1, z)))
    for x in list(range(-20, -2)) + list(range(3, 21)):
        for z in (15, 16):
            court.append(SH('gravel', (x + .5, 1.03, z + .5), (1, 0.06, 1), cell=(x, 1, z)))
    lamps = []
    for z in (6, 11, 21, 26):
        for x in (-3, 3):
            lamps.append(SH('fence', (x + .5, 2.0, z + .5), (0.25, 2, 0.25)))
            lamps.append(SH('glowstone', (x + .5, 3.3, z + .5), (0.55, 0.6, 0.55), light=(x, 3, z, 15)))
    trees = [D(tree_cells(x, z, int(rng.integers(5, 7)), rng))
             for (x, z) in [(20, 8), (-20, 8), (21, -8), (-21, -8), (21, -24), (-21, -24)]]
    hut = {}
    for x in range(-22, -17):
        for z in range(18, 23):
            if not (x in (-22, -18) or z in (18, 22)):
                continue
            corner = x in (-22, -18) and z in (18, 22)
            for y in (1, 2, 3):
                if x == -18 and z == 20 and y <= 2:
                    continue
                if z in (18, 22) and x == -20 and y == 2:
                    hut[(x, y, z)] = 'glass_lit'
                    continue
                hut[(x, y, z)] = 'oak_log' if corner else 'oak_planks'
    for k, y in enumerate((4, 5, 6, 7)):
        xa, xb, za, zb = -23 + k, -17 - k, 17 + k, 23 - k
        for x in range(xa, xb + 1):
            for z in range(za, zb + 1):
                if x in (xa, xb) or z in (za, zb) or k == 3:
                    hut[(x, y, z)] = 'roof_red'
    well = D({(x, 1, z): 'cobblestone' for x in range(18, 21) for z in range(19, 22) if (x, z) != (19, 20)})
    well.append(SH('water', (19.5, 1.8, 20.5), (1, 0.05, 1)))
    for (x, z) in [(18, 19), (20, 19), (18, 21), (20, 21)]:
        well.append(SH('fence', (x + .5, 3.0, z + .5), (0.25, 2, 0.25)))
    well.append(SH('spruce_planks', (19.5, 4.25, 20.5), (3.2, 0.5, 3.2)))
    flowers = []
    for x in list(range(-11, -3)) + list(range(4, 12)):
        for z in (3, 4, 5):
            r = rng.random()
            if r < 0.35:
                flowers.append(SH('flower_red' if rng.random() < 0.5 else 'flower_yellow', (x + .5, 1.2, z + .5), (0.3, 0.4, 0.3)))
            elif r < 0.55 and z == 3:
                flowers.append(P(x, 1, z, 'leaves'))
    W['court'] = [court, lamps] + trees + [D(hut), well, flowers]

    outer_dec, inner_dec = [], []
    for x in range(-30, 31):
        for z in range(-30, 31):
            m = max(abs(x), abs(z))
            if m not in (28, 27) or in_gate(x, z) or in_tower(x, z):
                continue
            coord = x if abs(z) >= abs(x) else z
            if abs(coord) >= 23:
                continue
            if m == 28 and coord % 6 == 0 and abs(coord) > 5:
                inner_dec.append(TORCH(x, 13, z))
            if m == 27 and coord % 8 == 4:
                ox = 0.35 * np.sign(x) if abs(x) == 27 else 0.0
                oz = 0.35 * np.sign(z) if abs(z) == 27 else 0.0
                inner_dec.append(TORCH(x, 5, z, ox, oz))
    for (x, y, z) in tower_torches:
        outer_dec.append(TORCH(x, y, z))
    for x in (-3, 3):
        inner_dec.append(TORCH(x, 3, 3, 0, -0.35))
    for x in (-2, 2):
        outer_dec.append(TORCH(x, 2, 40))
        outer_dec.append(TORCH(x, 2, 33))
    banners = []
    for c in (-18, -12, 12, 18):
        banners.append(((c + .5, 9.0, -30.05), (0.9, 3, 0.08)))
        banners.append(((31.05, 9.0, c + .5), (0.08, 3, 0.9)))
        banners.append(((-30.05, 9.0, c + .5), (0.08, 3, 0.9)))
    for c in (-19, -15, 15, 19):
        banners.append(((c + .5, 9.0, 31.05), (0.9, 3, 0.08)))
    for x in (-3, 3):
        banners.append(((x + .5, 10.5, 34.05), (0.9, 3, 0.08)))
    for x in (-8, 8):
        inner_dec.append(SH('banner', (x + .5, 10.5, 3.05), (0.9, 3, 0.08)))
    for (c, s) in banners:
        outer_dec.append(SH('banner', c, s))
    for (x, y, z) in tips:
        outer_dec.append(SH('fence', (x + .5, y + 2.5, z + .5), (0.18, 3, 0.18)))
        outer_dec.append(SH('flag', (x + .5 + 1.15, y + 3.35, z + .5), (2.1, 1.3, 0.06)))
    W['outer_dec'], W['inner_dec'] = outer_dec, inner_dec
    W['door'] = [RM(x, y, 2) for x in (-1, 0, 1) for y in range(1, 6)]
    W['interior'] = gen_interior()
    return W


def gen_interior():
    """Throne hall furniture inside the keep (x -12..12, z -18..0, y 1..10)."""
    I = {}
    lights = []
    for (x, z) in [(0, -4), (0, -12), (-8, -4), (-8, -12), (8, -4), (8, -12)]:
        lights.append(SH('fence', (x + .5, 10.0, z + .5), (0.12, 2.0, 0.12)))
        lights.append(SH('glowstone', (x + .5, 8.5, z + .5), (0.8, 0.8, 0.8), light=(x, 8, z, 15)))
        lights.append(SH('fence', (x + .5, 8.5, z + .5), (2.4, 0.12, 0.12)))
        lights.append(SH('fence', (x + .5, 8.5, z + .5), (0.12, 0.12, 2.4)))
        for (dx, dz) in [(1.15, 0), (-1.15, 0), (0, 1.15), (0, -1.15)]:
            lights.append(SH('torch', (x + .5 + dx, 8.8, z + .5 + dz), (0.14, 0.5, 0.14)))
    for z in (-16, -12, -8, -4):
        lights.append(TORCH(-12, 5, z, -0.35, 0))
        lights.append(TORCH(12, 5, z, 0.35, 0))
    for x in (-9, -5, 5, 9):
        lights.append(TORCH(x, 5, -18, 0, -0.35))
        lights.append(TORCH(x, 5, 0, 0, 0.35))
    I['lights'] = lights
    floor = []
    for z in range(0, -19, -1):
        for x in range(-12, 13):
            if abs(x) == 12 or z in (0, -18):
                t = 'smooth_stone'
            elif (z % 4 == 0):
                t = 'spruce_planks'
            else:
                t = 'dark_oak_planks'
            floor.append(SH(t, (x + .5, 0.53, z + .5), (1, 1, 1), cell=(x, 0, z)))
    I['floor'] = floor
    carpet = []
    for z in range(0, -16, -1):
        for x in (-1, 0, 1):
            carpet.append(SH('carpet_red', (x + .5, 1.09, z + .5), (1, 0.06, 1)))
    for sx in (-1, 1):
        for z in range(-14, -1):
            for x in range(6, 11):
                carpet.append(SH('carpet_blue', (sx * x + .5, 1.09, z + .5), (1, 0.06, 1)))
    I['carpet'] = carpet
    pil = {}
    for x in (-4, 4):
        for z in (-2, -7, -12):
            for y in range(1, 11):
                pil[(x, y, z)] = 'stone_bricks' if y in (1, 10) else 'pillar'
    I['pillars'] = D(pil)
    th = {}
    for x in range(-3, 4):
        for z in range(-18, -14):
            th[(x, 1, z)] = 'smooth_stone'
    for x in range(-2, 3):
        for z in range(-18, -15):
            th[(x, 2, z)] = 'smooth_stone'
    th[(0, 3, -17)] = 'gold'
    th[(-1, 3, -17)] = th[(1, 3, -17)] = 'gold'
    for y in (3, 4, 5, 6):
        th[(0, y, -18)] = 'gold'
    throne = D(th)
    throne.append(SH('wool_red', (0.5, 4.08, -16.5), (0.9, 0.16, 0.9)))
    for x in (-3, 3):
        throne.append(SH('fence', (x + .5, 2.5, -15.5), (0.2, 1.0, 0.2)))
        throne.append(SH('glowstone', (x + .5, 3.25, -15.5), (0.5, 0.5, 0.5), light=(x, 3, -16, 15)))
    for x in (-2, 2):
        throne.append(SH('banner', (x + .5, 7.0, -17.95), (0.9, 3, 0.08)))
    I['throne'] = throne
    tables = []
    for sx in (-1, 1):
        x = 8 * sx
        for z in range(-13, -2):
            tables.append(SH('spruce_planks', (x + .5, 1.92, z + .5), (1, 0.15, 1)))
        for z in (-13, -3):
            tables.append(SH('fence', (x + .5, 1.42, z + .5), (0.2, 0.85, 0.2)))
        for z in range(-12, -3, 2):
            for cx in (x - 2, x + 2):
                side = 1 if cx > x else -1
                tables.append(SH('oak_planks', (cx + .5, 1.5, z + .5), (0.8, 0.12, 0.8)))
                tables.append(SH('oak_planks', (cx + .5 + side * 0.36, 2.0, z + .5), (0.1, 0.9, 0.8)))
        for z in (-11, -7, -3):
            tables.append(SH('cake', (x + .5, 2.2, z + .5), (0.8, 0.45, 0.8)))
        for z in (-9, -5):
            tables.append(SH('torch', (x + .5, 2.25, z + .5), (0.12, 0.5, 0.12), light=(x, 2, z, 14)))
    I['tables'] = tables
    fp = {}
    for y in range(1, 11):
        for z in range(-11, -6):
            if y <= 4 and -10 <= z <= -8:
                continue
            if y >= 5 and z in (-11, -7):
                continue
            fp[(-12, y, z)] = 'cobblestone'
    fire = D(fp)
    for z in (-10, -9, -8):
        fire.append(SH('fire', (-11.5, 1.45, z + .5), (0.9, 0.9, 0.9), light=(-12, 1, z, 15)))
    I['fireplace'] = fire
    sh = {}
    for z in list(range(-17, -12)) + list(range(-5, 0)):
        for y in (1, 2, 3):
            sh[(12, y, z)] = 'bookshelf'
    for z in (-10, -9, -8):
        sh[(12, 1, z)] = 'chest'
    for x in list(range(-11, -5)) + list(range(6, 12)):
        for y in (1, 2):
            sh[(x, y, 0)] = 'bookshelf'
    I['shelves'] = D(sh)
    dec = []
    for sx in (-1, 1):
        for z in (-13, -9, -5):
            dec.append(SH('banner', (12.95 if sx > 0 else -11.95, 6.0, z + .5), (0.08, 3, 0.9)))
    for (x, z) in [(-11, -17), (11, -17), (-5, -1), (5, -1)]:
        dec.append(P(x, 1, z, 'leaves'))
    for (x, z) in [(-5, -3), (5, -3), (-5, -8), (5, -8), (-5, -13), (5, -13)]:
        dec.append(SH('flower_red' if (x + z) % 2 else 'flower_yellow', (x + .5, 1.3, z + .5), (0.3, 0.45, 0.3)))
    I['decor'] = dec
    return I


# --------------------------------------------------------------------------
# Ordering
# --------------------------------------------------------------------------


def order_acts(acts, center, start, chunk=None, desc=None, fixed_start_angle=None):
    """Chunk by angle around center, then by layer, then nearest-neighbour."""
    if not acts:
        return []
    pos = np.array([a.c for a in acts], float)
    n = len(acts)
    if chunk:
        ang = np.arctan2(pos[:, 2] - center[1], pos[:, 0] - center[0])
        a0 = fixed_start_angle if fixed_start_angle is not None else math.atan2(start[2] - center[1], start[0] - center[0])
        ang = (ang - a0) % TWO_PI
        r = float(np.median(np.hypot(pos[:, 0] - center[0], pos[:, 2] - center[1])))
        ck = np.floor(ang * max(r, 1.0) / chunk).astype(int)
    else:
        ck = np.zeros(n, int)
    if desc is None:
        desc = acts[0].kind == 1
    ys = np.floor(pos[:, 1] + 0.001).astype(int)
    out = []
    last = np.array(start, float)
    for c in sorted(set(ck.tolist())):
        idx_c = np.where(ck == c)[0]
        for y in sorted(set(ys[idx_c].tolist()), reverse=desc):
            sub = idx_c[ys[idx_c] == y]
            rem = list(sub)
            pp = pos[sub]
            alive = np.ones(len(sub), bool)
            for _ in range(len(sub)):
                d = np.sum((pp - last) ** 2, 1)
                d[~alive] = np.inf
                j = int(np.argmin(d))
                alive[j] = False
                out.append(acts[rem[j]])
                last = pp[j]
    return out


# --------------------------------------------------------------------------
# Story
# --------------------------------------------------------------------------
EYE = 1.62


class Story:
    def __init__(self):
        self.ev = []
        self.world = {}
        self.T = 0.0
        self.segs = []
        self.caps = []
        self.theta = []
        self.storm = [(0.0, 0.0)]
        self.sfx = []
        self.snd_ev = []
        self.lights = []
        self.rem = []
        self.swings = []
        self.hurts = []
        self.res = {'WOOD': [], 'STONE': [], 'COAL': [], 'IRON': [], 'DIAMONDS': []}
        self.fights = []
        self.fireworks = []
        self.lightning = []
        self.fire_t = None
        self.cam_end = (np.array([0, 3, 50.0]), np.array([0, 3, 0.0]))

    # -- events --
    def emit(self, t, a, sound=True):
        if a.kind == 1:
            ty = self.world.pop(a.cell, None)
            if ty is None:
                return None
            self.ev.append((t, 1, a.cell, ty, a.c, None))
            if t > -INF / 2:
                self.rem.append((t, a.c, ty))
                if sound:
                    self.snd_ev.append((t, MATERIAL.get(ty, 'stone'), 1))
                r = {'oak_log': 'WOOD', 'stone': 'STONE', 'cobblestone': 'STONE', 'coal_ore': 'COAL',
                     'iron_ore': 'IRON', 'diamond_ore': 'DIAMONDS'}.get(ty)
                if r:
                    self.res[r].append(t)
            return ty
        if a.cell is not None:
            self.world[a.cell] = a.type
        self.ev.append((t, 0, a.cell, a.type, a.c, a.s))
        if a.light:
            self.lights.append((*a.light, t))
        if t > -INF / 2 and sound:
            self.snd_ev.append((t, MATERIAL.get(a.type, 'stone'), 0))
        return a.type

    def seg(self, kind, t0, t1, **kw):
        d = dict(kind=kind, t0=t0, t1=t1, hud=True, hand=True, tl=False, final=False, res=False,
                 walk=False, item='none')
        d.update(kw)
        self.segs.append(d)
        return d

    def cap(self, dt0, dur, text, style='sub'):
        self.caps.append((self.T + dt0, self.T + dt0 + dur, text, style))

    def th(self, theta, t=None):
        self.theta.append((self.T if t is None else t, theta))

    # -- segment builders --
    def card(self, dur, text, sub=None):
        self.seg('card', self.T, self.T + dur, hud=False, hand=False)
        self.caps.append((self.T + 0.3, self.T + dur - 0.2, text, 'card'))
        if sub:
            self.caps.append((self.T + 0.5, self.T + dur - 0.2, sub, 'cardsub'))
        self.T += dur

    def path(self, dur, keys, **kw):
        """keys: list of (u, eye, look) with u in [0, 1]."""
        ks = [(self.T + u * dur, np.array(e, float), np.array(l, float)) for u, e, l in keys]
        self.seg('path', self.T, self.T + dur, keys=ks, **kw)
        self.T += dur
        self.cam_end = (ks[-1][1], ks[-1][2])

    def build(self, acts, rate, cam, travel=18.0, chapter=None, work=None, tl=True, res=False, gap=0.5):
        t = self.T + 0.15
        prev = None
        T, Pp, items, stands = [], [], [], []
        stand = None
        for a in acts:
            if a.kind == 1 and a.cell not in self.world:
                continue
            p = np.array(a.c, float)
            d = 0.0 if prev is None else float(np.linalg.norm(p - prev))
            t += 1.0 / rate + max(0.0, d - 3.0) / travel
            ty = self.emit(t, a)
            items.append(tool_for(ty) if a.kind == 1 else held_for(ty))
            T.append(t)
            Pp.append(p)
            prev = p
            if work:
                if stand is None:
                    stand = self.cam_end[0] - np.array([0, EYE, 0])
                v = np.array([stand[0] - p[0], stand[2] - p[2]])
                n = np.linalg.norm(v)
                v = v / n if n > 1e-3 else np.array([0, 1.0])
                st = np.array([p[0] + v[0] * work.get('dist', 2.6), work['feet'](p), p[2] + v[1] * work.get('dist', 2.6)])
                if 'bounds' in work:
                    b = work['bounds']
                    st[0] = min(max(st[0], b[0]), b[1])
                    st[2] = min(max(st[2], b[2]), b[3])
                stand = st
                stands.append(st.copy())
        kind = 'work' if work else 'build'
        sg = self.seg(kind, self.T, t + gap, times=np.array(T), pos=np.array(Pp), items=items,
                      stands=np.array(stands) if work else None, tl=tl, res=res, **cam)
        if chapter:
            self.caps.append((self.T + 0.2, self.T + 3.6, chapter, 'chapter'))
        self.T = t + gap
        e, l = raw_cam(sg, self.T - 0.01)
        self.cam_end = (e, l)
        return sg

    def fight(self, Pf, look0, spawns, hurt_idx=1):
        t0 = self.T
        Pf = np.array(Pf, float)
        mobs = []
        t = t0 + 1.0
        for i, sp in enumerate(spawns):
            sp = np.array(sp, float)
            dv = Pf - sp
            dist = float(np.hypot(dv[0], dv[2]))
            dirv = np.array([dv[0], 0, dv[2]]) / dist
            speed = 1.5
            start = t0 + 0.2 + i * 0.6
            stop = dist - 1.9
            arrive = start + stop / speed
            engage = max(t, arrive - 0.2)
            hits = [engage + 0.25, engage + 0.85, engage + 1.45]
            if i == hurt_idx:
                h = engage + 0.55
                self.hurts.append(h)
                self.sfx.append((h, 'hurt', 0.8))
                self.sfx.append((h - 0.05, 'hit', 0.6))
            death = hits[-1] + 0.3
            mobs.append(dict(sp=sp, dirv=dirv, speed=speed, start=start, stop=stop, hits=hits, death=death,
                             engage=engage))
            for hh in hits:
                self.swings.append(hh - 0.08)
                self.sfx.append((hh - 0.08, 'swing', 0.5))
                self.sfx.append((hh, 'hit', 0.8))
            for g in np.arange(start + 0.4, death, 2.3):
                self.sfx.append((g, 'groan', 0.55))
            self.sfx.append((death, 'poof', 0.7))
            t = death + 0.45
        t1 = t + 0.8
        sg = self.seg('fight', t0, t1, P=Pf, look0=np.array(look0, float), mobs=mobs, item='sword')
        self.fights.append(sg)
        self.T = t1
        self.cam_end = (Pf + np.array([0, EYE, 0]), np.array(look0, float))


def mob_pos(m, t):
    s = min(max((t - m['start']) * m['speed'], 0.0), m['stop'])
    p = m['sp'] + m['dirv'] * s
    kb = 0.0
    for h in m['hits']:
        if t >= h:
            kb += 1.1 * math.exp(-(t - h) / 0.3)
    p = p - m['dirv'] * kb
    moving = 0 < (t - m['start']) * m['speed'] < m['stop']
    return p, moving


def fight_look(sg, t):
    best = None
    for m in sg['mobs']:
        if t < m['death'] + 0.15 and t >= m['start'] - 0.5:
            best = m
            break
    if best is None:
        return sg['look0']
    p, _ = mob_pos(best, t)
    return p + np.array([0, 1.4, 0])


def raw_cam(sg, t):
    k = sg['kind']
    if k == 'path':
        ks = sg['keys']
        return catmull([(a, e) for a, e, l in ks], t), catmull([(a, l) for a, e, l in ks], t)
    if k in ('build', 'work'):
        T, Pp = sg['times'], sg['pos']
        if len(T) == 0:
            return np.array([0, 10, 50.0]), np.zeros(3)
        n = len(T)
        i = int(np.clip(np.searchsorted(T, t) - 1, 0, n - 1))
        j = min(i + 1, n - 1)
        u = 0.0 if j == i else float(np.clip((t - T[i]) / max(T[j] - T[i], 1e-6), 0, 1))
        tgt = Pp[i] * (1 - u) + Pp[j] * u
        if k == 'work':
            S = sg['stands']
            st = S[i] * (1 - u) + S[j] * u
            return st + np.array([0, EYE, 0]), tgt
        a = np.searchsorted(T, t - 1.3)
        b = np.searchsorted(T, t + 1.3)
        if b <= a:
            a, b = i, i + 1
        anchor = Pp[a:b].mean(0)
        c = np.array(sg['center'], float)
        if sg.get('inside'):
            ex = np.clip(anchor[0] * 0.15, -2.0, 2.0)
            ez = anchor[2] + (5.5 if anchor[2] < -8 else -5.5)
            ez = np.clip(ez, -16.5, -1.5)
            ey = np.clip(anchor[1] + 2.5, 3.6, 7.5)
            return np.array([ex, ey, ez]), tgt
        v = anchor[[0, 2]] - c
        nv = np.linalg.norm(v)
        dirv = v / nv if nv > 1.5 else np.array(sg.get('fallback', (0.0, 1.0)))
        dirv = dirv * sg.get('side', 1)
        eye = anchor + np.array([dirv[0] * sg['D'], sg['H'], dirv[1] * sg['D']])
        return eye, tgt
    if k == 'fight':
        return sg['P'] + np.array([0, EYE, 0]), fight_look(sg, t)
    return None, None


def catmull(keys, t):
    ts = [k[0] for k in keys]
    if t <= ts[0]:
        return np.array(keys[0][1], float)
    if t >= ts[-1]:
        return np.array(keys[-1][1], float)
    i = bisect.bisect_right(ts, t) - 1
    p0 = np.array(keys[max(i - 1, 0)][1], float)
    p1 = np.array(keys[i][1], float)
    p2 = np.array(keys[i + 1][1], float)
    p3 = np.array(keys[min(i + 2, len(keys) - 1)][1], float)
    u = (t - ts[i]) / (ts[i + 1] - ts[i])
    u = u * u * (3 - 2 * u) if len(keys) == 2 else u
    return 0.5 * (2 * p1 + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)


def build_story():
    W = gen_parts()
    S = Story()
    for a in W['init']:
        S.emit(-INF, a, sound=False)

    # ---------------- cold open: finished castle tour ----------------
    S.th(2.55)
    S.path(41.0, [
        (0.00, (80, 30, 125), (0, 18, 0)),
        (0.15, (40, 16, 82), (0, 10, 0)),
        (0.29, (0, 6.5, 56), (0, 5, 25)),
        (0.37, (0, 4.2, 40), (0, 4, 20)),
        (0.44, (0, 4.0, 24), (0, 6, 0)),
        (0.52, (0, 9, 12), (0, 22, -6)),
        (0.63, (0, 40, 9), (0, 58, -9)),
        (0.74, (15, 63, 4), (0, 62, -9)),
        (0.86, (17, 71, -25), (0, 60, -9)),
        (1.00, (80, 90, -70), (0, 25, -5)),
    ], hud=False, hand=False, final=True)
    S.caps.append((1.5, 8.0, "I BUILT AN EPIC CASTLE", 'title'))
    S.caps.append((2.3, 8.0, "in a block world - first person", 'titlesub'))
    S.caps.append((33.0, 39.5, "...but how did it all start?", 'sub'))
    S.th(2.75)
    S.card(3.5, "DAY 1", "An empty field")

    # ---------------- day 1: walk, clearing, quarry, diamonds ----------------
    S.th(0.35)
    S.path(10.0, [
        (0.0, (5, 1 + EYE, 64), (0, 6, 0)),
        (0.3, (4, 1 + EYE, 54), (-30, 5, 10)),
        (0.6, (3, 1 + EYE, 44), (25, 4, -5)),
        (1.0, (1, 1 + EYE, 34), (-4, 4, 24)),
    ], walk=True)
    S.cap(-9.0, 4.0, "It all started with an empty field...")
    S.cap(-4.6, 4.4, "...and a crazy idea.")
    trees = sorted(W['site_trees'], key=lambda tr: math.hypot(tr[0][0] - 1, tr[0][1] - 34))
    acts = []
    cur = np.array([1, 1, 34.0])
    left = list(trees)
    while left:
        left.sort(key=lambda tr: math.hypot(tr[0][0] - cur[0], tr[0][1] - cur[2]))
        (tx, tz), cells = left.pop(0)
        cells = sorted(cells, key=lambda c: (-c[1], abs(c[0] - tx) + abs(c[2] - tz)))
        acts += [RM(*c) for c in cells]
        cur = np.array([tx, 1, tz])
    S.cap(4.0, 4.5, "First, these trees have to go.")
    S.build(acts, 20, dict(), travel=10.0, work=dict(feet=lambda p: 1.0, dist=4.6),
            chapter="CLEARING THE LAND", res=True)
    S.th(1.2)
    e0 = S.cam_end[0]
    S.path(5.0, [(0.0, e0, S.cam_end[1]), (0.5, (-40, 1 + EYE, 0), (-60, 1.5, -1)),
                 (1.0, (-57.5, 1 + EYE, -0.5), (-64, 0, -1))], walk=True, tl=True, res=True)
    S.cap(-4.8, 4.5, "Now I need stone. A LOT of stone.")
    S.build(order_acts(W['quarry'], (-65, -1), np.array([-58, 1, -1.0]), desc=True), 40, dict(), travel=6.0,
            work=dict(feet=lambda p: math.floor(p[1]) + 1.0, dist=2.4, bounds=(-69.6, -60.4, -5.6, 3.6)),
            chapter="THE QUARRY", res=True)
    S.th(2.35)
    de = S.cam_end[0]
    dpos = np.array([-64.5, -8.5, -1.5])
    S.path(3.0, [(0.0, de, S.cam_end[1]), (1.0, (-63.5, -9 + EYE, 0.5), dpos)], res=True, item='pickaxe')
    S.cap(-2.8, 2.9, "Wait... is that...?")
    sg = S.build(W['diamonds'], 1.1, dict(), work=dict(feet=lambda p: -9.0, dist=2.0,
                                                       bounds=(-69.6, -60.4, -5.6, 3.6)), tl=False, res=True, gap=1.2)
    S.caps.append((sg['times'][0] - 0.1, sg['times'][0] + 3.6, "DIAMONDS!!!", 'big'))
    S.sfx.append((sg['times'][0] + 0.05, 'chime', 0.8))
    S.th(2.4)
    e0 = S.cam_end[0]
    S.path(7.0, [(0.0, e0, S.cam_end[1]), (0.25, (-63, 3.5, 0), (-50, 3, 0)),
                 (0.5, (-58, 1 + EYE, 0), (-40, 2, 0)), (1.0, (-46, 1 + EYE, 0), (-30, 2.5, 3))],
           walk=True, res=True, item='sword')
    S.th(3.55)
    S.cap(-6.5, 4.0, "Uh oh... it's getting dark.")
    S.cap(0.3, 2.5, "ZOMBIES!", 'big')
    S.fight((-46, 1, 0), (-30, 2.5, 3), [(-32, 1, 7), (-34, 1, -11), (-57, 1, 9)])
    S.th(3.95)
    S.path(3.0, [(0.0, S.cam_end[0], S.cam_end[1]), (1.0, S.cam_end[0], S.cam_end[1] + np.array([0, -0.5, 6]))],
           res=True, item='sword')
    S.cap(-2.9, 2.9, "Phew... time to sleep.")
    S.card(3.0, "DAY 2", "The moat")

    # ---------------- day 2: moat, water, foundation ----------------
    S.th(TWO_PI + 0.3)
    S.path(3.5, [(0.0, (8, 14, 66), (0, 0, 30)), (1.0, (6, 7, 46), (-6, 0, 37))])
    S.cap(-3.4, 3.6, "Let's dig a giant moat around the whole castle!")
    start = np.array([6, 7, 46.0])
    S.build(order_acts(W['moat'], (0, 0), start, chunk=8), 130, dict(center=(0, 0), D=4.5, H=4.5),
            chapter="THE MOAT")
    S.sfx.append((S.T + 0.1, 'splash', 0.8))
    S.cap(0.0, 3.5, "Water time!")
    S.build(order_acts(W['water'], (0, 0), start, chunk=6), 120, dict(center=(0, 0), D=4.5, H=4.0))
    S.build(order_acts(W['found_ring'], (0, 0), S.cam_end[0], chunk=10) +
            order_acts(W['found_keep'], (0, -9), S.cam_end[0], chunk=8),
            100, dict(center=(0, -3), D=8, H=6.5), chapter="FOUNDATION")
    S.th(TWO_PI + 3.2)
    S.path(3.0, [(0.0, S.cam_end[0], S.cam_end[1]), (1.0, S.cam_end[0] + np.array([0, 10, 0]), (0, 0, -3))])
    S.cap(-2.9, 2.9, "Not bad for day two.")
    S.card(3.0, "DAY 3", "Walls & towers")

    # ---------------- day 3: walls (storm), towers, zombie night ----------------
    S.th(2 * TWO_PI + 0.3)
    w0 = S.T
    S.build(order_acts(W['walls'], (0, 0), np.array([0, 5, 45.0]), chunk=10), 100,
            dict(center=(0, 0), D=6.5, H=4.0), chapter="THE WALLS")
    w1 = S.T
    s0, s1 = w0 + 0.3 * (w1 - w0), w1 - 2
    S.storm += [(s0 - 4, 0.0), (s0 + 2, 1.0), (s1 - 3, 1.0), (s1 + 3, 0.0)]
    S.caps.append((s0 - 1, s0 + 3.5, "A storm is coming... but we keep building!", 'sub'))
    rng = np.random.default_rng(9)
    for lt in np.arange(s0 + 2, s1 - 2, 3.5):
        lt = float(lt + rng.uniform(-1, 1))
        S.lightning.append(lt)
        S.sfx.append((lt + rng.uniform(0.3, 1.2), 'thunder', 0.9))
    first = True
    for (cx, cz), R, acts in W['towers']:
        st = S.cam_end[0]
        S.build(order_acts(acts, (cx, cz), st), 120, dict(center=(cx, cz), D=R + 8, H=3.5, fallback=tuple(norm((cx, cz)))),
                chapter="SEVEN GIANT TOWERS" if first else None, gap=0.3)
        first = False
    S.th(2 * TWO_PI + 3.3)
    S.path(4.0, [(0.0, S.cam_end[0], S.cam_end[1]), (0.6, (2, 6, 22), (0, 2, 10)), (1.0, (0, 1 + EYE, 14), (-8, 2, 18))],
           item='sword')
    S.th(2 * TWO_PI + 3.65)
    S.cap(-3.5, 3.5, "Something is moving in the dark...")
    S.fight((0, 1, 14), (-8, 2, 18), [(-15, 1, 22), (13, 1, 5), (-4, 1, -2)], hurt_idx=2)
    S.th(2 * TWO_PI + 4.0)
    S.path(3.0, [(0.0, S.cam_end[0], S.cam_end[1]), (1.0, S.cam_end[0], (6, 3, 4))], item='sword')
    S.cap(-2.9, 2.9, "Note to self: MORE TORCHES.")
    S.card(3.0, "DAY 4", "Gatehouse & keep")

    # ---------------- day 4: gate, bridge, road, keep ----------------
    S.th(3 * TWO_PI + 0.3)
    S.path(2.5, [(0.0, (0, 10, 60), (0, 6, 30)), (1.0, (-6, 8, 44), (-8, 4, 30))])
    first = True
    for c, acts in W['gate']:
        S.build(order_acts(acts, c, S.cam_end[0]), 75, dict(center=(c[0], 20), D=7, H=3.5, fallback=(0.0, 1.0)),
                chapter="GATEHOUSE & DRAWBRIDGE" if first else None, gap=0.3)
        first = False
    S.build(order_acts(W['bridge'], (0, 30), S.cam_end[0]), 40, dict(center=(0, 20), D=5, H=3, fallback=(1.0, 0.0)))
    S.build(sorted(W['road'], key=lambda a: (a.c[2], abs(a.c[0]))), 45, dict(center=(0, 20), D=4, H=3, fallback=(1.0, 0.0)))
    S.build(order_acts(W['keep'], (0, -9), S.cam_end[0], chunk=9), 110, dict(center=(0, -9), D=7, H=4),
            chapter="THE KEEP")
    for c, acts in W['turrets']:
        S.build(order_acts(acts, c, S.cam_end[0]), 110, dict(center=c, D=7, H=3, fallback=tuple(norm((c[0], c[1] + 9)))), gap=0.2)
    S.th(3 * TWO_PI + 3.2)
    S.path(3.0, [(0.0, S.cam_end[0], S.cam_end[1]), (1.0, S.cam_end[0] + np.array([0, 8, 0]), (0, 10, -9))])
    S.cap(-2.9, 2.9, "Tomorrow: the tallest tower.")
    S.card(3.0, "DAY 5", "The final day")

    # ---------------- day 5: main tower, roofs, courtyard, decorations ----------------
    S.th(4 * TWO_PI + 0.3)
    S.path(2.5, [(0.0, (14, 22, 12), (0, 20, -9)), (1.0, (12, 22, 6), (0, 20, -9))])
    S.cap(14.0, 4.0, "Don't look down...")
    S.build(order_acts(W['main_tower'], MT, S.cam_end[0]), 70, dict(center=MT, D=11, H=3.0),
            chapter="THE GREAT TOWER")
    first = True
    for c, R, acts in W['roofs']:
        fb = tuple(norm(c)) if math.hypot(*c) > 3 else (0.0, 1.0)
        S.build(order_acts(acts, c, S.cam_end[0]), 75, dict(center=c, D=R + 6, H=3.0, fallback=fb),
                chapter="ROOFS" if first else None, gap=0.25)
        first = False
    first = True
    for part in W['court']:
        S.build(order_acts(part, (0, 6), S.cam_end[0]), 28, dict(center=(0, 6), D=5, H=2.5),
                chapter="THE COURTYARD" if first else None, gap=0.25)
        first = False
    S.build(order_acts(W['inner_dec'], (0, 0), S.cam_end[0], chunk=12), 9,
            dict(center=(0, 0), D=6, H=2.5, side=-1), chapter="BANNERS, FLAGS & TORCHES", travel=45)
    S.build(order_acts(W['outer_dec'], (0, 0), S.cam_end[0], chunk=12), 10, dict(center=(0, 0), D=7, H=3), travel=45)
    S.th(4 * TWO_PI + 2.75)

    # ---------------- reveal ----------------
    S.path(20.0, [(0.0, (95, 22, 95), (0, 20, 0)), (0.35, (55, 40, 75), (0, 25, -5)),
                  (0.7, (-10, 58, 62), (0, 28, -8)), (1.0, (-70, 45, 45), (0, 25, -8))])
    S.th(4 * TWO_PI + 3.15)
    S.cap(-18.5, 6.0, "It's finally finished!")
    S.cap(-10.0, 5.0, "...or is it?")

    # ---------------- interior ----------------
    S.th(4 * TWO_PI + 3.55)
    S.path(7.0, [(0.0, (0, 1 + EYE, 13), (0, 3, 2)), (0.45, (0, 1 + EYE, 5), (0, 3, 0)),
                 (1.0, (0, 1 + EYE, -2.5), (0, 4, -12))], walk=True)
    for a in W['door']:
        S.emit(S.T - 4.5, a, sound=False)
    S.sfx.append((S.T - 4.5, 'door', 0.8))
    S.cap(-3.5, 4.0, "Inside... it's completely EMPTY.")
    I = W['interior']
    hall = dict(center=(0, -9), inside=True)
    start = np.array([0, 3, -3.0])
    S.build(order_acts(I['lights'], (0, -9), start), 7, hall, chapter="LET THERE BE LIGHT", travel=10)
    S.build(order_acts(I['floor'], (0, -9), S.cam_end[0]), 30, hall, chapter="A PROPER FLOOR")
    S.build(order_acts(I['carpet'], (0, -9), S.cam_end[0]), 24, hall, chapter="ROYAL CARPET", travel=25)
    S.build(order_acts(I['pillars'], (0, -9), S.cam_end[0]), 20, hall)
    S.build(order_acts(I['throne'], (0, -16), S.cam_end[0]), 6, hall, chapter="THE THRONE")
    S.build(order_acts(I['tables'], (0, -9), S.cam_end[0]), 14, hall, chapter="FEAST HALL")
    fp = S.build(order_acts(I['fireplace'], (-12, -9), S.cam_end[0]), 10, hall, chapter="A WARM FIREPLACE")
    S.fire_t = float(fp['times'][-1])
    S.build(order_acts(I['shelves'], (0, -9), S.cam_end[0]), 12, hall, chapter="BOOKS & TREASURE")
    S.build(I['decor'], 4, hall)
    S.th(4 * TWO_PI + 4.1)
    S.path(6.0, [(0.0, (0, 1 + EYE, -1.5), (0, 3.5, -18)), (1.0, (0, 1 + EYE, -11.5), (0, 4.5, -18))],
           walk=True, cut=True, hand=False)
    S.path(6.0, [(0.0, (0, 3.2 + EYE, -16.4), (0, 3.6, -6)), (1.0, (0, 3.2 + EYE, -16.6), (0, 3.2, 1))],
           cut=True, hand=False)
    S.cap(-5.0, 4.8, "Now THIS is a castle.")

    # ---------------- finale ----------------
    S.th(4 * TWO_PI + 4.2)
    f0 = S.T
    S.path(26.0, [(0.0, (0, 1 + EYE, 15), (0, 24, -10)), (0.4, (0, 1 + EYE, 18), (0, 42, -22)),
                  (1.0, (0, 1 + EYE, 21), (0, 50, -28))], hud=False, hand=False, cut=True)
    S.th(4 * TWO_PI + 4.5)
    rng = np.random.default_rng(5)
    cols = ['spark_red', 'spark_gold', 'spark_blue', 'spark_green', 'spark_pink', 'spark_white']
    t = f0 + 1.5
    while t < f0 + 23:
        p = np.array([rng.uniform(-38, 38), rng.uniform(62, 92), rng.uniform(-40, 0)])
        dirs = rng.normal(size=(90, 3))
        dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
        S.fireworks.append(dict(tl=t, tb=t + 1.0, p=p, dirs=dirs, col=cols[rng.integers(0, 6)],
                                col2=cols[rng.integers(0, 6)], sp=rng.uniform(12, 17)))
        S.sfx.append((t, 'launch', 0.35))
        S.sfx.append((t + 1.0, 'boom', 0.7))
        t += rng.uniform(0.4, 1.0)
    S.caps.append((f0 + 15.5, f0 + 26.5, "THANKS FOR WATCHING!", 'title'))
    S.caps.append((f0 + 16.3, f0 + 26.5, "Like & subscribe for more epic builds", 'titlesub'))
    S.T_END = S.T
    S.main_tip = W['main_tip']
    return S


# --------------------------------------------------------------------------
# Light (block light + sky light), computed from the world at time t
# --------------------------------------------------------------------------
LV_O = np.array([-80, -12, -48])
LV_N = np.array([128, 80, 96])


def propagate(L, open_):
    for _ in range(15):
        nb = L.copy()
        np.maximum(nb[1:], L[:-1], out=nb[1:]); np.maximum(nb[:-1], L[1:], out=nb[:-1])
        np.maximum(nb[:, 1:], L[:, :-1], out=nb[:, 1:]); np.maximum(nb[:, :-1], L[:, 1:], out=nb[:, :-1])
        np.maximum(nb[:, :, 1:], L[:, :, :-1], out=nb[:, :, 1:]); np.maximum(nb[:, :, :-1], L[:, :, 1:], out=nb[:, :, :-1])
        nb = np.where(nb > 0, nb - 1, 0).astype(np.uint8)
        L = np.where(open_, np.maximum(L, nb), L)
    return L


class LightField:
    def __init__(self, inst, names, cells, lights):
        nx, ny, nz = LV_N
        self.base = np.zeros((nz, ny, nx), bool)
        xs = np.arange(nx) + LV_O[0]
        zs = np.arange(nz) + LV_O[2]
        X, Z = np.meshgrid(xs, zs)
        m = np.maximum(np.abs(X), np.abs(Z))
        hole = ((m >= 33) & (m <= 40)) | ((X >= QX0) & (X <= QX1) & (Z >= QZ0) & (Z <= QZ1))
        for iy in range(ny):
            if iy + LV_O[1] <= 0:
                self.base[:, iy, :] = ~hole
        sel = []
        for j, cell in enumerate(cells):
            if cell is None:
                continue
            nm = names[j]
            if nm in NONSOLID or inst[j][3] != 1 or inst[j][4] != 1:
                continue
            ix, iy, iz = cell[0] - LV_O[0], cell[1] - LV_O[1], cell[2] - LV_O[2]
            if 0 <= ix < nx and 0 <= iy < ny and 0 <= iz < nz:
                sel.append((ix, iy, iz, inst[j][7], inst[j][8]))
        a = np.array(sel, float)
        self.sx, self.sy, self.sz = a[:, 0].astype(int), a[:, 1].astype(int), a[:, 2].astype(int)
        self.s0, self.s1 = a[:, 3], a[:, 4]
        ls = [(x - LV_O[0], y - LV_O[1], z - LV_O[2], lv, t) for (x, y, z, lv, t) in lights
              if 0 <= x - LV_O[0] < nx and 0 <= y - LV_O[1] < ny and 0 <= z - LV_O[2] < nz]
        b = np.array(ls, float)
        self.lx, self.ly, self.lz = b[:, 0].astype(int), b[:, 1].astype(int), b[:, 2].astype(int)
        self.ll, self.lt = b[:, 3].astype(np.uint8), b[:, 4]

    def compute(self, t):
        solid = self.base.copy()
        m = (self.s0 <= t) & (t < self.s1)
        solid[self.sz[m], self.sy[m], self.sx[m]] = True
        open_ = ~solid
        above = np.maximum.accumulate(solid[:, ::-1, :], axis=1)[:, ::-1, :]
        sky = np.where(above, 0, 15).astype(np.uint8)
        sky = propagate(sky, open_)
        blk = np.zeros_like(sky)
        lm = self.lt <= t
        blk[self.lz[lm], self.ly[lm], self.lx[lm]] = self.ll[lm]
        blk = propagate(blk, open_)
        out = np.stack([blk, sky], -1).astype(np.float32) * (255.0 / 15.0)
        self.last = out
        return out.astype(np.uint8)

    def sample(self, p):
        ix, iy, iz = int(math.floor(p[0])) - LV_O[0], int(math.floor(p[1])) - LV_O[1], int(math.floor(p[2])) - LV_O[2]
        nx, ny, nz = LV_N
        if 0 <= ix < nx and 0 <= iy < ny and 0 <= iz < nz:
            v = self.last[iz, iy, ix]
            return v[0] / 255.0, v[1] / 255.0
        return 0.0, 1.0


# --------------------------------------------------------------------------
# Shaders
# --------------------------------------------------------------------------
VS_BLOCK = """
#version 330
in vec3 in_pos; in vec3 in_norm; in vec2 in_uv; in float in_face;
in vec3 i_c; in vec3 i_s; in float i_yaw; in float i_t0; in float i_t1; in float i_type;
uniform mat4 uVP; uniform float uT;
uniform ivec4 uTex[96]; uniform int uFlags[96];
out vec3 vW; out vec3 vN; out vec2 vUV; flat out int vL; flat out int vF;
void main() {
    int ty = int(i_type + 0.5);
    int face = int(in_face + 0.5);
    vF = uFlags[ty];
    vL = uTex[ty][face];
    float s = 1.0;
    if (uT < i_t0 || uT >= i_t1) s = 0.0;
    else {
        float a = (uT - i_t0) / 0.12;
        if (a < 1.0) s = 0.4 + 0.6 * a;
        float r = (i_t1 - uT) / 0.1;
        if (r < 1.0) s *= r;
    }
    vUV = in_uv;
    if (s <= 0.001) { vW = vec3(0.0); vN = vec3(0.0, 1.0, 0.0); gl_Position = vec4(0.0, 0.0, 2.0, 1.0); return; }
    float c = cos(i_yaw), sn = sin(i_yaw);
    vec3 p = in_pos * i_s * s;
    p = vec3(c * p.x + sn * p.z, p.y, -sn * p.x + c * p.z);
    vN = vec3(c * in_norm.x + sn * in_norm.z, in_norm.y, -sn * in_norm.x + c * in_norm.z);
    vW = i_c + p;
    gl_Position = uVP * vec4(vW, 1.0);
}
"""

FS_BLOCK = """
#version 330
in vec3 vW; in vec3 vN; in vec2 vUV; flat in int vL; flat in int vF;
uniform sampler2DArray uTexArr;
uniform sampler2DShadow uShadow;
uniform sampler3D uLV;
uniform mat4 uLightVP; uniform vec3 uLightDir; uniform vec3 uLightCol; uniform vec3 uAmb;
uniform vec3 uLVo; uniform vec3 uLVs; uniform float uDay;
uniform vec3 uCam; uniform vec3 uFogCol; uniform float uFogNear; uniform float uFogFar;
uniform float uGlow; uniform float uTime; uniform vec3 uFlash;
uniform int uHand; uniform vec3 uHandLight;
out vec4 frag;
float shadowAt(vec3 w, vec3 n) {
    vec4 lp = uLightVP * vec4(w + n * 0.07, 1.0);
    vec3 q = lp.xyz / lp.w * 0.5 + 0.5;
    if (q.x < 0.0 || q.x > 1.0 || q.y < 0.0 || q.y > 1.0 || q.z > 1.0) return 1.0;
    float sum = 0.0;
    vec2 px = vec2(1.0 / 4096.0);
    for (int i = -1; i <= 1; i++)
        for (int j = -1; j <= 1; j++)
            sum += texture(uShadow, vec3(q.xy + vec2(i, j) * px * 1.5, q.z - 0.0006));
    return sum / 9.0;
}
void main() {
    vec2 uv = vUV;
    vec3 n = normalize(vN);
    if ((vF & 32) != 0) {
        if (abs(n.y) > 0.5) uv = vW.xz; else uv = vec2(vW.x + vW.z, -vW.y);
    }
    if ((vF & 16) != 0) uv = vW.xz * 0.5 + vec2(uTime * 0.04, uTime * 0.09);
    vec4 tx = texture(uTexArr, vec3(uv, float(vL)));
    if ((vF & 4) != 0 && tx.a < 0.5) discard;
    float face = n.y > 0.5 ? 1.0 : (n.y < -0.5 ? 0.55 : (abs(n.x) > 0.5 ? 0.78 : 0.9));
    vec3 col;
    float alpha = (vF & 2) != 0 ? tx.a : 1.0;
    if (uHand == 1) {
        col = tx.rgb * uHandLight * face;
        if ((vF & 1) != 0) col = tx.rgb * 1.1;
        frag = vec4(col, 1.0);
        return;
    }
    vec2 lv = texture(uLV, (vW + n * 0.5 - uLVo) / uLVs).rg;
    float sky = lv.g;
    float bl = lv.r;
    float ndl = max(dot(n, uLightDir), 0.0);
    float sh = ndl > 0.0 ? shadowAt(vW, n) : 0.0;
    vec3 light = uAmb * face * (0.05 + 0.95 * pow(sky, 1.4)) + uLightCol * ndl * sh + uFlash * face * sky;
    light += vec3(1.0, 0.72, 0.42) * pow(bl, 1.6) * 1.7 * (1.0 - 0.7 * uDay * sky);
    col = tx.rgb * light;
    if ((vF & 1) != 0) col = tx.rgb * 1.15;
    if ((vF & 8) != 0) {
        col = mix(col, vec3(1.0, 0.70, 0.32) * 1.15, uGlow * 0.9);
        alpha = mix(alpha, 0.94, uGlow);
    }
    if ((vF & 16) != 0) {
        vec3 v = normalize(vW - uCam);
        vec3 r = reflect(v, n);
        float fres = pow(1.0 - max(dot(-v, n), 0.0), 3.0);
        col = mix(col, uFogCol * 0.9, fres * 0.5);
        col += uLightCol * pow(max(dot(r, uLightDir), 0.0), 80.0) * sh * 1.2;
        alpha = mix(alpha, 0.95, fres);
    }
    float d = length(vW - uCam);
    float fog = clamp((d - uFogNear) / (uFogFar - uFogNear), 0.0, 1.0);
    col = mix(col, uFogCol, fog);
    frag = vec4(col, alpha);
}
"""

FS_SHADOW = """
#version 330
in vec3 vW; in vec3 vN; in vec2 vUV; flat in int vL; flat in int vF;
uniform sampler2DArray uTexArr;
void main() {
    if ((vF & 4) != 0 && texture(uTexArr, vec3(vUV, float(vL))).a < 0.5) discard;
}
"""

VS_SCREEN = """
#version 330
in vec2 in_p; out vec2 vP;
void main() { vP = in_p; gl_Position = vec4(in_p, 0.9999, 1.0); }
"""

FS_SKY = """
#version 330
in vec2 vP;
uniform mat4 uInvVP; uniform vec3 uCam; uniform vec3 uSun; uniform vec3 uMoon;
uniform vec3 uZenith; uniform vec3 uHorizon; uniform vec3 uGlowCol; uniform float uNight; uniform float uStorm;
out vec4 frag;
float hash(vec3 p) { return fract(sin(dot(p, vec3(12.9898, 78.233, 37.719))) * 43758.5453); }
void main() {
    vec4 a = uInvVP * vec4(vP, 1.0, 1.0);
    vec3 dir = normalize(a.xyz / a.w - uCam);
    float h = dir.y;
    vec3 col = mix(uHorizon, uZenith, pow(clamp(h, 0.0, 1.0), 0.5));
    if (h < 0.0) col = uHorizon * mix(1.0, 0.75, clamp(-h * 4.0, 0.0, 1.0));
    float sd = max(dot(dir, uSun), 0.0);
    col += uGlowCol * pow(sd, 5.0) * (1.0 - clamp(h * 1.5, 0.0, 1.0));
    float vis = 1.0 - uStorm;
    vec3 t1 = normalize(cross(uSun, vec3(0.0, 0.0, 1.0)));
    vec3 t2 = cross(t1, uSun);
    if (dot(dir, uSun) > 0.0 && max(abs(dot(dir, t1)), abs(dot(dir, t2))) < 0.05)
        col = mix(col, vec3(1.0, 0.96, 0.75) * 1.4, vis);
    vec3 m1 = normalize(cross(uMoon, vec3(0.0, 0.0, 1.0)));
    vec3 m2 = cross(m1, uMoon);
    float mu = dot(dir, m1), mv = dot(dir, m2);
    if (dot(dir, uMoon) > 0.0 && max(abs(mu), abs(mv)) < 0.035) {
        float cr = hash(floor(vec3(mu, mv, 0.0) * 120.0));
        col = mix(col, vec3(0.86, 0.88, 0.95) * (cr > 0.75 ? 0.8 : 1.0), clamp(uNight * 1.5, 0.0, 1.0) * vis);
    }
    vec3 q = floor(dir * 220.0);
    if (h > 0.03 && hash(q) > 0.9975) col += vec3(0.85) * uNight * vis * (0.5 + 0.5 * hash(q + 7.0));
    frag = vec4(col, 1.0);
}
"""

VS_CLOUD = """
#version 330
in vec3 in_p; uniform mat4 uVP; out vec3 vW;
void main() { vW = in_p; gl_Position = uVP * vec4(in_p, 1.0); }
"""

FS_CLOUD = """
#version 330
in vec3 vW; uniform float uTime; uniform vec3 uCam; uniform vec3 uCloudCol; uniform vec3 uFogCol; uniform float uCover;
out vec4 frag;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
void main() {
    vec2 p = vW.xz + vec2(uTime * 2.5, 0.0);
    vec2 cell = floor(p / 12.0);
    float n = vnoise(cell * 0.21) * 0.7 + vnoise(cell * 0.63 + 13.0) * 0.3;
    if (n < 0.57 - uCover) discard;
    float d = length(vW.xz - uCam.xz);
    float fade = 1.0 - smoothstep(380.0, 780.0, d);
    frag = vec4(mix(uCloudCol, uFogCol, smoothstep(150.0, 700.0, d)), (0.82 + 0.15 * uCover) * fade);
}
"""

FS_FADE = """
#version 330
uniform vec4 uCol; out vec4 frag;
void main() { frag = uCol; }
"""


def cube_mesh():
    faces = [((0, 1, 0), 0), ((0, -1, 0), 1), ((1, 0, 0), 2), ((-1, 0, 0), 2), ((0, 0, 1), 3), ((0, 0, -1), 2)]
    out = []
    for n, fi in faces:
        n = np.array(n, float)
        if abs(n[1]) > 0.5:
            a, bv = np.array([1, 0, 0.]), np.array([0, 0, 1.])
        else:
            a, bv = np.cross([0, 1, 0], n), np.array([0, 1, 0.])
        quad = [n * 0.5 + a * 0.5 * su + bv * 0.5 * sv for su, sv in [(-1, -1), (1, -1), (1, 1), (-1, 1)]]
        tris = [(0, 1, 2), (0, 2, 3)]
        if np.dot(np.cross(quad[1] - quad[0], quad[2] - quad[0]), n) < 0:
            tris = [(0, 2, 1), (0, 3, 2)]
        for tri in tris:
            for k in tri:
                p = quad[k]
                uv = (p[0] + 0.5, p[2] + 0.5) if abs(n[1]) > 0.5 else (np.dot(p, a) + 0.5, 0.5 - p[1])
                out.append([*p, *n, *uv, fi])
    return np.array(out, np.float32)


def perspective(fovy, aspect, n, f):
    t = 1 / math.tan(math.radians(fovy) / 2)
    M = np.zeros((4, 4))
    M[0, 0] = t / aspect; M[1, 1] = t
    M[2, 2] = (f + n) / (n - f); M[2, 3] = 2 * f * n / (n - f); M[3, 2] = -1
    return M


def look_at(eye, tgt, up=(0, 1, 0)):
    eye, tgt = np.asarray(eye, float), np.asarray(tgt, float)
    f = norm(tgt - eye)
    s = np.cross(f, up)
    if np.linalg.norm(s) < 1e-6:
        s = np.cross(f, (0, 0, 1))
    s = norm(s)
    u = np.cross(s, f)
    M = np.eye(4)
    M[0, :3], M[1, :3], M[2, :3] = s, u, -f
    M[:3, 3] = -M[:3, :3] @ eye
    return M


def ortho(ext, n, f):
    M = np.eye(4)
    M[0, 0] = M[1, 1] = 1 / ext
    M[2, 2] = -2 / (f - n); M[2, 3] = -(f + n) / (f - n)
    return M


def mbytes(M):
    return M.T.astype(np.float32).tobytes()


def sky_state(theta, storm=0.0):
    sd = norm([math.cos(theta), 0.85 * math.sin(theta), 0.5])
    md = norm([-math.cos(theta), -0.85 * math.sin(theta), 0.5])
    e = sd[1]
    day = smoothstep(-0.10, 0.30, e)
    twi = 1.0 - smoothstep(0.02, 0.42, abs(e))
    near = smoothstep(-0.28, 0.02, e)
    zen = lerp(np.array([0.012, 0.018, 0.06]), np.array([0.33, 0.55, 0.95]), day)
    hor = lerp(np.array([0.035, 0.05, 0.12]), np.array([0.68, 0.80, 0.97]), day)
    sunset = np.array([0.98, 0.55, 0.30])
    hor = lerp(hor, sunset, twi * 0.75 * near)
    zen = lerp(zen, np.array([0.28, 0.32, 0.62]), twi * 0.4 * near)
    glow = sunset * twi * 0.6 * near
    amb = lerp(np.array([0.18, 0.19, 0.30]), np.array([0.68, 0.70, 0.76]), day)
    amb = lerp(amb, np.array([0.55, 0.42, 0.38]), twi * 0.35 * day)
    if e > -0.03:
        L = sd
        col = lerp(np.array([1.0, 0.55, 0.28]), np.array([1.0, 0.96, 0.86]), smoothstep(0.0, 0.45, e))
        col = col * 0.50 * smoothstep(-0.03, 0.12, e)
    else:
        L = md
        col = np.array([0.16, 0.19, 0.30]) * smoothstep(0.03, 0.2, -e)
    night = 1 - smoothstep(-0.18, 0.06, e)
    cloud = lerp(np.array([0.12, 0.13, 0.2]), np.array([1, 1, 1.0]), day)
    cloud = lerp(cloud, np.array([1.0, 0.75, 0.6]), twi * 0.5 * day)
    if storm > 0:
        gray = np.array([0.36, 0.38, 0.42]) * (0.25 + 0.75 * day)
        zen = lerp(zen, gray * 0.8, storm)
        hor = lerp(hor, gray, storm)
        glow = glow * (1 - storm)
        col = col * (1 - 0.85 * storm)
        amb = amb * (1 - 0.3 * storm)
        cloud = lerp(cloud, gray * 0.75, storm)
    return dict(sun=sd, moon=md, zen=zen, hor=hor, glow=glow, amb=amb, L=L, Lcol=col,
                night=night, cloud=cloud, elev=e, day=day)


# --------------------------------------------------------------------------
# Text overlay (pixel font, upper case)
# --------------------------------------------------------------------------
GLYPHS = {
    'A': [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    'B': ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "],
    'C': [" ### ", "#   #", "#    ", "#    ", "#    ", "#   #", " ### "],
    'D': ["#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "],
    'E': ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
    'F': ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "],
    'G': [" ### ", "#   #", "#    ", "# ###", "#   #", "#   #", " ### "],
    'H': ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    'I': ["###", " # ", " # ", " # ", " # ", " # ", "###"],
    'J': ["    #", "    #", "    #", "    #", "#   #", "#   #", " ### "],
    'K': ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    'L': ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
    'M': ["#   #", "## ##", "# # #", "#   #", "#   #", "#   #", "#   #"],
    'N': ["#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"],
    'O': [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    'P': ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "],
    'Q': [" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"],
    'R': ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
    'S': [" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "],
    'T': ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    'U': ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    'V': ["#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "],
    'W': ["#   #", "#   #", "#   #", "#   #", "# # #", "## ##", "#   #"],
    'X': ["#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"],
    'Y': ["#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "],
    'Z': ["#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"],
    '0': [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
    '1': [" # ", "## ", " # ", " # ", " # ", " # ", "###"],
    '2': [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
    '3': ["#### ", "    #", "    #", " ### ", "    #", "    #", "#### "],
    '4': ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
    '5': ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "],
    '6': [" ### ", "#    ", "#    ", "#### ", "#   #", "#   #", " ### "],
    '7': ["#####", "    #", "   # ", "  #  ", "  #  ", "  #  ", "  #  "],
    '8': [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    '9': [" ### ", "#   #", "#   #", " ####", "    #", "    #", " ### "],
    "'": ["#", "#", " ", " ", " ", " ", " "],
    '-': ["   ", "   ", "   ", "###", "   ", "   ", "   "],
    '!': ["#", "#", "#", "#", "#", " ", "#"],
    '?': [" ### ", "#   #", "    #", "   # ", "  #  ", "     ", "  #  "],
    ':': [" ", "#", " ", " ", " ", "#", " "],
    '.': [" ", " ", " ", " ", " ", " ", "#"],
    ',': [" ", " ", " ", " ", " ", "#", "#"],
    '&': [" ##  ", "#  # ", "#  # ", " ##  ", "# # #", "#  # ", " ## #"],
    '+': ["     ", "  #  ", "  #  ", "#####", "  #  ", "  #  ", "     "],
    '/': ["    #", "    #", "   # ", "  #  ", " #   ", "#    ", "#    "],
    '|': ["#", "#", "#", "#", "#", "#", "#"],
    '>': ["#   ", " #  ", "  # ", "   #", "  # ", " #  ", "#   "],
    ' ': ["   "] * 7,
}
_mask_cache = {}


def text_mask(text, scale):
    key = (text, scale)
    m = _mask_cache.get(key)
    if m is None:
        cols = []
        for ch in text.upper():
            g = GLYPHS.get(ch, GLYPHS[' '])
            cols.append(np.array([[c == '#' for c in row] for row in g], bool))
            cols.append(np.zeros((7, 1), bool))
        m = np.concatenate(cols, 1)
        m = np.pad(m, ((0, 1), (0, 1)))
        m = np.repeat(np.repeat(m, scale, 0), scale, 1)
        if len(_mask_cache) > 600:
            _mask_cache.clear()
        _mask_cache[key] = m
    return m


def _blend(img, mask, x0, y0, col, alpha):
    H, W, _ = img.shape
    h, w = mask.shape
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if xa >= xb or ya >= yb:
        return
    sub = img[ya:yb, xa:xb]
    mk = mask[ya - y0:yb - y0, xa - x0:xb - x0]
    if alpha >= 0.999:
        sub[mk] = np.asarray(col).astype(np.uint8)
    else:
        sub[mk] = (sub[mk] * (1 - alpha) + np.asarray(col) * alpha).astype(np.uint8)


def draw_text(img, text, x, y, scale, color=(255, 255, 255), alpha=1.0, anchor='c'):
    if alpha <= 0.01:
        return
    m = text_mask(text, scale)
    h, w = m.shape
    if anchor == 'c':
        x0, y0 = int(x - w / 2), int(y - h / 2)
    elif anchor == 'r':
        x0, y0 = int(x - w), int(y)
    else:
        x0, y0 = int(x), int(y)
    col = np.array(color, np.float32)
    _blend(img, m, x0 + scale, y0 + scale, col * 0.25, alpha)
    _blend(img, m, x0, y0, col, alpha)


def panel(img, x0, y0, x1, y1, alpha, color=(0, 0, 0)):
    if alpha <= 0.01:
        return
    H, W, _ = img.shape
    sub = img[max(y0, 0):min(y1, H), max(x0, 0):min(x1, W)]
    sub[:] = (sub * (1 - alpha) + np.array(color) * alpha).astype(np.uint8)


def text_width(text, scale):
    return text_mask(text, scale).shape[1]


def env(t, a, b, fade=0.5):
    if t < a or t > b:
        return 0.0
    return min(1.0, (t - a) / fade, (b - t) / fade)


HEART = ["  ## ##  ", " ####### ", "#########", "#########", " ####### ", "  #####  ", "   ###   ", "    #    "]


# --------------------------------------------------------------------------
# Audio (sound effects only)
# --------------------------------------------------------------------------
SR = 44100


def sfx_bank(rng):
    B = {}

    def lp(x, k):
        return np.convolve(x, np.ones(k) / k, 'same') if k > 1 else x

    def tt(n):
        return np.arange(n) / SR

    def env_(n, dec, att=0.002):
        t = tt(n)
        return np.minimum(1, t / att) * np.exp(-t * dec)

    def grains(n, density, k):
        g = np.zeros(n)
        idx = rng.integers(0, n, int(density * n / SR))
        g[idx] = rng.uniform(-1, 1, len(idx))
        return lp(g, k) * k ** 0.5

    def mat(name, dur, dec, nk, tone, tamt, tdec, gr=0.0, gk=3, extra=None):
        out = []
        for v in range(5):
            n = int(dur * SR)
            t = tt(n)
            f = tone * rng.uniform(0.88, 1.12)
            s = lp(rng.normal(size=n), nk) * env_(n, dec) * 0.8
            if tamt:
                s += tamt * np.sin(2 * np.pi * f * t) * env_(n, tdec)
                s += tamt * 0.4 * np.sin(2 * np.pi * f * 2.03 * t) * env_(n, tdec * 1.5)
            if gr:
                s += grains(n, gr, gk) * env_(n, dec * 0.7) * 0.6
            if extra:
                s += extra(t, n)
            out.append(s / (np.max(np.abs(s)) + 1e-9))
        B[name] = out

    mat('stone0', 0.13, 38, 2, 170, 0.5, 55, gr=2500, gk=2)
    mat('stone1', 0.22, 22, 2, 140, 0.6, 35, gr=5000, gk=2)
    mat('wood0', 0.14, 40, 5, 230, 1.0, 32)
    mat('wood1', 0.22, 24, 4, 190, 1.0, 22, gr=1500, gk=4)
    mat('grass0', 0.18, 24, 3, 0, 0, 0, gr=5000, gk=3)
    mat('grass1', 0.24, 18, 3, 0, 0, 0, gr=8000, gk=3)
    mat('gravel0', 0.2, 22, 2, 0, 0, 0, gr=9000, gk=2)
    mat('gravel1', 0.26, 16, 2, 0, 0, 0, gr=12000, gk=2)
    mat('wool0', 0.12, 32, 14, 0, 0, 0)
    mat('wool1', 0.16, 26, 12, 0, 0, 0)
    glass = lambda t, n: (np.sin(2 * np.pi * 2900 * t) + 0.6 * np.sin(2 * np.pi * 4300 * t)) * np.exp(-t * 16) * 0.8
    mat('glass0', 0.3, 50, 1, 0, 0, 0, extra=glass)
    mat('glass1', 0.45, 20, 1, 0, 0, 0, gr=9000, gk=1, extra=glass)
    metal = lambda t, n: (np.sin(2 * np.pi * 1250 * t) + 0.5 * np.sin(2 * np.pi * 1875 * t)) * np.exp(-t * 7)
    mat('metal0', 0.5, 60, 2, 0, 0, 0, extra=metal)
    mat('metal1', 0.5, 40, 2, 0, 0, 0, extra=metal)

    def water(t, n):
        s = np.zeros(n)
        for _ in range(9):
            t0 = rng.uniform(0, 0.25)
            m = t >= t0
            u = t[m] - t0
            f = rng.uniform(300, 700) * (1 + 3 * u)
            s[m] += np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-u * 30)
        return s
    mat('water0', 0.4, 30, 6, 0, 0, 0, extra=water)
    mat('water1', 0.4, 30, 6, 0, 0, 0, extra=water)

    def one(name, s):
        B[name] = [s / (np.max(np.abs(s)) + 1e-9)]

    n = int(0.2 * SR); t = tt(n)
    one('swing', lp(rng.normal(size=n), 6) * np.sin(np.pi * np.minimum(t / 0.2, 1)) ** 2)
    n = int(0.25 * SR); t = tt(n)
    one('hit', np.sin(2 * np.pi * 95 * t) * np.exp(-t * 22) + lp(rng.normal(size=n), 3) * np.exp(-t * 35) * 0.7)
    n = int(1.0 * SR); t = tt(n)
    f0 = 78 + 6 * np.sin(2 * np.pi * 4.5 * t)
    ph = np.cumsum(f0) / SR
    saw = 2 * (ph % 1) - 1
    g = lp(saw, 18) * np.minimum(1, t / 0.12) * np.exp(-np.maximum(t - 0.5, 0) * 6)
    one('groan', g + lp(rng.normal(size=n), 30) * 0.15 * np.exp(-t * 3))
    n = int(0.28 * SR); t = tt(n)
    f0 = 150 * (1 - 0.25 * t / 0.28)
    pulse = (np.sin(2 * np.pi * np.cumsum(f0) / SR) > 0.6).astype(float)
    one('hurt', lp(pulse, 10) * np.exp(-t * 9) * np.minimum(1, t / 0.01))
    n = int(0.5 * SR); t = tt(n)
    one('poof', lp(rng.normal(size=n), 25) * np.exp(-t * 9))
    n = int(4.0 * SR); t = tt(n)
    th = lp(rng.normal(size=n), 220) * np.exp(-t * 0.9) * (1 + 0.6 * np.sin(2 * np.pi * 0.7 * t))
    th[:int(0.25 * SR)] += lp(rng.normal(size=int(0.25 * SR)), 3) * np.exp(-t[:int(0.25 * SR)] * 12) * 0.03
    one('thunder', th)
    n = int(1.6 * SR); t = tt(n)
    ch = np.zeros(n)
    for i, f in enumerate([1046, 1318, 1568, 2093]):
        m = t >= i * 0.09
        u = t[m] - i * 0.09
        ch[m] += np.sin(2 * np.pi * f * u) * np.exp(-u * 4)
    one('chime', ch)
    n = int(0.9 * SR); t = tt(n)
    f = 260 + 140 * np.sin(np.pi * t / 0.9)
    one('door', np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * lp(rng.normal(size=n), 2) * 0.3 * np.sin(np.pi * t / 0.9)
        + np.sin(2 * np.pi * 70 * t) * np.exp(-np.maximum(t - 0.75, 0) * 30) * (t > 0.75))
    n = int(1.2 * SR); t = tt(n)
    one('splash', lp(rng.normal(size=n), 5) * np.exp(-t * 3.5) + water(t, n) * 0.5)
    n = int(0.9 * SR); t = tt(n)
    f = 900 + 1400 * t
    one('launch', np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t * 4) * (1 - t / 0.9))
    n = int(2.2 * SR); t = tt(n)
    boom = lp(rng.normal(size=n), 80) * np.exp(-t * 3.5) * 1.6 + np.sin(2 * np.pi * 55 * t) * np.exp(-t * 6) * 0.25
    cr = np.zeros(n)
    idx = rng.integers(int(0.3 * SR), n, 160)
    cr[idx] = rng.uniform(-1, 1, 160) * 0.5
    cr = np.convolve(cr, np.exp(-np.arange(120) / 20), 'same') * np.exp(-t * 1.2)
    one('boom', boom + cr)
    B['step_grass'] = [s * 0.6 for s in B['grass0']]
    B['step_wood'] = [s * 0.6 for s in B['wood0']]
    return B


def synth_audio(path, dur, S, steps):
    rng = np.random.default_rng(3)
    B = sfx_bank(rng)
    n = int((dur + 3) * SR)
    L = np.zeros(n)
    R = np.zeros(n)

    def add(name, t0, vol, pan=0.5):
        if name not in B or t0 < 0:
            return
        s = B[name][rng.integers(0, len(B[name]))] * vol
        i = int(t0 * SR)
        if i >= n:
            return
        j = min(n, i + len(s))
        L[i:j] += s[:j - i] * math.sqrt(1 - pan)
        R[i:j] += s[:j - i] * math.sqrt(pan)

    # block sounds, rate-limited
    last = -1.0
    for (t, m, k) in sorted(S.snd_ev):
        if t - last < 0.1:
            continue
        last = t
        add(f'{m}{k}', t + rng.uniform(0, 0.02), 0.32 if k == 0 else 0.38, rng.uniform(0.35, 0.65))
    for (t, name, vol) in S.sfx:
        add(name, t, vol, rng.uniform(0.4, 0.6))
    for (t, mat) in steps:
        add('step_' + mat, t, 0.22, rng.uniform(0.4, 0.6))
    # rain bed
    st = np.array(S.storm)
    tt_ = np.arange(n) / SR
    sv = np.interp(tt_, st[:, 0], st[:, 1])
    if sv.max() > 0:
        m = sv > 0.001
        k = int(m.sum())
        rain = np.convolve(rng.normal(size=k), np.ones(3) / 3, 'same') * 0.06
        drops = np.zeros(k)
        idx = rng.integers(0, k, k // 600)
        drops[idx] = rng.uniform(-1, 1, len(idx)) * 0.25
        drops = np.convolve(drops, np.exp(-np.arange(60) / 8), 'same')
        L[m] += (rain + drops) * sv[m]
        R[m] += (np.roll(rain, 777) + np.roll(drops, 391)) * sv[m]
    # fireplace crackle
    if S.fire_t is not None:
        a = int(S.fire_t * SR)
        b = int(S.fire_end * SR)
        k = b - a
        cr = np.zeros(k)
        idx = rng.integers(0, k, k // 1500)
        cr[idx] = rng.uniform(-1, 1, len(idx))
        cr = np.convolve(cr, np.exp(-np.arange(80) / 10), 'same') * 0.12
        cr += np.convolve(rng.normal(size=k), np.ones(40) / 40, 'same') * 0.05
        fade = np.minimum(1, np.minimum(np.arange(k), k - np.arange(k)) / (0.5 * SR))
        L[a:b] += cr * fade
        R[a:b] += np.roll(cr, 300) * fade
    out = np.stack([L, R])[:, :int(dur * SR)]
    out = np.tanh(out * 1.2) / np.tanh(1.2)
    out = out / max(1e-6, np.max(np.abs(out))) * 0.89
    fo = int(2.0 * SR)
    out[:, -fo:] *= np.linspace(1, 0, fo)
    pcm = (out.T * 32767).astype(np.int16)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# --------------------------------------------------------------------------
# Video
# --------------------------------------------------------------------------
HOTBAR = ['sword', 'pickaxe', 'axe', 'shovel', 'cobblestone', 'stone_bricks', 'oak_planks', 'glass', 'torch']


def build_instances(events):
    order = sorted(range(len(events)), key=lambda i: events[i][0])
    inst, names, cells, occ = [], [], [], {}
    for i in order:
        t, kind, cell, ty, c, s = events[i]
        if kind == 1:
            j = occ.pop(cell, None)
            if j is not None:
                inst[j][8] = t
            continue
        if cell is not None and cell in occ:
            inst[occ[cell]][8] = t
        inst.append([c[0], c[1], c[2], s[0], s[1], s[2], 0.0, t, INF, TYPES[ty]])
        names.append(ty)
        cells.append(cell)
        if cell is not None:
            occ[cell] = len(inst) - 1
    return np.array(inst, np.float32), names, cells


class Video:
    def __init__(self, W, H):
        self.W, self.H = W, H
        make_textures()
        make_types()
        t0 = time.time()
        S = self.S = build_story()
        self.T_END = S.T_END
        inst, names, cells = build_instances(S.ev)
        self.inst_all, self.names, self.cells = inst, names, cells
        print(f"events {len(S.ev)}  instances {len(inst)}  video {self.T_END:.1f}s  ({time.time() - t0:.1f}s)")
        self.seg_t0 = [s['t0'] for s in S.segs]
        self.theta_k = sorted(S.theta, key=lambda k: k[0])
        st = np.array(S.storm)
        self.storm_k = st[np.argsort(st[:, 0], kind='stable')]
        self.lightf = LightField(inst, names, cells, S.lights)
        rem = S.rem
        self.rem_t = np.array([r[0] for r in rem])
        self.rem_c = np.array([r[1] for r in rem])
        self.rem_ty = [r[2] for r in rem]
        self.res_t = {k: np.sort(np.array(v)) for k, v in S.res.items()}
        self.swings = np.sort(np.array(S.swings)) if S.swings else np.zeros(0)
        self.hurts = sorted(S.hurts)
        self.solid_cells = {}
        for j, c in enumerate(cells):
            if c is not None and names[j] not in ('torch', 'flower_red', 'flower_yellow', 'water', 'gravel', 'fence'):
                self.solid_cells.setdefault(c, []).append((inst[j][7], inst[j][8]))
        blend_ids = {TYPES[n] for n in BLEND_TYPES}
        is_blend = np.isin(inst[:, 9].astype(int), list(blend_ids))
        self.inst_op = inst[~is_blend]
        self.inst_bl = inst[is_blend]
        self.cuts = self.jump_cuts()
        self.precompute_camera()
        self.init_gl()
        self.lv_time = None

    # ---------------- segment / timeline helpers ----------------
    def seg_at(self, t):
        i = max(bisect.bisect_right(self.seg_t0, t) - 1, 0)
        return self.S.segs[i]

    def theta_at(self, t):
        k = self.theta_k
        ts = [a for a, b in k]
        i = bisect.bisect_right(ts, t) - 1
        if i < 0:
            return k[0][1]
        if i >= len(k) - 1:
            return k[-1][1]
        a0, b0 = k[i]
        a1, b1 = k[i + 1]
        return b0 if a1 <= a0 else lerp(b0, b1, (t - a0) / (a1 - a0))

    def storm_at(self, t):
        return float(np.interp(t, self.storm_k[:, 0], self.storm_k[:, 1]))

    def occupied(self, p, t):
        for dx, dy, dz in ((0, 0, 0), (0.25, 0, 0), (-0.25, 0, 0), (0, 0, 0.25), (0, 0, -0.25), (0, -0.3, 0), (0, 0.2, 0)):
            c = (int(math.floor(p[0] + dx)), int(math.floor(p[1] + dy)), int(math.floor(p[2] + dz)))
            for (a, b) in self.solid_cells.get(c, ()):
                if a <= t < b:
                    return True
            if c[1] <= 0:
                x, z = c[0], c[2]
                m = max(abs(x), abs(z))
                hole = (33 <= m <= 40) or (QX0 <= x <= QX1 and QZ0 <= z <= QZ1)
                if not hole:
                    return True
        return False

    def precompute_camera(self):
        n = int(self.T_END * FPS) + 2
        self.n_frames = n
        eye = np.zeros((n, 3))
        look = np.zeros((n, 3))
        te = np.zeros(n)
        tl = np.zeros(n)
        cut = np.zeros(n, bool)
        prev_seg = None
        last_e, last_l = np.array([0, 10, 60.0]), np.zeros(3)
        for f in range(n):
            t = f / FPS
            sg = self.seg_at(t)
            e, l = raw_cam(sg, t)
            if e is None:
                e, l = last_e, last_l
            eye[f], look[f] = e, l
            last_e, last_l = e, l
            k = sg['kind']
            te[f], tl[f] = {'build': (0.8, 0.22), 'work': (0.35, 0.15), 'fight': (0.0, 0.14)}.get(k, (0.0, 0.0))
            if prev_seg is not None and sg is not prev_seg and (k == 'card' or prev_seg['kind'] == 'card' or
                                                               any(abs(sg['t0'] - c) < 1e-6 for c in self.cuts)):
                cut[f] = True
            prev_seg = sg

        def smooth(x, tau):
            y = x.copy()
            a = np.where(tau > 0, 1 - np.exp(-1 / (FPS * np.maximum(tau, 1e-6))), 1.0)
            for i in range(1, len(y)):
                if not cut[i]:
                    y[i] = y[i - 1] + (y[i] - y[i - 1]) * a[i]
            for i in range(len(y) - 2, -1, -1):
                if not cut[i + 1]:
                    y[i] = y[i + 1] + (y[i] - y[i + 1]) * a[i]
            return y

        eye = smooth(eye, te)
        look = smooth(look, tl)
        offs = [(0, 0, 0)]
        for r in range(1, 4):
            for dx in range(-r, r + 1):
                for dy in range(-1, r + 1):
                    for dz in range(-r, r + 1):
                        if max(abs(dx), abs(dy), abs(dz)) == r:
                            offs.append((dx, dy, dz))
        offs.sort(key=lambda o: math.sqrt(o[0] ** 2 + o[1] ** 2 + o[2] ** 2) - 0.4 * o[1])
        fix = np.zeros((n, 3))
        for f in range(n):
            t = f / FPS
            sg = self.seg_at(t)
            if sg['kind'] == 'card':
                continue
            tt = INTRO_T if sg['final'] else t
            if not self.occupied(eye[f], tt):
                continue
            for o in offs[1:]:
                q = eye[f] + np.array(o, float)
                if not self.occupied(q, tt):
                    fix[f] = o
                    break
        fix = smooth(fix, np.full(n, 0.25))
        self.eye = eye + fix
        self.look = look
        # walking bob + footsteps
        self.bob = np.zeros(n)
        self.steps = []
        dist = 0.0
        for f in range(1, n):
            t = f / FPS
            sg = self.seg_at(t)
            if sg['kind'] in ('path', 'work', 'fight') and (sg['walk'] or sg['kind'] == 'work'):
                d = float(np.hypot(*(self.eye[f, [0, 2]] - self.eye[f - 1, [0, 2]])))
                if d > 0.01:
                    dist += d
                    self.bob[f] = abs(math.sin(dist * 1.8)) * 0.07
                    if dist > 1.75:
                        dist = 0.0
                        if not sg['tl']:
                            inside = abs(self.eye[f, 0]) < 13 and -19 < self.eye[f, 2] < 1
                            self.steps.append((t, 'wood' if inside else 'grass'))
        self.S.fire_end = self.T_END - 26.0

    # ---------------- GL setup ----------------
    def init_gl(self):
        ctx = self.ctx = moderngl.create_standalone_context(require=330)
        W, H = self.W, self.H
        self.fbo_ms = ctx.framebuffer([ctx.renderbuffer((W, H), 4, samples=4)],
                                      ctx.depth_renderbuffer((W, H), samples=4))
        self.fbo_rs = ctx.framebuffer([ctx.renderbuffer((W, H), 4)])
        self.shadow_tex = ctx.depth_texture((4096, 4096))
        self.shadow_tex.compare_func = '<='
        self.shadow_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.shadow_tex.repeat_x = self.shadow_tex.repeat_y = False
        self.fbo_sh = ctx.framebuffer(depth_attachment=self.shadow_tex)
        data = np.stack(TEX_LIST)
        self.tex_arr = ctx.texture_array((16, 16, len(TEX_LIST)), 4, data.tobytes())
        self.tex_arr.build_mipmaps()
        self.tex_arr.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.NEAREST)
        self.tex_arr.anisotropy = 8.0
        nx, ny, nz = (int(v) for v in LV_N)
        self.lv_tex = ctx.texture3d((nx, ny, nz), 2, np.zeros((nz, ny, nx, 2), np.uint8).tobytes())
        self.lv_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.lv_tex.repeat_x = self.lv_tex.repeat_y = self.lv_tex.repeat_z = False

        self.p_main = ctx.program(vertex_shader=VS_BLOCK, fragment_shader=FS_BLOCK)
        self.p_shadow = ctx.program(vertex_shader=VS_BLOCK, fragment_shader=FS_SHADOW)
        self.p_sky = ctx.program(vertex_shader=VS_SCREEN, fragment_shader=FS_SKY)
        self.p_fade = ctx.program(vertex_shader=VS_SCREEN, fragment_shader=FS_FADE)
        self.p_cloud = ctx.program(vertex_shader=VS_CLOUD, fragment_shader=FS_CLOUD)
        assert len(TYPE_TEX) <= 96
        ttab = np.zeros((96, 4), np.int32)
        ttab[:len(TYPE_TEX)] = TYPE_TEX
        ftab = np.zeros(96, np.int32)
        ftab[:len(TYPE_FLAGS)] = TYPE_FLAGS
        for p in (self.p_main, self.p_shadow):
            p['uTex'].write(ttab.tobytes())
            p['uFlags'].write(ftab.tobytes())
            p['uTexArr'] = 0
        self.p_main['uShadow'] = 1
        self.p_main['uLV'] = 2
        self.p_main['uLVo'] = tuple(float(v) for v in LV_O)
        self.p_main['uLVs'] = tuple(float(v) for v in LV_N)

        cube = ctx.buffer(cube_mesh().tobytes())
        self.ib_op = ctx.buffer(self.inst_op.tobytes())
        self.ib_bl = ctx.buffer(self.inst_bl.tobytes())
        self.ib_dyn = ctx.buffer(reserve=8000 * 40)
        self.ib_dynb = ctx.buffer(reserve=3000 * 40)
        self.ib_hand = ctx.buffer(reserve=16 * 40)
        ifmt = '3f 3f 1f 1f 1f 1f/i'
        inames = ['i_c', 'i_s', 'i_yaw', 'i_t0', 'i_t1', 'i_type']

        def vao(prog, ib, shadow=False):
            if shadow:
                return ctx.vertex_array(prog, [(cube, '3f 12x 2f 1f', 'in_pos', 'in_uv', 'in_face'), (ib, ifmt, *inames)])
            return ctx.vertex_array(prog, [(cube, '3f 3f 2f 1f', 'in_pos', 'in_norm', 'in_uv', 'in_face'), (ib, ifmt, *inames)])

        self.vao_op = vao(self.p_main, self.ib_op)
        self.vao_bl = vao(self.p_main, self.ib_bl)
        self.vao_dyn = vao(self.p_main, self.ib_dyn)
        self.vao_dynb = vao(self.p_main, self.ib_dynb)
        self.vao_hand = vao(self.p_main, self.ib_hand)
        self.vao_sh_op = vao(self.p_shadow, self.ib_op, True)
        self.vao_sh_dyn = vao(self.p_shadow, self.ib_dyn, True)
        tri = ctx.buffer(np.array([-1, -1, 3, -1, -1, 3], np.float32).tobytes())
        self.vao_sky = ctx.vertex_array(self.p_sky, [(tri, '2f', 'in_p')])
        self.vao_fade = ctx.vertex_array(self.p_fade, [(tri, '2f', 'in_p')])
        Sz = 900.0
        self.cloud_q = np.array([[-Sz, 128, -Sz], [Sz, 128, -Sz], [Sz, 128, Sz], [-Sz, 128, -Sz], [Sz, 128, Sz], [-Sz, 128, Sz]], np.float32)
        self.cloud_buf = ctx.buffer(reserve=self.cloud_q.nbytes)
        self.vao_cloud = ctx.vertex_array(self.p_cloud, [(self.cloud_buf, '3f', 'in_p')])
        self.icons = {}

    def update_light(self, t_sched, force=False):
        if not force and self.lv_time is not None and abs(t_sched - self.lv_time) < 0.5:
            return
        data = self.lightf.compute(t_sched)
        self.lv_tex.write(data.tobytes())
        self.lv_time = t_sched

    # ---------------- per-frame dynamic content ----------------
    def held_and_swing(self, sg, t):
        k = sg['kind']
        if k in ('build', 'work') and len(sg['times']):
            T = sg['times']
            i = int(np.clip(np.searchsorted(T, t) - 1, 0, len(T) - 1))
            item = sg['items'][i]
            active = T[0] - 0.2 <= t <= T[-1] + 0.2
            if not active:
                return item, 0.0
            if sg['tl']:
                return item, abs(math.sin(t * 9.0))
            dt = t - T[max(np.searchsorted(T, t) - 1, 0)]
            return item, math.sin(math.pi * min(max(dt / 0.3, 0), 1)) if dt < 0.3 else 0.0
        if k == 'fight':
            j = np.searchsorted(self.swings, t) - 1
            if j >= 0 and t - self.swings[j] < 0.3:
                return 'sword', math.sin(math.pi * (t - self.swings[j]) / 0.3)
            return 'sword', 0.0
        return sg.get('item', 'none'), 0.0

    def dyn_instances(self, t, eye, sched_t, sg):
        out = []
        blend = []
        # block-break particles
        a = np.searchsorted(self.rem_t, t - 0.6)
        b = np.searchsorted(self.rem_t, t)
        idx = np.arange(a, b)
        if len(idx) > 80:
            idx = idx[np.linspace(0, len(idx) - 1, 80).astype(int)]
        for i in idx:
            dt = t - self.rem_t[i]
            c = self.rem_c[i]
            ty = TYPES[self.rem_ty[i]]
            for k in range(5):
                h = (i * 7919 + k * 104729) % 1000 / 1000.0
                h2 = (i * 3571 + k * 7741) % 1000 / 1000.0
                h3 = (i * 1231 + k * 3001) % 1000 / 1000.0
                v = np.array([(h - 0.5) * 3, 2.0 + h2 * 2, (h3 - 0.5) * 3])
                p = np.array(c) + v * dt + np.array([0, -9.0 * dt * dt, 0])
                sz = 0.14 * (1 - dt / 0.6)
                out.append([*p, sz, sz, sz, 0, -INF, INF, ty])
        # zombies
        for fs in self.S.fights:
            if not (fs['t0'] <= t <= fs['t1']):
                continue
            Pf = fs['P']
            for m in fs['mobs']:
                if t < m['start'] - 0.2:
                    continue
                if t >= m['death']:
                    dt = t - m['death']
                    if dt < 0.9:
                        pc, _ = mob_pos(m, m['death'])
                        for k in range(14):
                            h = (k * 7919) % 1000 / 1000.0
                            h2 = (k * 3571) % 1000 / 1000.0
                            p = pc + np.array([(h - 0.5) * 1.6 * (0.3 + dt), 0.6 + h2 * 1.4 + dt * 1.2, ((k * 37) % 10 / 10 - 0.5) * 1.6 * (0.3 + dt)])
                            sz = 0.35 * (1 - dt / 0.9)
                            out.append([*p, sz, sz, sz, 0, -INF, INF, TYPES['smoke']])
                    continue
                p, moving = mob_pos(m, t)
                d = Pf - p
                yaw = math.atan2(d[0], d[2])
                hurt = any(0 <= t - h < 0.3 for h in m['hits'])
                sfx = '_h' if hurt else ''
                c, s = math.cos(yaw), math.sin(yaw)
                sw = math.sin(t * 8) * 0.3 if moving else 0.0
                parts = [((0, 1.55, 0), (0.5, 0.5, 0.5), 'zhead'), ((0, 1.0, 0), (0.5, 0.65, 0.28), 'zbody'),
                         ((-0.37, 1.3, 0.32), (0.22, 0.22, 0.68), 'zarm'), ((0.37, 1.3, 0.32), (0.22, 0.22, 0.68), 'zarm'),
                         ((-0.13, 0.35, sw), (0.24, 0.68, 0.26), 'zleg'), ((0.13, 0.35, -sw), (0.24, 0.68, 0.26), 'zleg')]
                for lc, sz, ty in parts:
                    wv = np.array([c * lc[0] + s * lc[2], lc[1], -s * lc[0] + c * lc[2]])
                    out.append([*(p + wv), *sz, yaw, -INF, INF, TYPES[ty + sfx]])
        # fireworks
        flash = np.zeros(3)
        for fw in self.S.fireworks:
            if fw['tl'] <= t < fw['tb']:
                u = (t - fw['tl']) / (fw['tb'] - fw['tl'])
                p = np.array([fw['p'][0], lerp(12, fw['p'][1], 1 - (1 - u) ** 2), fw['p'][2]])
                out.append([*p, 0.35, 0.35, 0.35, 0, -INF, INF, TYPES['spark_gold']])
            dt = t - fw['tb']
            if 0 <= dt < 2.3:
                life = dt / 2.3
                disp = fw['sp'] * (1 - math.exp(-2.4 * dt)) / 2.4
                pts = fw['p'] + fw['dirs'] * disp + np.array([0, -2.5 * dt * dt, 0])
                sz = 1.0 * (1 - life) ** 0.6
                for i, q in enumerate(pts):
                    if life > 0.6 and (i * 7 + int(t * 30)) % 3 == 0:
                        continue
                    ty = fw['col'] if i % 3 else fw['col2']
                    out.append([*q, sz, sz, sz, 0, -INF, INF, TYPES[ty]])
                colv = np.array(TEX_LIST[TEX[fw['col']]][0, 0, :3], float) / 255
                flash += colv * math.exp(-dt * 2.2) * 0.22
        # rain
        st = self.storm_at(t)
        if st > 0.02:
            nd = int(1400 * st)
            ii = np.arange(nd)
            hx = ((ii * 7919) % 1000) / 1000.0
            hz = ((ii * 6007) % 1000) / 1000.0
            hp = ((ii * 3203) % 1000) / 1000.0
            xs = eye[0] + ((hx * 36 - eye[0]) % 36) - 18
            zs = eye[2] + ((hz * 36 - eye[2]) % 36) - 18
            ys = eye[1] + 14 - ((t * 22 + hp * 30) % 30)
            for x, y, z in zip(xs, ys, zs):
                blend.append([x, y, z, 0.04, 0.8, 0.04, 0, -INF, INF, TYPES['rain']])
        return (np.array(out, np.float32).reshape(-1, 10), np.array(blend, np.float32).reshape(-1, 10), flash)

    def hand_instances(self, item, swing, t, bob):
        out = []
        s = swing
        ox = -0.12 * s
        oy = -0.16 * math.sin(math.pi * s) * 0.6 - 0.25 * s - bob * 0.4
        oz = -0.28 * s
        yaw = 0.25 * s
        c, sn = math.cos(0.15 + yaw), math.sin(0.15 + yaw)
        arm = np.array([0.62 + ox, -0.74 + oy, -1.05 + oz])
        out.append([*arm, 0.22, 0.22, 0.75, 0.15 + yaw, -INF, INF, TYPES['sleeve']])
        hand = arm + np.array([-sn * 0.48, 0.0, -c * 0.48])
        out.append([*hand, 0.2, 0.2, 0.22, 0.15 + yaw, -INF, INF, TYPES['skin']])
        if item in ('none', None, 'leaves'):
            return np.array(out, np.float32)
        hp = [0.46 + ox, -0.38 + oy, -1.25 + oz]
        if item in ITEMS:
            out.append([hp[0] + 0.02, hp[1] + 0.14, hp[2], 0.62, 0.62, 0.05, -0.55 + yaw, -INF, INF, TYPES[item]])
        elif item == 'torch':
            out.append([hp[0], hp[1] + 0.1, hp[2], 0.09, 0.45, 0.09, 0.0, -INF, INF, TYPES['torch']])
        elif item == 'fence':
            out.append([hp[0], hp[1] + 0.1, hp[2], 0.12, 0.45, 0.12, 0.0, -INF, INF, TYPES['fence']])
        elif item in TYPES:
            out.append([hp[0], hp[1], hp[2], 0.36, 0.36, 0.36, 0.7 + yaw, -INF, INF, TYPES[item]])
        return np.array(out, np.float32)

    # ---------------- rendering ----------------
    def render(self, t):
        ctx = self.ctx
        W, H = self.W, self.H
        sg = self.seg_at(t)
        f = min(int(round(t * FPS)), self.n_frames - 1)
        if sg['kind'] == 'card':
            img = np.zeros((H, W, 3), np.uint8)
            self.overlay(img, t, sg)
            return img
        sched = INTRO_T if sg['final'] else t
        self.update_light(sched, force=(self.lv_time is None or (self.lv_time > 1e6) != (sched > 1e6)))
        eye = self.eye[f].copy()
        eye[1] += self.bob[f]
        look = self.look[f].copy()
        for h in self.hurts:
            if 0 <= t - h < 0.35:
                k = (1 - (t - h) / 0.35) * 0.18
                eye += np.array([math.sin(t * 90) * k, math.cos(t * 70) * k * 0.6, 0])
        th = self.theta_at(t)
        storm = self.storm_at(t)
        sk = sky_state(th, storm)
        fov = 72.0
        V = look_at(eye, look)
        Pm = perspective(fov, W / H, 0.08, 1700)
        VP = Pm @ V
        dyn, dynb, flash = self.dyn_instances(t, eye, sched, sg)
        for lt in self.S.lightning:
            if 0 <= t - lt < 0.25:
                flash = flash + np.array([1.2, 1.2, 1.4]) * (1 - (t - lt) / 0.25) * (1 if (t - lt) < 0.06 or (t - lt) > 0.12 else 0.3)
        if len(dyn):
            self.ib_dyn.write(dyn[:8000].tobytes())
        if len(dynb):
            self.ib_dynb.write(dynb[:3000].tobytes())
        Ld = sk['L']
        center = np.array([-15, 18, -4.0])
        LV = look_at(center + Ld * 400, center, (0, 1, 0) if abs(Ld[1]) < 0.99 else (0, 0, 1))
        LVP = ortho(120, 1, 900) @ LV

        self.fbo_sh.use()
        self.fbo_sh.clear(depth=1.0)
        ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        ctx.disable(moderngl.BLEND)
        ctx.cull_face = 'front'
        self.tex_arr.use(0)
        self.p_shadow['uVP'].write(mbytes(LVP))
        self.p_shadow['uT'] = float(sched)
        self.vao_sh_op.render(moderngl.TRIANGLES, instances=len(self.inst_op))
        if len(dyn):
            self.vao_sh_dyn.render(moderngl.TRIANGLES, instances=min(len(dyn), 8000))

        self.fbo_ms.use()
        self.fbo_ms.clear(0, 0, 0, 1, depth=1.0)
        ctx.cull_face = 'back'
        ctx.disable(moderngl.DEPTH_TEST)
        ps = self.p_sky
        ps['uInvVP'].write(mbytes(np.linalg.inv(VP)))
        ps['uCam'] = tuple(eye)
        ps['uSun'] = tuple(sk['sun'])
        ps['uMoon'] = tuple(sk['moon'])
        ps['uZenith'] = tuple(sk['zen'] + flash * 0.25)
        ps['uHorizon'] = tuple(sk['hor'] + flash * 0.25)
        ps['uGlowCol'] = tuple(sk['glow'])
        ps['uNight'] = float(sk['night'])
        ps['uStorm'] = float(storm)
        self.vao_sky.render(moderngl.TRIANGLES)

        ctx.enable(moderngl.DEPTH_TEST)
        pm = self.p_main
        pm['uHand'] = 0
        pm['uVP'].write(mbytes(VP))
        pm['uT'] = float(sched)
        pm['uLightVP'].write(mbytes(LVP))
        pm['uLightDir'] = tuple(Ld)
        pm['uLightCol'] = tuple(sk['Lcol'])
        pm['uAmb'] = tuple(sk['amb'])
        pm['uDay'] = float(sk['day'])
        pm['uCam'] = tuple(eye)
        pm['uFogCol'] = tuple(sk['hor'])
        pm['uFogNear'] = 210.0 - 120 * storm
        pm['uFogFar'] = 620.0 - 380 * storm
        pm['uGlow'] = float(sk['night'])
        pm['uTime'] = float(t)
        pm['uFlash'] = tuple(flash)
        self.shadow_tex.use(1)
        self.lv_tex.use(2)
        self.vao_op.render(moderngl.TRIANGLES, instances=len(self.inst_op))
        if len(dyn):
            self.vao_dyn.render(moderngl.TRIANGLES, instances=min(len(dyn), 8000))

        ctx.enable(moderngl.BLEND)
        ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.fbo_ms.depth_mask = False
        ctx.disable(moderngl.CULL_FACE)
        cq = self.cloud_q.copy()
        cq[:, 0] += eye[0]
        cq[:, 2] += eye[2]
        self.cloud_buf.write(cq.tobytes())
        pc = self.p_cloud
        pc['uVP'].write(mbytes(VP))
        pc['uTime'] = float(t)
        pc['uCam'] = tuple(eye)
        pc['uCloudCol'] = tuple(sk['cloud'])
        pc['uFogCol'] = tuple(sk['hor'])
        pc['uCover'] = float(0.35 * storm)
        self.vao_cloud.render(moderngl.TRIANGLES)
        ctx.enable(moderngl.CULL_FACE)
        self.vao_bl.render(moderngl.TRIANGLES, instances=len(self.inst_bl))
        if len(dynb):
            self.vao_dynb.render(moderngl.TRIANGLES, instances=min(len(dynb), 3000))
        self.fbo_ms.depth_mask = True
        ctx.disable(moderngl.BLEND)

        # first-person hand
        if sg['hand']:
            item, swing = self.held_and_swing(sg, t)
            hi = self.hand_instances(item, swing, t, self.bob[f])
            self.ib_hand.write(hi.tobytes())
            ctx.disable(moderngl.DEPTH_TEST)
            ctx.enable(moderngl.CULL_FACE)
            bl, skv = self.lightf.sample(eye)
            hl = sk['amb'] * (0.08 + 0.92 * skv ** 1.4) + sk['Lcol'] * 0.6 * skv + np.array([1.0, 0.72, 0.42]) * bl ** 1.6 * 1.5 * (1 - 0.7 * sk['day'] * skv)
            pm['uHand'] = 1
            pm['uHandLight'] = tuple(np.minimum(hl + flash * 0.3, 1.4))
            pm['uVP'].write(mbytes(perspective(70, W / H, 0.05, 10)))
            pm['uT'] = 0.0
            self.vao_hand.render(moderngl.TRIANGLES, instances=len(hi))
            pm['uHand'] = 0

        fa = self.fade_alpha(t)
        if fa > 0:
            ctx.disable(moderngl.DEPTH_TEST)
            ctx.enable(moderngl.BLEND)
            self.p_fade['uCol'] = (0.0, 0.0, 0.0, float(fa))
            self.vao_fade.render(moderngl.TRIANGLES)
            ctx.disable(moderngl.BLEND)
        ctx.copy_framebuffer(self.fbo_rs, self.fbo_ms)
        raw = self.fbo_rs.read(components=3)
        img = np.frombuffer(raw, np.uint8).reshape(H, W, 3)[::-1].copy()
        for h in self.hurts:
            if 0 <= t - h < 0.5:
                panel(img, 0, 0, W, H, 0.35 * (1 - (t - h) / 0.5), (200, 0, 0))
        self.overlay(img, t, sg)
        return img

    def jump_cuts(self):
        segs = self.S.segs
        out = []
        for i in range(1, len(segs)):
            a, b = segs[i - 1], segs[i]
            if 'card' in (a['kind'], b['kind']):
                continue
            if b.get('cut'):
                out.append(b['t0'])
                continue
            ea = raw_cam(a, b['t0'] - 0.01)[0]
            eb = raw_cam(b, b['t0'])[0]
            if ea is not None and eb is not None and np.linalg.norm(ea - eb) > 12:
                out.append(b['t0'])
        return out

    def fade_alpha(self, t):
        a = 0.0
        for s in self.S.segs:
            if s['kind'] == 'card':
                if t < s['t0']:
                    a = max(a, smoothstep(s['t0'] - 0.8, s['t0'], t))
                elif t >= s['t1']:
                    a = max(a, 1 - smoothstep(s['t1'], s['t1'] + 0.8, t))
        for c in self.cuts:
            a = max(a, 1 - abs(t - c) / 0.4)
        a = max(a, smoothstep(self.T_END - 2.0, self.T_END - 0.2, t))
        return min(max(a, 0.0), 1.0)

    # ---------------- HUD / captions ----------------
    def icon(self, item, size):
        key = (item, size)
        if key not in self.icons:
            if item in ITEMS:
                im = TEX_LIST[TEX[item]]
            else:
                ty = TYPES.get(item, TYPES['cobblestone'])
                im = TEX_LIST[TYPE_TEX[ty][2]]
            rep = max(1, size // 16)
            big = np.repeat(np.repeat(im, rep, 0), rep, 1)
            self.icons[key] = big
        return self.icons[key]

    def blit_icon(self, img, ic, x0, y0):
        h, w = ic.shape[:2]
        sub = img[y0:y0 + h, x0:x0 + w]
        a = ic[:h, :w, 3:4].astype(np.float32) / 255
        sub[:] = (sub * (1 - a) + ic[:h, :w, :3] * a).astype(np.uint8)

    def overlay(self, img, t, sg):
        W, H = self.W, self.H
        u = H / 1080.0

        def S_(v):
            return max(1, int(round(v * u)))
        gold, white = (255, 214, 80), (255, 255, 255)
        if sg['hud']:
            cx, cy = W // 2, H // 2
            panel(img, cx - S_(14), cy - S_(2), cx + S_(14), cy + S_(2), 0.85, (235, 235, 235))
            panel(img, cx - S_(2), cy - S_(14), cx + S_(2), cy + S_(14), 0.85, (235, 235, 235))
            slot = S_(64)
            x0 = cx - slot * 9 // 2
            y0 = H - slot - S_(16)
            item, _ = self.held_and_swing(sg, t)
            bar = list(HOTBAR)
            sel = bar.index(item) if item in bar else None
            if sel is None and item not in ('none', 'leaves', None):
                bar[8] = item
                sel = 8
            panel(img, x0 - S_(4), y0 - S_(4), x0 + slot * 9 + S_(4), y0 + slot + S_(4), 0.55)
            for i, it in enumerate(bar):
                sx = x0 + i * slot
                panel(img, sx + S_(3), y0 + S_(3), sx + slot - S_(3), y0 + slot - S_(3), 0.35, (90, 90, 90))
                ic = self.icon(it, S_(48))
                self.blit_icon(img, ic, sx + (slot - ic.shape[1]) // 2, y0 + (slot - ic.shape[0]) // 2)
            if sel is not None:
                sx = x0 + sel * slot
                b = S_(4)
                for (a0, b0, a1, b1) in [(sx - b, y0 - b, sx + slot + b, y0), (sx - b, y0 + slot, sx + slot + b, y0 + slot + b),
                                         (sx - b, y0, sx, y0 + slot), (sx + slot, y0, sx + slot + b, y0 + slot)]:
                    panel(img, a0, b0, a1, b1, 0.95, (240, 240, 240))
            hp = 20
            for h in self.hurts:
                if t >= h:
                    hp = max(hp - 4, 0)
                    hp = min(20, hp + int((t - h) / 3.0))
            hm = np.array([[c == '#' for c in row] for row in HEART], bool)
            hs = S_(3)
            big = np.repeat(np.repeat(hm, hs, 0), hs, 1)
            for i in range(10):
                hx = x0 + i * S_(31)
                hy = y0 - S_(36)
                _blend(img, big, hx + hs, hy + hs, np.array([30, 10, 10]), 0.9)
                full = hp >= (i + 1) * 2
                half = hp == i * 2 + 1
                col = (220, 30, 40) if full or half else (60, 30, 30)
                _blend(img, big, hx, hy, np.array(col), 1.0)
                if full:
                    _blend(img, big[:hs * 3, :hs * 4], hx + hs, hy, np.array([255, 140, 140]), 0.5)
            day = int(self.theta_at(t) // TWO_PI) + 1
            if not sg['final']:
                txt = f"DAY {day}"
                panel(img, S_(28), S_(28), S_(28) + text_width(txt, S_(6)) + S_(36), S_(100), 0.4)
                draw_text(img, txt, S_(46), S_(42), S_(6), gold, 1.0, 'l')
            if sg['tl']:
                draw_text(img, ">> 20X", W - S_(46), S_(42), S_(6), white, 0.8 + 0.2 * math.sin(t * 5), 'r')
            if sg['res']:
                y = S_(110)
                for k in ['WOOD', 'STONE', 'COAL', 'IRON', 'DIAMONDS']:
                    cnt = int(np.searchsorted(self.res_t[k], t, side='right'))
                    if k in ('COAL', 'IRON', 'DIAMONDS') and cnt == 0:
                        continue
                    txt = f"{k} {cnt}"
                    col = (120, 240, 235) if k == 'DIAMONDS' else white
                    draw_text(img, txt, W - S_(46), y, S_(4), col, 1.0, 'r')
                    y += S_(42)
        for (a0, a1, text, style) in self.S.caps:
            if not (a0 <= t <= a1):
                continue
            a = env(t, a0, a1, 0.4)
            if style == 'sub':
                sc = S_(5)
                w = text_width(text, sc)
                yb = H - S_(230)
                panel(img, W // 2 - w // 2 - S_(22), yb - S_(18), W // 2 + w // 2 + S_(22), yb + sc * 8 + S_(14), 0.5 * a)
                draw_text(img, text, W // 2, yb + sc * 4, sc, white, a)
            elif style == 'chapter':
                draw_text(img, text, W // 2, H * 0.2, S_(10), white, a)
                w = text_width(text, S_(10))
                panel(img, W // 2 - w // 2, int(H * 0.2) + S_(48), W // 2 + w // 2, int(H * 0.2) + S_(54), 0.9 * a, gold)
            elif style == 'big':
                pop = 1.0 + 0.15 * max(0.0, 1 - (t - a0) / 0.3)
                draw_text(img, text, W // 2, H * 0.36, int(S_(15) * pop), (120, 240, 235) if 'DIAMOND' in text else (255, 80, 70), a)
            elif style == 'title':
                draw_text(img, text, W // 2, H * 0.34, S_(13), gold, a)
            elif style == 'titlesub':
                draw_text(img, text, W // 2, H * 0.34 + S_(95), S_(5), white, a)
            elif style == 'card':
                draw_text(img, text, W // 2, H * 0.44, S_(18), gold, a)
            elif style == 'cardsub':
                draw_text(img, text, W // 2, H * 0.44 + S_(110), S_(6), white, a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--w', type=int, default=1920)
    ap.add_argument('--h', type=int, default=1080)
    ap.add_argument('--preview', type=str, default=None)
    ap.add_argument('--start', type=float, default=0.0)
    ap.add_argument('--end', type=float, default=None)
    ap.add_argument('--out', type=str, default=os.path.join(HERE, 'epic_castle_build.mp4'))
    ap.add_argument('--audio', type=str, default=os.path.join(HERE, 'build', 'sfx.wav'))
    args = ap.parse_args()

    v = Video(args.w, args.h)
    if args.preview:
        os.makedirs(os.path.join(HERE, 'preview'), exist_ok=True)
        for s in args.preview.split(','):
            t = float(s)
            t0 = time.time()
            v.lv_time = None
            img = v.render(t)
            p = os.path.join(HERE, 'preview', f'v2_{t:06.1f}.png')
            Image.fromarray(img).save(p)
            print(f"{p}  ({time.time() - t0:.2f}s)")
        return
    end = args.end if args.end is not None else v.T_END
    os.makedirs(os.path.dirname(args.audio), exist_ok=True)
    t0 = time.time()
    synth_audio(args.audio, v.T_END, v.S, v.steps)
    print(f"audio ready ({time.time() - t0:.1f}s)", flush=True)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, '-y', '-loglevel', 'error',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{args.w}x{args.h}', '-r', str(FPS), '-i', '-',
           '-ss', f'{args.start:.3f}', '-i', args.audio,
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', args.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    f0, f1 = int(args.start * FPS), int(end * FPS)
    t_start = time.time()
    for f in range(f0, f1):
        img = v.render(f / FPS)
        proc.stdin.write(img.tobytes())
        if (f - f0) % 300 == 0:
            el = time.time() - t_start
            done = f - f0 + 1
            print(f"frame {f}/{f1}  {el:.0f}s elapsed  eta {el / done * (f1 - f0 - done):.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    print("done:", args.out, f"{time.time() - t_start:.0f}s")


if __name__ == '__main__':
    main()
