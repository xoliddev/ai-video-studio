'use strict';
// Uhud — procedural anime-style film. All people are faceless silhouettes;
// the Prophet (peace be upon him) and named companions are never depicted.
const W = 1920, H = 1080;
const cv = document.getElementById('c');
cv.width = W; cv.height = H;
const main = cv.getContext('2d');
const mk = (w = W, h = H) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; };
const bufA = mk(), bufB = mk();
const actxA = bufA.getContext('2d'), actxB = bufB.getContext('2d');
let ctx = main;

// ---------- math ----------
function rng(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp = (a, b, k) => a + (b - a) * k;
const ease = x => x < .5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;
const smooth = (a, b, x) => { x = clamp((x - a) / (b - a), 0, 1); return x * x * (3 - 2 * x); };
const win = (t, a, b, f = .6) => smooth(a, a + f, t) * (1 - smooth(b - f, b, t));
const setLS = v => { if ('letterSpacing' in ctx) ctx.letterSpacing = v; };
const mod = (a, n) => ((a % n) + n) % n;

function layer(cam, d, fn) {
  const lz = 1 + (cam.z - 1) * d;
  ctx.save();
  ctx.translate(W / 2, H / 2); ctx.scale(lz, lz);
  ctx.translate(-(W / 2 + (cam.x - W / 2) * d), -(H / 2 + (cam.y - H / 2) * d));
  fn();
  ctx.restore();
}
function scr(cam, d, x, y) {
  const lz = 1 + (cam.z - 1) * d;
  return [W / 2 + (x - (W / 2 + (cam.x - W / 2) * d)) * lz, H / 2 + (y - (H / 2 + (cam.y - H / 2) * d)) * lz];
}
// Cross-dissolve between two shots inside one scene.
function blend(k, fa, fb) {
  if (k <= 0) return fa();
  if (k >= 1) return fb();
  fa();
  const tgt = ctx; ctx = actxB;
  ctx.setTransform(tgt.getTransform()); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  fb();
  ctx = tgt;
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = k; ctx.drawImage(bufB, 0, 0); ctx.restore();
}

// ---------- sky ----------
const SKY = {
  night: [[0, '#04061a'], [.45, '#0c1638'], [.8, '#1d2a55'], [1, '#2c3a66']],
  dusk: [[0, '#0e1030'], [.25, '#2b1e4f'], [.48, '#6e2f5f'], [.62, '#c8505a'], [.72, '#f08a4b'], [.82, '#ffc36b'], [1, '#ffd98a']],
  duskRed: [[0, '#140c2a'], [.3, '#3a1a44'], [.55, '#8a2f4a'], [.7, '#d0553f'], [.82, '#f39a4f'], [1, '#ffd08a']],
  dawn: [[0, '#1a2350'], [.35, '#4b4a86'], [.6, '#c27a9a'], [.78, '#f3b08a'], [1, '#ffe0a8']],
  day: [[0, '#4a86c8'], [.45, '#8dbbe0'], [.75, '#f0d6a8'], [1, '#f7d9a0']],
  afternoon: [[0, '#3a5a9a'], [.4, '#9aa4c8'], [.7, '#f0c890'], [1, '#f8d8a0']],
  blood: [[0, '#2a0a14'], [.35, '#6a1a24'], [.6, '#c2402a'], [.78, '#f08040'], [1, '#ffc070']],
  smoke: [[0, '#120406'], [.4, '#3a0c10'], [.7, '#8a2a1a'], [1, '#c0582a']],
  deepDusk: [[0, '#0c0a24'], [.4, '#2a1a40'], [.7, '#6a2a44'], [.88, '#b84a3a'], [1, '#e08040']],
  ash: [[0, '#151018'], [.5, '#3a2a30'], [1, '#6a4a40']],
};
function sky(p) { const g = ctx.createLinearGradient(0, 0, 0, H); p.forEach(s => g.addColorStop(s[0], s[1])); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); }
function glow(x, y, r, col, a) {
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, `rgba(${col},${a})`); g.addColorStop(.4, `rgba(${col},${a * .35})`); g.addColorStop(1, `rgba(${col},0)`);
  ctx.fillStyle = g; ctx.fillRect(x - r, y - r, 2 * r, 2 * r);
}
function sunDisc(x, y, r = 70, inner = '#fffbe8', mid = '#ffe7a6') {
  const g = ctx.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, inner); g.addColorStop(.6, mid); g.addColorStop(1, 'rgba(255,200,120,0)');
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill();
}
function rays(x, y, t, o = {}) {
  const n = o.n || 12, a = o.a ?? .13, col = o.col || '255,205,140', len = o.len || 1300, from = o.from ?? -Math.PI, span = o.span ?? Math.PI;
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (let i = 0; i < n; i++) {
    const ang = from + i * (span / (n - 1)) + Math.sin(t * .15 + i) * .04, wd = .025 + (i % 3) * .015;
    const g = ctx.createRadialGradient(x, y, 40, x, y, len); g.addColorStop(0, `rgba(${col},${a})`); g.addColorStop(1, `rgba(${col},0)`);
    ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(x, y); ctx.arc(x, y, len, ang - wd, ang + wd); ctx.closePath(); ctx.fill();
  }
  ctx.restore();
}
const STARS = (() => { const r = rng(23), a = []; for (let i = 0; i < 280; i++) a.push({ x: r() * W, y: r() * H * .72, r: .5 + r() * 1.4, ph: r() * 6 }); return a; })();
const MILKY = (() => { const r = rng(41), a = []; for (let i = 0; i < 1000; i++) { const u = r(); a.push({ x: u * W * 1.2 - W * .1, y: H * .66 - u * H * .62 + (r() - .5) * r() * 170, r: .3 + r() * .9, a: .15 + r() * .45 }); } return a; })();
function stars(t, alpha = 1, maxY = H * .72, milky = false) {
  ctx.save(); ctx.fillStyle = '#fff';
  if (milky) {
    ctx.save(); ctx.translate(W / 2, H * .35); ctx.rotate(-.47);
    const g = ctx.createLinearGradient(0, -170, 0, 170); g.addColorStop(0, 'rgba(170,160,255,0)'); g.addColorStop(.5, `rgba(190,180,255,${.09 * alpha})`); g.addColorStop(1, 'rgba(170,160,255,0)');
    ctx.fillStyle = g; ctx.fillRect(-1500, -170, 3000, 340); ctx.restore();
    ctx.fillStyle = '#fff';
    for (const s of MILKY) { ctx.globalAlpha = s.a * alpha; ctx.fillRect(s.x, s.y, s.r, s.r); }
  }
  for (const s of STARS) {
    if (s.y > maxY) continue;
    ctx.globalAlpha = alpha * (1 - s.y / maxY * .7) * (.55 + .45 * Math.sin(t * 2 + s.ph));
    ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, 7); ctx.fill();
  }
  ctx.restore();
}
const MOON = (() => {
  const c = mk(240, 240), g = c.getContext('2d');
  const gr = g.createRadialGradient(120, 120, 0, 120, 120, 120); gr.addColorStop(0, 'rgba(220,230,255,.4)'); gr.addColorStop(1, 'rgba(220,230,255,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 240, 240);
  const d = mk(240, 240), h = d.getContext('2d');
  h.fillStyle = '#f4f1e0'; h.beginPath(); h.arc(120, 120, 36, 0, 7); h.fill();
  h.globalCompositeOperation = 'destination-out'; h.beginPath(); h.arc(135, 108, 32, 0, 7); h.fill();
  g.drawImage(d, 0, 0); return c;
})();
function moon(x, y) { ctx.drawImage(MOON, x - 120, y - 120); }

// ---------- clouds ----------
const CPAL = {
  dusk: { lit: ['#ffcf9a', '#ff9a6a'], sh: ['#4b3a6e', '#9a5a82'], shs: ['#c86a7a', '#e88a78'] },
  duskRed: { lit: ['#ffc08a', '#ff8a5a'], sh: ['#4a2448', '#8a3a5a'], shs: ['#b85a6a', '#e07a68'] },
  day: { lit: ['#c6d2e6', '#b4c2da'], sh: ['#ffffff', '#f2f6fb'], shs: ['#f8f4ee', '#ffffff'] },
  night: { lit: ['#9fb0d8', '#6d7fb0'], sh: ['#161e40', '#26305e'], shs: ['#26305e', '#36426e'] },
  blood: { lit: ['#ffb070', '#e8603a'], sh: ['#3a0d16', '#6a1a22'], shs: ['#7a2a26', '#b04a32'] },
  dawn: { lit: ['#ffe0b8', '#ffb090'], sh: ['#5a5a96', '#a07aa8'], shs: ['#d89aa8', '#f0b8a0'] },
  afternoon: { lit: ['#ffe2b0', '#f8c890'], sh: ['#f4f0ea', '#ffffff'], shs: ['#fff0d8', '#fff8ec'] },
};
function makeCloud(seed, w, h, streak, pal) {
  const r = rng(seed), c = mk(w + 80, h + 80), g = c.getContext('2d'); g.translate(40, 40);
  const blobs = [];
  if (streak) for (let i = 0; i < 12; i++) blobs.push([w * .05 + r() * w * .9, h * .5 + (r() - .5) * h * .3, h * .35 + r() * h * .3]);
  else for (let i = 0; i < 16; i++) { const x = w * .1 + r() * w * .8, k = 1 - Math.abs(x / w - .5) * 1.6; blobs.push([x, h * .75 - r() * h * .5 * k, (h * .18 + r() * h * .22) * (.5 + k * .6)]); }
  const path = (oy, sc) => { g.beginPath(); blobs.forEach(b => { g.moveTo(b[0] + b[2] * sc, b[1] + oy * b[2]); g.arc(b[0], b[1] + oy * b[2], b[2] * sc, 0, 7); }); };
  path(0, 1);
  const lit = g.createLinearGradient(0, 0, 0, h); lit.addColorStop(0, pal.lit[0]); lit.addColorStop(1, pal.lit[1]);
  g.fillStyle = lit; g.fill();
  g.globalCompositeOperation = 'source-atop';
  path(-.28, 1.02);
  const s = streak ? pal.shs : pal.sh, sh = g.createLinearGradient(0, 0, 0, h); sh.addColorStop(0, s[0]); sh.addColorStop(1, s[1]);
  g.fillStyle = sh; g.fill();
  return c;
}
const CLOUDS = {};
function cloudSet(name) {
  if (CLOUDS[name]) return CLOUDS[name];
  const r = rng(21), pal = CPAL[name], set = [];
  for (let i = 0; i < 9; i++) { const w = 300 + r() * 420, h = 110 + r() * 90; set.push({ img: makeCloud(100 + i, w, h, false, pal), x: -300 + r() * 2500, y: 90 + r() * 280, s: .6 + r() * .6, v: 4 + r() * 6, a: .92 }); }
  for (let i = 0; i < 6; i++) { const w = 500 + r() * 600, h = 26 + r() * 16; set.push({ img: makeCloud(200 + i, w, h, true, pal), x: -300 + r() * 2500, y: 460 + r() * 90, s: 1, v: 6 + r() * 5, a: .85 }); }
  return (CLOUDS[name] = set);
}
function clouds(name, cam, t, o = {}) {
  const set = cloudSet(name), dy = o.dy || 0, alpha = o.alpha ?? 1, sp = o.speed ?? 1;
  layer(cam, .1, () => {
    for (const c of set) {
      const x = mod(c.x - t * c.v * sp + 800, 3500) - 800;
      ctx.globalAlpha = c.a * alpha; ctx.drawImage(c.img, x, c.y + dy, c.img.width * c.s, c.img.height * c.s);
    }
    ctx.globalAlpha = 1;
  });
}

// ---------- terrain ----------
function genRidge(seed, x0, x1, step, f) { const r = rng(seed), p = [r() * 6, r() * 6, r() * 6, r() * 6, r() * 6], a = []; for (let x = x0; x <= x1; x += step) a.push([x, f(x, p)]); return a; }
function ridgePath(pts, bottom) { ctx.beginPath(); ctx.moveTo(pts[0][0], bottom); for (const p of pts) ctx.lineTo(p[0], p[1]); ctx.lineTo(pts[pts.length - 1][0], bottom); ctx.closePath(); }
function ridgeLine(pts) { ctx.beginPath(); pts.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])); }
function rimGrad(x0, x1, sx, a, col = '255,185,120') {
  const g = ctx.createLinearGradient(x0, 0, x1, 0), p = clamp((sx - x0) / (x1 - x0), .05, .95);
  g.addColorStop(0, `rgba(${col},${a * .08})`); g.addColorStop(clamp(p - .3, 0, 1), `rgba(${col},${a * .3})`);
  g.addColorStop(p, `rgba(${col},${a})`); g.addColorStop(clamp(p + .3, 0, 1), `rgba(${col},${a * .3})`); g.addColorStop(1, `rgba(${col},${a * .08})`);
  return g;
}
function ridgeLayer(cam, d, pts, o) {
  layer(cam, d, () => {
    ridgePath(pts, 1700);
    const g = ctx.createLinearGradient(0, o.y0 ?? 450, 0, o.y1 ?? 950); g.addColorStop(0, o.top); g.addColorStop(1, o.bot);
    ctx.fillStyle = g; ctx.fill();
    if (o.extra) { ctx.save(); ctx.clip(); o.extra(); ctx.restore(); }
    if (o.rimA) { ridgeLine(pts); ctx.strokeStyle = rimGrad(pts[0][0], pts[pts.length - 1][0], o.sunX ?? 960, o.rimA, o.rimCol); ctx.lineWidth = o.rimW || 2.5; ctx.stroke(); }
  });
}
const FAR = genRidge(3, -900, 2900, 8, (x, p) => 690 - 40 * Math.sin(x * .0021 + p[0]) - 22 * Math.sin(x * .0057 + p[1]) - 8 * Math.sin(x * .017 + p[2]));
const UHUD = genRidge(11, -900, 2900, 6, (x, p) => 790 - 310 * Math.exp(-Math.pow((x - 820) / 620, 2)) - 120 * Math.exp(-Math.pow((x - 1900) / 420, 2))
  - 55 * Math.abs(Math.sin(x * .0042 + p[0])) - 22 * Math.sin(x * .011 + p[1]) - 7 * Math.sin(x * .035 + p[2]));
const uhudY = x => UHUD[clamp(Math.round((x + 900) / 6), 0, UHUD.length - 1)][1];
const RAV = (() => { const r = rng(13), a = []; for (let i = 0; i < 46; i++) a.push({ x: -200 + r() * 2400, dx: (r() - .5) * 160, w: 3 + r() * 14, lit: r() < .35 }); return a; })();
function uhudLayer(cam, d, o) {
  ridgeLayer(cam, d, UHUD, Object.assign({ y0: 420, y1: 900 }, o, {
    extra: () => {
      ctx.lineCap = 'round';
      const ra = o.ravA ?? 1;
      for (const r of RAV) {
        const ry = uhudY(r.x);
        ctx.strokeStyle = r.lit ? `rgba(${o.rimCol || '255,150,100'},${.08 * ra})` : `rgba(12,0,10,${.22 * ra})`;
        ctx.lineWidth = r.w; ctx.beginPath(); ctx.moveTo(r.x, ry); ctx.quadraticCurveTo(r.x + r.dx * .3, ry + 120, r.x + r.dx, ry + 300); ctx.stroke();
      }
    }
  }));
}
const DUNES = [
  genRidge(51, -900, 2900, 10, (x, p) => 800 - 30 * Math.sin(x * .0018 + p[0]) - 14 * Math.sin(x * .0049 + p[1])),
  genRidge(52, -900, 2900, 10, (x, p) => 880 - 36 * Math.sin(x * .0016 + p[0]) - 16 * Math.sin(x * .0043 + p[1])),
  genRidge(53, -900, 2900, 10, (x, p) => 985 - 40 * Math.sin(x * .0013 + p[0]) - 14 * Math.sin(x * .0051 + p[1])),
];
function dunes(cam, cols, o = {}) {
  const ds = [.5, .75, 1];
  DUNES.forEach((pts, i) => ridgeLayer(cam, ds[i], pts, { top: cols[i][0], bot: cols[i][1], y0: 760 + i * 80, y1: 1080, rimA: o.rimA ?? .5, rimCol: o.rimCol, sunX: o.sunX, rimW: 2 }));
}
function plain(cam, d, y, c0, c1, haze) {
  layer(cam, d, () => {
    const g = ctx.createLinearGradient(0, y, 0, y + 380); g.addColorStop(0, c0); g.addColorStop(1, c1);
    ctx.fillStyle = g; ctx.fillRect(-2000, y, 6000, 1500);
    if (haze) { const h = ctx.createLinearGradient(0, y - 30, 0, y + 60); h.addColorStop(0, `rgba(${haze},0)`); h.addColorStop(.5, `rgba(${haze},.22)`); h.addColorStop(1, `rgba(${haze},0)`); ctx.fillStyle = h; ctx.fillRect(-2000, y - 30, 6000, 90); }
  });
}

// ---------- sprites ----------
function radialSprite(col, a) { const c = mk(128, 128), g = c.getContext('2d'); const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64); gr.addColorStop(0, `rgba(${col},${a})`); gr.addColorStop(1, `rgba(${col},0)`); g.fillStyle = gr; g.fillRect(0, 0, 128, 128); return c; }
const DUST = radialSprite('225,140,95', .45), DUSTDAY = radialSprite('230,190,140', .4), SMOKE = radialSprite('40,18,20', .55), GOLD = radialSprite('255,215,140', .8);
const VIGNETTE = (() => { const c = mk(), g = c.getContext('2d'); const gr = g.createRadialGradient(W / 2, H / 2, 480, W / 2, H / 2, 1250); gr.addColorStop(0, 'rgba(10,0,12,0)'); gr.addColorStop(1, 'rgba(10,0,12,.7)'); g.fillStyle = gr; g.fillRect(0, 0, W, H); return c; })();
const MOTES = (() => { const r = rng(29), a = []; for (let i = 0; i < 80; i++) a.push({ x: r() * W, y: r() * H, r: .8 + r() * 2.2, v: .5 + r() * 1.5, ph: r() * 6 }); return a; })();
function motes(t, col = '255,190,120', alpha = 1, up = 6) {
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (const m of MOTES) {
    const x = mod(m.x - t * m.v * 30, W + 40) - 20, y = mod(m.y + Math.sin(t * .7 + m.ph) * 20 - t * up, H);
    ctx.fillStyle = `rgba(${col},${(.25 + .25 * Math.sin(t * 1.3 + m.ph)) * alpha})`; ctx.beginPath(); ctx.arc(x, y, m.r, 0, 7); ctx.fill();
  }
  ctx.restore();
}

// ---------- characters (units: height 100, feet at origin, facing right) ----------
function figure(t, ph, pose, weapon, col, shield) {
  const w = Math.sin(t * 3.2 + ph), w2 = Math.sin(t * 4.1 + ph * 1.7);
  const kneel = pose === 'kneel', seated = pose === 'seated', moving = pose === 'walk' || pose === 'run';
  const sp = pose === 'run' ? 11 : 6.5, sw = Math.sin(t * sp + ph);
  const bob = moving ? Math.abs(Math.cos(t * sp + ph)) * (pose === 'run' ? 3 : 1.5) : 0;
  const hy = (kneel ? -26 : seated ? 0 : -42) - bob, sh = hy - 36;
  ctx.fillStyle = col; ctx.strokeStyle = col; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  ctx.lineWidth = 7; ctx.beginPath();
  if (seated) { ctx.moveTo(0, 0); ctx.lineTo(6, 20); }
  else if (kneel) { ctx.moveTo(0, hy); ctx.lineTo(12, hy); ctx.lineTo(12, 0); ctx.moveTo(0, hy); ctx.lineTo(-6, -3); ctx.lineTo(-20, 0); }
  else if (moving) { const a = pose === 'run' ? 15 : 9; ctx.moveTo(0, hy); ctx.lineTo(sw * a, -Math.max(0, -sw) * 5); ctx.moveTo(0, hy); ctx.lineTo(-sw * a, -Math.max(0, sw) * 5); }
  else { ctx.moveTo(-3, hy); ctx.lineTo(-8, 0); ctx.moveTo(3, hy); ctx.lineTo(8, 0); }
  ctx.stroke();
  ctx.save();
  if (pose === 'run') { ctx.translate(0, hy); ctx.transform(1, 0, -.2, 1, 0, 0); ctx.translate(0, -hy); }
  // robe and cloak
  ctx.beginPath(); ctx.moveTo(-11, sh); ctx.lineTo(11, sh); ctx.lineTo(14, hy + (kneel ? 8 : 14)); ctx.lineTo(-16 - 4 * w, hy + (kneel ? 10 : 16)); ctx.closePath(); ctx.fill();
  ctx.beginPath(); ctx.moveTo(-10, sh + 2); ctx.quadraticCurveTo(-24 + w * 4, sh + 20, -24 + w * 6, hy + 10); ctx.lineTo(-13, hy + 12); ctx.closePath(); ctx.fill();
  if (weapon === 'bow') {
    ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(-9, sh + 2); ctx.lineTo(-16, sh + 24); ctx.stroke();
    ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(-9, sh + 2); ctx.lineTo(-7, sh - 7); ctx.moveTo(-9, sh + 2); ctx.lineTo(-10, sh - 8); ctx.moveTo(-9, sh + 2); ctx.lineTo(-13, sh - 6); ctx.stroke();
    ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(8, sh + 4); ctx.lineTo(20, sh + 12); ctx.stroke();
    ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(19, sh - 14); ctx.quadraticCurveTo(35, sh + 12, 19, sh + 38); ctx.stroke();
    ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(19, sh - 14); ctx.lineTo(19, sh + 38); ctx.stroke();
  } else if (weapon === 'spear') {
    ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(8, sh + 4); ctx.lineTo(17, sh + 14); ctx.stroke();
    ctx.lineWidth = 2.5; ctx.beginPath(); ctx.moveTo(14, hy + 14); ctx.lineTo(26, sh - 46); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(26, sh - 58); ctx.lineTo(29, sh - 44); ctx.lineTo(23, sh - 45); ctx.closePath(); ctx.fill();
  } else if (weapon === 'sword') {
    const a = -1.1 + Math.sin(t * 6 + ph) * .7;
    const hx = 8 + Math.cos(a) * 14, hy2 = sh + 4 + Math.sin(a) * 14;
    ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(8, sh + 4); ctx.lineTo(hx, hy2); ctx.stroke();
    ctx.lineWidth = 2.5; ctx.beginPath(); ctx.moveTo(hx, hy2); ctx.lineTo(hx + Math.cos(a - .3) * 34, hy2 + Math.sin(a - .3) * 34); ctx.stroke();
  }
  if (shield) { ctx.beginPath(); ctx.arc(15, shield === 'up' ? sh - 4 : sh + 16, 13, 0, 7); ctx.fill(); }
  ctx.beginPath(); ctx.arc(0, sh - 9, 8, 0, 7); ctx.fill();
  ctx.beginPath(); ctx.ellipse(0, sh - 13, 10, 6.5, 0, 0, 7); ctx.fill();
  ctx.beginPath(); ctx.moveTo(-6, sh - 13); ctx.quadraticCurveTo(-18, sh - 8 + w * 3, -32 + w2 * 3, sh - 5 + w * 4);
  ctx.lineTo(-30 + w2 * 3, sh + w * 4); ctx.quadraticCurveTo(-16, sh - 2, -5, sh - 6); ctx.closePath(); ctx.fill();
  ctx.restore();
}
function horse(t, ph, col, gallop) {
  const g = t * gallop * 9 + ph, bob = Math.sin(g * 2) * 2 * gallop;
  ctx.fillStyle = col; ctx.strokeStyle = col; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  ctx.save(); ctx.translate(0, bob * .5);
  ctx.lineWidth = 5;
  const leg = (hx, phase, front) => {
    const s = Math.sin(g + phase), lift = Math.max(0, Math.cos(g + phase)) * 10 * gallop;
    ctx.beginPath(); ctx.moveTo(hx, -44); ctx.lineTo(hx + s * 10 * gallop, -26 - lift * .4); ctx.lineTo(hx + s * 18 * gallop + (front ? 3 : -3), -lift - bob * .5); ctx.stroke();
  };
  leg(24, 0, true); leg(19, 1.2, true); leg(-24, 2.6, false); leg(-19, 3.6, false);
  ctx.beginPath(); ctx.ellipse(0, -50, 34, 14, 0, 0, 7); ctx.fill();
  ctx.beginPath(); ctx.moveTo(18, -60); ctx.quadraticCurveTo(34, -74, 42, -88); ctx.lineTo(50, -90); ctx.lineTo(66, -76); ctx.lineTo(62, -70); ctx.lineTo(48, -76); ctx.quadraticCurveTo(44, -60, 32, -44); ctx.closePath(); ctx.fill();
  ctx.beginPath(); ctx.moveTo(45, -89); ctx.lineTo(48, -98); ctx.lineTo(51, -89); ctx.fill();
  ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(40, -88); ctx.quadraticCurveTo(28 - Math.sin(t * 8 + ph) * 3, -76, 22, -62); ctx.stroke();
  const f = Math.sin(t * 6 + ph) * 4; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(-32, -56); ctx.quadraticCurveTo(-46, -52 + f, -56, -38 + f); ctx.stroke();
  ctx.restore();
}
function camel(t, ph, col) {
  const g = t * 5 + ph;
  ctx.fillStyle = col; ctx.strokeStyle = col; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.lineWidth = 4.5;
  const leg = (hx, phase) => { const s = Math.sin(g + phase); ctx.beginPath(); ctx.moveTo(hx, -58); ctx.lineTo(hx + s * 7, -30); ctx.lineTo(hx + s * 12, -Math.max(0, Math.cos(g + phase)) * 5); ctx.stroke(); };
  leg(26, 0); leg(22, Math.PI); leg(-22, Math.PI * .5); leg(-26, Math.PI * 1.5);
  ctx.beginPath(); ctx.moveTo(-36, -60); ctx.quadraticCurveTo(-30, -74, -14, -76); ctx.quadraticCurveTo(-2, -98, 12, -78); ctx.quadraticCurveTo(26, -74, 34, -64);
  ctx.quadraticCurveTo(30, -52, 0, -52); ctx.quadraticCurveTo(-30, -52, -36, -60); ctx.fill();
  ctx.lineWidth = 9; ctx.beginPath(); ctx.moveTo(30, -64); ctx.quadraticCurveTo(48, -60, 52, -82); ctx.stroke();
  ctx.beginPath(); ctx.ellipse(57, -86, 9, 5, .2, 0, 7); ctx.fill();
  ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(-36, -60); ctx.lineTo(-40, -44); ctx.stroke();
}
// Silhouette with optional rim light (dx,dy points toward the light).
function sil(x, y, s, o, draw) {
  const pass = (ox, oy, col) => { ctx.save(); ctx.translate(x + ox, y + oy); ctx.scale(o.flip ? -s : s, s); draw(col); ctx.restore(); };
  if (o.alpha !== undefined) { ctx.save(); ctx.globalAlpha *= o.alpha; }
  if (o.rim) { const [rx, ry] = o.rim; pass(rx * 2.2, ry * 2.2, o.rimSoft || 'rgba(255,150,80,.25)'); pass(rx, ry, o.rimCol || 'rgba(255,195,125,.9)'); }
  pass(0, 0, o.col || '#0b0609');
  if (o.alpha !== undefined) ctx.restore();
}
const person = (x, y, s, o) => sil(x, y, s, o, c => figure(o.t, o.ph || 0, o.pose || 'stand', o.weapon || 'none', c, o.shield));
const cavalry = (x, y, s, o) => sil(x, y, s, o, c => {
  const gl = o.gallop ?? 1;
  horse(o.t, o.ph || 0, c, gl);
  ctx.save(); ctx.translate(2, -58 + Math.sin((o.t * gl * 9 + (o.ph || 0)) * 2) * 1); ctx.scale(.62, .62);
  figure(o.t, o.ph || 0, 'seated', o.weapon || 'spear', c, o.shield); ctx.restore();
});
const camelRider = (x, y, s, o) => sil(x, y, s, o, c => {
  camel(o.t, o.ph || 0, c);
  ctx.save(); ctx.translate(-4, -80); ctx.scale(.6, .6); figure(o.t, o.ph || 0, 'seated', 'spear', c); ctx.restore();
});
function palm(x, y, h, t, ph, col) {
  ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineCap = 'round';
  const bend = h * .12, sway = Math.sin(t * 1.2 + ph) * h * .015, tx = x + bend + sway, ty = y - h;
  ctx.lineWidth = h * .045; ctx.beginPath(); ctx.moveTo(x, y); ctx.quadraticCurveTo(x + bend * .2, y - h * .5, tx, ty); ctx.stroke();
  for (let i = 0; i < 9; i++) {
    const a = -Math.PI / 2 + (i - 4) * .42 + Math.sin(t * 1.5 + ph + i) * .04, L = h * (.42 + .1 * Math.cos(i * 1.7));
    const ex = tx + Math.cos(a) * L, ey = ty + Math.sin(a) * L * .55 + L * .35;
    const cx = tx + Math.cos(a) * L * .6, cy = ty + Math.sin(a) * L * .6 - L * .15;
    ctx.lineWidth = h * .016; ctx.beginPath(); ctx.moveTo(tx, ty); ctx.quadraticCurveTo(cx, cy, ex, ey); ctx.stroke();
    ctx.lineWidth = h * .008; ctx.beginPath();
    for (let k = 1; k <= 7; k++) {
      const u = k / 8, qx = (1 - u) * (1 - u) * tx + 2 * (1 - u) * u * cx + u * u * ex, qy = (1 - u) * (1 - u) * ty + 2 * (1 - u) * u * cy + u * u * ey;
      const ll = L * .14 * (1 - u * .5);
      ctx.moveTo(qx, qy); ctx.lineTo(qx + Math.cos(a + .9) * ll, qy + Math.abs(Math.sin(a + .9)) * ll + ll * .4);
      ctx.moveTo(qx, qy); ctx.lineTo(qx + Math.cos(a - .9) * ll, qy + Math.abs(Math.sin(a - .9)) * ll + ll * .4);
    }
    ctx.stroke();
  }
  ctx.beginPath(); ctx.arc(tx, ty + h * .03, h * .035, 0, 7); ctx.fill();
}
function makeTown(seed, w, h, col, win, density) {
  const c = mk(w, h + 40), g = c.getContext('2d'), r = rng(seed);
  for (let row = 0; row < 3; row++) {
    let x = -20 + row * 25;
    const base = h - row * 26, shade = row === 0 ? col : row === 1 ? col + 'dd' : col + 'aa';
    while (x < w) {
      const bw = 40 + r() * 80, bh = 30 + r() * 60 + (2 - row) * 8;
      g.fillStyle = shade; g.fillRect(x, base - bh, bw, bh + 40);
      g.fillRect(x - 2, base - bh - 4, bw + 4, 5);
      if (r() < .35) { const tw = bw * (.4 + r() * .3); g.fillRect(x + bw * .2, base - bh - 26, tw, 26); }
      const nwin = (bw / 22) | 0;
      for (let k = 0; k < nwin; k++) if (r() < density) {
        const wx = x + 8 + k * 20, wy = base - bh * (.35 + r() * .35);
        const gg = g.createRadialGradient(wx + 3, wy + 4, 0, wx + 3, wy + 4, 22); gg.addColorStop(0, `rgba(${win},.35)`); gg.addColorStop(1, `rgba(${win},0)`);
        g.fillStyle = gg; g.fillRect(wx - 20, wy - 20, 46, 48);
        g.fillStyle = `rgb(${win})`; g.fillRect(wx, wy, 6, 8); g.fillStyle = shade;
      }
      x += bw + r() * 10;
    }
  }
  return c;
}
let TOWN_M, TOWN_D;
function torch(x, y, t, ph, s = 1) {
  const f = .75 + .25 * Math.sin(t * 13 + ph) * Math.sin(t * 7.3 + ph * 2);
  glow(x, y - 30 * s, 60 * s * f, '255,150,60', .45);
  ctx.strokeStyle = '#120808'; ctx.lineWidth = 3 * s; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y - 26 * s); ctx.stroke();
  ctx.fillStyle = '#ffd27a'; ctx.beginPath(); ctx.moveTo(x - 5 * s, y - 26 * s); ctx.quadraticCurveTo(x, y - (44 + 6 * f) * s, x + 5 * s, y - 26 * s); ctx.fill();
}
function tent(x, y, w, h, col) {
  ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(x - w / 2, y); ctx.quadraticCurveTo(x - w * .2, y - h * .5, x, y - h); ctx.quadraticCurveTo(x + w * .2, y - h * .5, x + w / 2, y); ctx.closePath(); ctx.fill();
  ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x, y - h); ctx.lineTo(x, y - h - 10); ctx.stroke();
}
function arrow(x, y, ang, len, col, w = 2) {
  const dx = Math.cos(ang), dy = Math.sin(ang);
  ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = w; ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(x - dx * len, y - dy * len); ctx.lineTo(x, y); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x + dx * w * 3, y + dy * w * 3); ctx.lineTo(x - dx * w * 2 - dy * w * 1.8, y - dy * w * 2 + dx * w * 1.8); ctx.lineTo(x - dx * w * 2 + dy * w * 1.8, y - dy * w * 2 - dx * w * 1.8); ctx.fill();
}
function banner(x, y, h, t, ph, col, ang = 0) {
  ctx.save(); ctx.translate(x, y); ctx.rotate(ang);
  ctx.strokeStyle = '#120808'; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, -h); ctx.stroke();
  const f1 = Math.sin(t * 5 + ph) * 3, f2 = Math.sin(t * 5 + ph + 1.5) * 3;
  ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(0, -h); ctx.quadraticCurveTo(h * .2, -h + f1, h * .4, -h + 2 + f2); ctx.lineTo(h * .4, -h * .7 + f2); ctx.quadraticCurveTo(h * .2, -h * .72 + f1, 0, -h * .7); ctx.fill();
  ctx.restore();
}

// ---------- text ----------
function wrapText(text, maxW) {
  const words = text.split(' '), lines = []; let cur = '';
  for (const w of words) { const test = cur ? cur + ' ' + w : w; if (ctx.measureText(test).width > maxW && cur) { lines.push(cur); cur = w; } else cur = test; }
  if (cur) lines.push(cur); return lines;
}
function titleBlock(k, title, sub, small, y = 520, size = 180) {
  if (k <= 0) return;
  ctx.save(); ctx.globalAlpha = k; ctx.textAlign = 'center';
  ctx.font = `700 ${size}px Cinzel, Georgia, serif`; setLS(size * .2 + 'px');
  const g = ctx.createLinearGradient(0, y - size * .75, 0, y + 10); g.addColorStop(0, '#fff1c9'); g.addColorStop(.5, '#f2b45a'); g.addColorStop(1, '#a8562a');
  ctx.shadowColor = 'rgba(255,140,60,.6)'; ctx.shadowBlur = 40; ctx.fillStyle = g;
  ctx.fillText(title, W / 2 + size * .1, y - (1 - k) * 14);
  setLS('0px'); ctx.shadowBlur = 12; ctx.shadowColor = 'rgba(0,0,0,.8)';
  ctx.strokeStyle = 'rgba(240,180,100,.7)'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(W / 2 - 330, y + 45); ctx.lineTo(W / 2 - 60, y + 45); ctx.moveTo(W / 2 + 60, y + 45); ctx.lineTo(W / 2 + 330, y + 45); ctx.stroke();
  ctx.fillStyle = '#f0b866'; ctx.beginPath(); ctx.moveTo(W / 2, y + 35); ctx.lineTo(W / 2 + 9, y + 45); ctx.lineTo(W / 2, y + 55); ctx.lineTo(W / 2 - 9, y + 45); ctx.fill();
  if (sub) { ctx.font = 'italic 500 50px "Cormorant Garamond", Georgia, serif'; ctx.fillStyle = '#f6e2c4'; ctx.fillText(sub, W / 2, y + 120); }
  if (small) { ctx.font = '500 24px Cinzel, Georgia, serif'; setLS('8px'); ctx.fillStyle = 'rgba(240,200,140,.85)'; ctx.fillText(small, W / 2 + 4, y + 175); setLS('0px'); }
  ctx.restore();
}
function label(text, x, y, o = {}) {
  ctx.save(); ctx.globalAlpha *= o.alpha ?? 1; ctx.textAlign = o.align || 'center';
  ctx.font = o.font || '600 26px Cinzel, Georgia, serif'; setLS(o.ls || '3px');
  if (o.shadow !== false) { ctx.shadowColor = o.shadowCol || 'rgba(0,0,0,.85)'; ctx.shadowBlur = o.blur ?? 12; }
  ctx.fillStyle = o.col || '#fbf1e3'; ctx.fillText(text, x, y); setLS('0px'); ctx.restore();
}
function statCard(k, x, y, num, lab, col = '#fff6e4', backdrop = false) {
  if (k <= 0) return;
  if (backdrop) {
    const bw = backdrop === true ? 340 : backdrop;
    ctx.save(); ctx.globalAlpha = k * .45; ctx.fillStyle = '#1a0c06';
    ctx.beginPath(); ctx.roundRect(x - bw / 2, y - 80, bw, 140, 18); ctx.fill(); ctx.restore();
  }
  label(num, x, y - (1 - k) * 12, { alpha: k, font: '700 72px Cinzel, Georgia, serif', col, ls: '2px', blur: 18 });
  label(lab, x, y + 40, { alpha: k, font: '600 22px Cinzel, Georgia, serif', col: 'rgba(255,230,190,.95)', ls: '6px' });
}
function quoteCard(k, text, who, col, y = 420) {
  if (k <= 0) return;
  ctx.save(); ctx.globalAlpha = k; ctx.textAlign = 'center';
  ctx.font = '600 22px Cinzel, Georgia, serif'; setLS('8px'); ctx.fillStyle = col; ctx.shadowColor = 'rgba(0,0,0,.9)'; ctx.shadowBlur = 12;
  ctx.fillText(who, W / 2 + 4, y - 80); setLS('0px');
  ctx.font = 'italic 600 70px "Cormorant Garamond", Georgia, serif'; ctx.fillStyle = '#fff6e6'; ctx.shadowBlur = 24;
  const lines = wrapText('“' + text + '”', 1500);
  lines.forEach((l, i) => ctx.fillText(l, W / 2, y + i * 80 - (1 - k) * 10));
  ctx.restore();
}

// ---------- shared shots ----------
const SUN = { x: 1450, y: 592 };
function hillY(x) { const u = (x - 1350) / 480; return 700 + 400 * Math.pow(Math.abs(u), 2.6) + 5 * Math.sin(x * .045); }
const ARCHERS = (() => { const r = rng(5), a = []; for (let i = 0; i < 12; i++) a.push({ x: 1200 + i * 26 + (r() - .5) * 10, ph: r() * 6, k: r() < .3, s: .36 + r() * .04 }); return a; })();
const ARMY = (() => { const r = rng(9), a = []; for (let i = 0; i < 280; i++) { const ang = r() * 6.28, rr = Math.sqrt(r()); a.push({ x: 1350 + Math.cos(ang) * rr * 230, y: 845 + Math.sin(ang) * rr * 26, h: 5 + r() * 3 }); } return a; })();
const ARMY_BAN = (() => { const r = rng(17), a = []; for (let i = 0; i < 14; i++) a.push({ x: 1160 + r() * 380, y: 838 + r() * 18, red: r() < .5, ph: r() * 6 }); return a; })();
const ARMY_DUST = (() => { const r = rng(19), a = []; for (let i = 0; i < 30; i++) a.push({ x: 1150 + r() * 480, y: 790 + r() * 55, s: 80 + r() * 140, v: 2 + r() * 4 }); return a; })();
const TUFTS = (() => { const r = rng(31), a = []; for (let i = 0; i < 38; i++) a.push({ x: r() * 840, n: 3 + (r() * 4 | 0), h: 22 + r() * 40, ph: r() * 6 }); return a; })();
const rockY = x => 985 + Math.pow(Math.max(0, x - 250) / 650, 2) * 110 + 6 * Math.sin(x * .03);

function sunsetBackdrop(cam, t) {
  const [sx, sy] = scr(cam, .05, SUN.x, SUN.y);
  sky(SKY.dusk);
  stars(t, .8, 380);
  glow(sx, sy, 950, '255,170,100', .7);
  rays(sx, sy, t);
  sunDisc(sx, sy);
  clouds('dusk', cam, t);
  ridgeLayer(cam, .25, FAR, { top: '#9a5576', bot: '#6a3558', y0: 600, y1: 820, rimA: .55, sunX: SUN.x });
  uhudLayer(cam, .4, { top: '#6e3036', bot: '#2a1220', rimA: .85, rimCol: '255,175,110', sunX: SUN.x });
  plain(cam, .6, 772, '#7a4044', '#170a10', '255,170,110');
  return [sx, sy];
}
function qurayshArmy(cam, t, tb, scale = 1) {
  layer(cam, .6, () => {
    const ax = -tb * 3;
    for (const d of ARMY_DUST) if (d.y < 820) ctx.drawImage(DUST, d.x + ax - tb * d.v * .5 - d.s / 2, d.y - d.s / 2 - tb * 1.5, d.s * 1.6, d.s);
    ctx.fillStyle = 'rgba(26,12,16,.92)';
    for (const a of ARMY) { ctx.fillRect(a.x + ax, a.y - a.h * scale, 1.7 * scale, a.h * scale); ctx.beginPath(); ctx.arc(a.x + ax + .85, a.y - a.h * scale - 1, 1.3 * scale, 0, 7); ctx.fill(); }
    for (const b of ARMY_BAN) banner(b.x + ax, b.y, 20 * scale, t, b.ph, b.red ? '#7a1d1d' : '#2a0f12');
    for (const d of ARMY_DUST) if (d.y >= 820) ctx.drawImage(DUST, d.x + ax - tb * d.v * .5 - d.s / 2, d.y - d.s / 2 - tb * 1.5, d.s * 1.6, d.s);
  });
}
function archersWide(t, k, cam) {
  sunsetBackdrop(cam, t);
  layer(cam, .85, () => {
    ctx.beginPath(); ctx.moveTo(850, 1500);
    for (let x = 850; x <= 1850; x += 6) ctx.lineTo(x, hillY(x));
    ctx.lineTo(1850, 1500); ctx.closePath();
    const hg = ctx.createLinearGradient(0, 690, 0, 1000); hg.addColorStop(0, '#26131f'); hg.addColorStop(1, '#0d070c');
    ctx.fillStyle = hg; ctx.fill();
    ctx.beginPath(); for (let x = 860; x <= 1840; x += 6) x === 860 ? ctx.moveTo(x, hillY(x)) : ctx.lineTo(x, hillY(x));
    ctx.strokeStyle = rimGrad(900, 1800, 1600, .9); ctx.lineWidth = 2; ctx.stroke();
    for (const a of ARCHERS) person(a.x, hillY(a.x) + 1, a.s, { t, ph: a.ph, pose: a.k ? 'kneel' : 'stand', weapon: 'bow', rim: [1.1, -.3] });
  });
}
function heroShot(t, tb) {
  const cam = { x: 700 + 4 * tb, y: 600, z: 1.1 + .01 * tb };
  sunsetBackdrop(cam, t);
  qurayshArmy(cam, t, tb);
  ctx.beginPath(); ctx.moveTo(-20, H + 20);
  for (let x = -20; x <= 920; x += 8) ctx.lineTo(x, rockY(x));
  ctx.lineTo(920, H + 200); ctx.lineTo(-20, H + 200); ctx.closePath(); ctx.fillStyle = '#0c060a'; ctx.fill();
  ctx.beginPath(); for (let x = -20; x <= 920; x += 8) x === -20 ? ctx.moveTo(x, rockY(x)) : ctx.lineTo(x, rockY(x));
  ctx.strokeStyle = rimGrad(0, 920, 900, .8); ctx.lineWidth = 3; ctx.stroke();
  grass(t, rockY, '#0b0609');
  person(470, rockY(470) + 2, 4.4, { t, ph: 1.3, weapon: 'bow', rim: [4, -1.2] });
}
function grass(t, yf, col) {
  ctx.strokeStyle = col; ctx.lineWidth = 2.5; ctx.lineCap = 'round';
  for (const tf of TUFTS) {
    const by = yf(tf.x) + 3;
    for (let i = 0; i < tf.n; i++) {
      const lean = (i - tf.n / 2) * 6 - 10 - 8 * Math.sin(t * 2.2 + tf.ph + i * .4), hh = tf.h * (.6 + .4 * ((i * 7) % 5) / 5);
      ctx.beginPath(); ctx.moveTo(tf.x + i * 3, by); ctx.quadraticCurveTo(tf.x + i * 3 + lean * .3, by - hh * .6, tf.x + i * 3 + lean, by - hh); ctx.stroke();
    }
  }
}

// ---------- map ----------
function contour(g, cx, cy, rx, ry, seed, levels, fillCols, stroke) {
  const r = rng(seed), p = [r() * 6, r() * 6, r() * 6];
  for (let k = 0; k < levels; k++) {
    const sc = 1 - k * (.8 / levels);
    g.beginPath();
    for (let i = 0; i <= 120; i++) {
      const a = i / 120 * Math.PI * 2, rr = 1 + .12 * Math.sin(3 * a + p[0] + k * .3) + .07 * Math.sin(5 * a + p[1]) + .04 * Math.sin(9 * a + p[2]);
      const x = cx + Math.cos(a) * rx * sc * rr, y = cy + Math.sin(a) * ry * sc * rr;
      i ? g.lineTo(x, y) : g.moveTo(x, y);
    }
    g.closePath(); g.fillStyle = fillCols[Math.min(k, fillCols.length - 1)]; g.fill();
    g.strokeStyle = stroke; g.lineWidth = 1.4; g.stroke();
  }
}
const MAP = (() => {
  const c = mk(), g = c.getContext('2d');
  const gr = g.createRadialGradient(W / 2, H / 2, 200, W / 2, H / 2, 1200); gr.addColorStop(0, '#efe0bd'); gr.addColorStop(1, '#c9a874');
  g.fillStyle = gr; g.fillRect(0, 0, W, H);
  const r = rng(77);
  for (let i = 0; i < 260; i++) { const x = r() * W, y = r() * H, rad = 20 + r() * 120, q = g.createRadialGradient(x, y, 0, x, y, rad), dark = r() < .5; q.addColorStop(0, dark ? 'rgba(120,80,40,.07)' : 'rgba(255,250,230,.07)'); q.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = q; g.fillRect(x - rad, y - rad, 2 * rad, 2 * rad); }
  g.strokeStyle = 'rgba(90,55,25,.6)'; g.lineWidth = 3; g.strokeRect(60, 60, W - 120, H - 120); g.lineWidth = 1; g.strokeRect(74, 74, W - 148, H - 148);
  // Mount Uhud
  contour(g, 960, 230, 720, 150, 101, 6, ['rgba(150,100,60,.25)', 'rgba(140,90,50,.3)', 'rgba(130,80,45,.35)', 'rgba(120,72,40,.4)', 'rgba(110,64,35,.45)', 'rgba(100,58,30,.5)'], 'rgba(90,55,25,.55)');
  // archers' hill
  contour(g, 1330, 585, 95, 52, 202, 4, ['rgba(150,100,60,.25)', 'rgba(135,85,48,.35)', 'rgba(120,72,40,.45)', 'rgba(105,60,32,.55)'], 'rgba(90,55,25,.55)');
  // wadi Qanat
  g.strokeStyle = 'rgba(70,110,140,.45)'; g.lineWidth = 5; g.lineCap = 'round'; g.beginPath();
  for (let x = 120; x <= 1800; x += 10) { const y = 528 + Math.sin(x * .006) * 18 + Math.sin(x * .017) * 6; x === 120 ? g.moveTo(x, y) : g.lineTo(x, y); }
  g.stroke();
  // compass
  g.save(); g.translate(1740, 190); g.fillStyle = 'rgba(90,55,25,.75)';
  g.beginPath(); g.moveTo(0, -46); g.lineTo(9, 0); g.lineTo(0, 46); g.lineTo(-9, 0); g.closePath(); g.fill();
  g.beginPath(); g.moveTo(-36, 0); g.lineTo(0, 7); g.lineTo(36, 0); g.lineTo(0, -7); g.closePath(); g.globalAlpha = .5; g.fill(); g.globalAlpha = 1;
  g.font = '700 24px Cinzel, Georgia, serif'; g.textAlign = 'center'; g.fillText('N', 0, -54); g.restore();
  return c;
})();
const MAP_ARCHERS = (() => { const r = rng(303), a = []; for (let i = 0; i < 50; i++) { const ang = r() * 6.28, rr = Math.sqrt(r()); a.push([1330 + Math.cos(ang) * rr * 52, 585 + Math.sin(ang) * rr * 26]); } return a; })();
const FLANK = [[1360, 790], [1520, 720], [1560, 560], [1480, 440], [1300, 405], [1100, 420]];
function polyPartial(pts, k) {
  const seg = []; let total = 0;
  for (let i = 1; i < pts.length; i++) { const l = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); seg.push(l); total += l; }
  let rem = total * clamp(k, 0, 1); const out = [pts[0]];
  for (let i = 1; i < pts.length; i++) {
    if (rem >= seg[i - 1]) { out.push(pts[i]); rem -= seg[i - 1]; }
    else { const u = rem / seg[i - 1]; out.push([lerp(pts[i - 1][0], pts[i][0], u), lerp(pts[i - 1][1], pts[i][1], u)]); break; }
  }
  return out;
}
function mapArrow(pts, k, col, width, dash) {
  if (k <= 0) return;
  const p = polyPartial(pts, k);
  ctx.save(); ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = width; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  if (dash) ctx.setLineDash(dash);
  ctx.beginPath(); p.forEach((q, i) => i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1])); ctx.stroke();
  ctx.setLineDash([]);
  if (p.length > 1) {
    const a = p[p.length - 1], b = p[p.length - 2], ang = Math.atan2(a[1] - b[1], a[0] - b[0]), s = width * 3.2;
    ctx.beginPath(); ctx.moveTo(a[0] + Math.cos(ang) * s, a[1] + Math.sin(ang) * s);
    ctx.lineTo(a[0] + Math.cos(ang + 2.4) * s, a[1] + Math.sin(ang + 2.4) * s); ctx.lineTo(a[0] + Math.cos(ang - 2.4) * s, a[1] + Math.sin(ang - 2.4) * s); ctx.fill();
  }
  ctx.restore();
}
function mapBlock(x, y, w, h, col, a) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a; ctx.fillStyle = col; ctx.fillRect(x, y, w, h);
  ctx.strokeStyle = 'rgba(40,20,10,.6)'; ctx.lineWidth = 1.5; ctx.strokeRect(x, y, w, h);
  ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip();
  ctx.strokeStyle = 'rgba(255,255,255,.18)'; ctx.lineWidth = 2;
  for (let i = -h; i < w; i += 10) { ctx.beginPath(); ctx.moveTo(x + i, y + h); ctx.lineTo(x + i + h, y); ctx.stroke(); }
  ctx.restore();
}
const MAPTXT = { font: '600 24px Cinzel, Georgia, serif', col: '#4a2a14', shadow: false, ls: '3px' };
function drawMap(lt, D, s) {
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
  const z = 1 + .03 * clamp(lt / D, 0, 1);
  ctx.translate(W / 2, H / 2); ctx.scale(z, z); ctx.translate(-W / 2, -H / 2);
  ctx.drawImage(MAP, 0, 0);
  label('UHUD JANGI · HIJRIY 3-YIL, SHAVVOL', W / 2, 120, Object.assign({}, MAPTXT, { font: '700 30px Cinzel, Georgia, serif', ls: '6px' }));
  label("UHUD TOG'I", 960, 236, Object.assign({}, MAPTXT, { font: '700 34px Cinzel, Georgia, serif', ls: '10px', col: '#3a1e0c' }));
  label('Qanot vodiysi', 260, 512, Object.assign({}, MAPTXT, { font: 'italic 500 24px "Cormorant Garamond", Georgia, serif', col: 'rgba(40,70,100,.85)', ls: '1px' }));
  label('sxema — masshtabsiz', W - 110, H - 96, Object.assign({}, MAPTXT, { font: 'italic 500 20px "Cormorant Garamond", Georgia, serif', align: 'right', ls: '1px', col: 'rgba(74,42,20,.7)' }));
  label('↓ Madina tomon', W / 2, H - 100, Object.assign({}, MAPTXT, { font: 'italic 500 24px "Cormorant Garamond", Georgia, serif', ls: '1px' }));
  const mY = s.mPos || 0, green = '#2f6b3a', red = '#8a2a22';
  [780, 900, 1020].forEach(x => mapBlock(x, 455 + mY, 112, 32, green, s.muslims || 0));
  label('MUSULMONLAR · 700', 760, 478 + mY, Object.assign({}, MAPTXT, { align: 'right', alpha: s.muslims || 0, col: '#1f4a28' }));
  const qs = s.qScatter || 0;
  [700, 840, 980, 1120].forEach((x, i) => mapBlock(x + (i - 1.5) * 30 * qs, 780 + qs * (40 + i * 12), 120, 32, red, (s.quraysh || 0) * (1 - qs * .5)));
  label('QURAYSH · 3 000', 920, 862 + qs * 70, Object.assign({}, MAPTXT, { alpha: (s.quraysh || 0), col: '#6a1a14' }));
  mapBlock(1300, 776, 90, 28, '#a3382c', s.cav || 0);
  label('XOLID — OTLIQLAR', 1345, 836, Object.assign({}, MAPTXT, { alpha: s.cav || 0, font: '600 20px Cinzel, Georgia, serif', col: '#6a1a14' }));
  mapBlock(530, 776, 90, 28, '#a3382c', s.cav || 0);
  label('IKRIMA — OTLIQLAR', 575, 836, Object.assign({}, MAPTXT, { alpha: s.cav || 0, font: '600 20px Cinzel, Georgia, serif', col: '#6a1a14' }));
  label('KAMONCHILAR TEPALIGI', 1440, 590, Object.assign({}, MAPTXT, { align: 'left', alpha: s.hill || 0, col: '#3a1e0c' }));
  label("Aynayn tog'i", 1440, 620, Object.assign({}, MAPTXT, { align: 'left', alpha: s.hill || 0, font: 'italic 500 24px "Cormorant Garamond", Georgia, serif', ls: '1px' }));
  const nA = Math.round(s.archers || 0), gone = Math.round(s.gone || 0);
  for (let i = 0; i < nA; i++) {
    if (i >= 50 - gone && i < 50) continue;
    ctx.fillStyle = green; ctx.beginPath(); ctx.arc(MAP_ARCHERS[i][0], MAP_ARCHERS[i][1], 4.5, 0, 7); ctx.fill();
  }
  if (s.archerLabel) label('50 KAMONCHI · ABDULLOH IBN JUBAYR', 1330, 670, Object.assign({}, MAPTXT, { alpha: s.archerLabel, font: '600 20px Cinzel, Georgia, serif', col: '#1f4a28' }));
  if (s.threat) mapArrow(FLANK, s.threat, `rgba(150,30,25,${s.threatA ?? .8})`, 5, [14, 12]);
  if (s.block) { ctx.save(); ctx.globalAlpha = s.block; ctx.strokeStyle = '#1f4a28'; ctx.lineWidth = 7; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(1500, 610); ctx.lineTo(1560, 670); ctx.moveTo(1560, 610); ctx.lineTo(1500, 670); ctx.stroke(); ctx.restore(); }
  if (s.attack) mapArrow(FLANK, s.attack, '#b02a20', 10);
  if (s.ret) { mapArrow([[820, 900], [860, 560]], s.ret, 'rgba(150,30,25,.85)', 7); mapArrow([[1080, 920], [1040, 560]], s.ret, 'rgba(150,30,25,.85)', 7); }
  if (s.burst) { ctx.save(); ctx.globalAlpha = s.burst; ctx.strokeStyle = '#b02a20'; ctx.lineWidth = 4; for (let i = 0; i < 3; i++) { ctx.beginPath(); ctx.arc(1000, 440 + mY, 40 + i * 26 + (lt * 40) % 26, 0, 7); ctx.stroke(); } ctx.restore(); }
  ctx.restore();
}

// ---------- scenes ----------
const SC = {};

SC.title = (lt, D, L, t) => {
  const cam = { x: 960, y: 540, z: 1 + .08 * ease(clamp(lt / D, 0, 1)) };
  sky(SKY.night); stars(t, 1, H * .75, true);
  const [mx, my] = scr(cam, .03, 1500, 230); moon(mx, my);
  const ss = clamp((lt - 3.5) / 1.0, 0, 1);
  if (ss > 0 && ss < 1) {
    const x = 500 + ss * 520, y = 140 + ss * 190, g = ctx.createLinearGradient(x - 160, y - 58, x, y);
    g.addColorStop(0, 'rgba(255,255,255,0)'); g.addColorStop(1, `rgba(255,255,255,${.9 * Math.sin(ss * Math.PI)})`);
    ctx.strokeStyle = g; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x - 160, y - 58); ctx.lineTo(x, y); ctx.stroke();
  }
  uhudLayer(cam, .3, { top: '#1c2244', bot: '#0e1228', rimA: .45, rimCol: '190,205,255', sunX: 1500, ravA: .5 });
  dunes(cam, [['#141a36', '#0b0f22'], ['#0f1430', '#080b1a'], ['#090c1e', '#05060f']], { rimA: .35, rimCol: '190,205,255', sunX: 1500 });
  motes(t, '200,210,255', .5, 3);
  titleBlock(smooth(L(1), L(1) + 1.4, lt), 'UHUD', 'Sabr va itoat qissasi', 'HIJRIY 3-YIL · MILODIY 625', 470);
};

SC.makkah = (lt, D, L, t) => {
  const cam = { x: 900 + 120 * (lt / D), y: 540, z: 1.05 };
  const [sx, sy] = scr(cam, .05, 820, 640);
  sky(SKY.duskRed); stars(t, .5, 300);
  glow(sx, sy, 900, '255,150,90', .65); rays(sx, sy, t, { a: .1 }); sunDisc(sx, sy, 80);
  clouds('duskRed', cam, t);
  const mk1 = MAKKAH_FAR, mk2 = MAKKAH_NEAR;
  ridgeLayer(cam, .25, mk1, { top: '#7a3a5a', bot: '#4a2240', y0: 380, y1: 800, rimA: .5, sunX: 820 });
  ridgeLayer(cam, .45, mk2, { top: '#3a1a2a', bot: '#1a0a14', y0: 350, y1: 900, rimA: .8, sunX: 820, rimCol: '255,160,100' });
  if (!TOWN_M) TOWN_M = makeTown(7, 1500, 230, '#1a0e18', '255,190,110', .3);
  layer(cam, .6, () => { ctx.drawImage(TOWN_M, 220, 610); });
  plain(cam, .7, 860, '#2a1420', '#0d060a');
  layer(cam, .75, () => { for (let i = 0; i < 9; i++) torch(380 + i * 150, 900, t, i * 1.7, 1); });
  const grow = smooth(L(1), L(1) + 4, lt), n = Math.round(50 + 110 * grow);
  layer(cam, .9, () => {
    const r = rng(61);
    for (let i = 0; i < 160; i++) {
      const row = i % 3, x = 250 + r() * 1500, s = .44 + row * .05, y = 935 + row * 26, ph = r() * 6, wpn = r() < .4 ? 'spear' : 'none';
      if (i >= n) continue;
      person(x, y, s, { t, ph, weapon: wpn, flip: r() < .5, rim: [1, -.3], rimCol: 'rgba(255,170,100,.8)' });
    }
    for (let i = 0; i < 6; i++) banner(400 + i * 230, 960, 70, t, i, '#7a1d1d');
  });
};

SC.march = (lt, D, L, t) => {
  const cut = L(1) + 2.0;
  const shot1 = () => {
    const cam = { x: 960 + lt * 6, y: 540, z: 1.02 };
    const [sx, sy] = scr(cam, .05, 380, 250);
    sky(SKY.day); glow(sx, sy, 700, '255,250,225', .8); sunDisc(sx, sy, 60, '#ffffff', '#fffbe8');
    clouds('day', cam, t, { dy: -40 });
    ridgeLayer(cam, .25, FAR, { top: '#d0a488', bot: '#b88a70', y0: 600, y1: 800 });
    dunes(cam, [['#e2ae72', '#c98a52'], ['#d39a5e', '#b4733e'], ['#b87a44', '#8e5428']], { rimA: .45, rimCol: '255,245,215', sunX: 380 });
    layer(cam, .75, () => {
      for (let i = 0; i < 44; i++) {
        const x = mod(-400 + i * 64 + lt * 38, 2800) - 400, y = DUNES[1][clamp(Math.round((x + 900) / 10), 0, DUNES[1].length - 1)][1] + 26;
        ctx.globalAlpha = .35; ctx.drawImage(DUSTDAY, x - 90, y - 50, 150, 60); ctx.globalAlpha = 1;
        const o = { t, ph: i * 1.3, col: '#2a160e' };
        if (i % 3 === 0) camelRider(x, y, .5, o); else if (i % 3 === 1) cavalry(x, y, .5, Object.assign(o, { gallop: .45 })); else person(x, y, .5, Object.assign(o, { pose: 'walk', weapon: 'spear' }));
      }
    });
    statCard(smooth(L(0) + .4, L(0) + 1.2, lt), 560, 230, '3 000', 'KISHI', undefined, true);
    statCard(smooth(L(0) + 2.6, L(0) + 3.4, lt), 960, 230, '200', 'OT', undefined, true);
    statCard(smooth(L(0) + 4.4, L(0) + 5.2, lt), 1360, 230, '700', 'SOVUT', undefined, true);
  };
  const shot2 = () => {
    const tb = lt - cut, cam = { x: 960 + tb * 260, y: 560, z: 1 };
    sky(SKY.afternoon); const [sx, sy] = scr(cam, .05, 1300, 380);
    glow(sx, sy, 800, '255,220,160', .8); sunDisc(sx, sy, 60);
    clouds('afternoon', cam, t, { speed: 4 });
    ridgeLayer(cam, .2, FAR, { top: '#c79a80', bot: '#a87a66', y0: 600, y1: 800 });
    ridgeLayer(cam, .45, DUNES[1], { top: '#c98a52', bot: '#a86a38', y0: 820, y1: 1080, rimA: .5, rimCol: '255,240,200', sunX: 1300 });
    ctx.fillStyle = '#8a5428'; ctx.fillRect(0, 930, W, 400);
    const r = rng(5);
    for (let i = 0; i < 40; i++) { const x = mod(r() * W - tb * 900, W + 60) - 30, y = 940 + r() * 130; ctx.fillStyle = 'rgba(60,30,14,.5)'; ctx.fillRect(x, y, 6 + r() * 14, 3); }
    for (let i = 0; i < 6; i++) {
      const x = 200 + i * 300 + Math.sin(t * .8 + i) * 30, y = 990 + (i % 2) * 40, s = 2.1 + (i % 2) * .3;
      ctx.globalAlpha = .5; ctx.drawImage(DUSTDAY, x - 300, y - 110, 260, 120); ctx.globalAlpha = 1;
      cavalry(x, y, s, { t, ph: i * 2.1, gallop: 1.25, weapon: 'spear', col: '#1a0c08', rim: [3, -1], rimCol: 'rgba(255,230,180,.85)' });
    }
    label('XOLID IBN VALID OTLIQLARI', 110, 150, { alpha: smooth(1.2, 2, tb), align: 'left', font: '600 30px Cinzel, Georgia, serif', ls: '5px' });
    label("Quraysh qo'shinining o'ng qanoti", 110, 192, { alpha: smooth(1.5, 2.3, tb), align: 'left', font: 'italic 500 30px "Cormorant Garamond", Georgia, serif', ls: '1px', col: '#ffe2b8' });
  };
  blend(smooth(cut, cut + 1, lt), shot1, shot2);
};

SC.madinah = (lt, D, L, t) => {
  const cam = { x: 900 + 110 * (lt / D), y: 540, z: 1 + .07 * ease(lt / D) };
  sky(SKY.night); stars(t, 1, H * .7, true);
  const [mx, my] = scr(cam, .03, 1450, 190); moon(mx, my);
  ridgeLayer(cam, .2, FAR, { top: '#141c3a', bot: '#0c1228', y0: 620, y1: 820, rimA: .3, rimCol: '190,205,255', sunX: 1450 });
  uhudLayer(cam, .3, { top: '#1a2046', bot: '#0c1028', rimA: .45, rimCol: '190,205,255', sunX: 1450, ravA: .4 });
  layer(cam, .55, () => { [[300, 860, 300], [520, 860, 260], [1500, 860, 320], [1700, 860, 280], [1250, 855, 240]].forEach((p, i) => palm(p[0], p[1], p[2], t, i, '#0a0d1e')); });
  if (!TOWN_D) TOWN_D = makeTown(19, 1700, 170, '#0d0f20', '255,200,120', .35);
  layer(cam, .6, () => { ctx.drawImage(TOWN_D, 100, 720); });
  plain(cam, .7, 880, '#0c0e1e', '#04050c');
  layer(cam, .72, () => {
    // the simple mosque: low walls, palm-trunk roof, lamplight in doorways
    ctx.fillStyle = '#090a16'; ctx.fillRect(780, 805, 380, 78);
    ctx.fillRect(770, 798, 400, 9);
    for (let i = 0; i < 4; i++) { const x = 830 + i * 90; glow(x + 14, 850, 70, '255,190,110', .35); ctx.fillStyle = '#ffcf86'; ctx.fillRect(x, 830, 28, 50); }
    glow(970, 790, 200, '255,190,110', .12 + .05 * Math.sin(t * 3));
    const gather = smooth(L(2), L(2) + 3, lt);
    const r = rng(81);
    for (let i = 0; i < 22; i++) {
      const x = 700 + r() * 540, ph = r() * 6, s = .55 + r() * .05;
      if (i / 22 > .25 + gather * .75) continue;
      person(x, 905 + (i % 2) * 10, s, { t, ph, weapon: i % 3 ? 'spear' : 'none', flip: x > 970, col: '#050611', rim: [-1, -.3], rimCol: 'rgba(255,200,130,.6)' });
    }
  });
  layer(cam, 1.0, () => { palm(60, 1090, 700, t, 3, '#03040a'); palm(1860, 1100, 620, t, 5, '#03040a'); });
  motes(t, '255,220,150', .35, 2);
};

SC.split = (lt, D, L, t) => {
  const cam = { x: 960, y: 540, z: 1.02 + .04 * (lt / D) };
  const [sx, sy] = scr(cam, .05, 1500, 690 - lt * 4);
  sky(SKY.dawn); stars(t, .3 * (1 - lt / D), 250);
  glow(sx, sy, 900, '255,200,140', .7); rays(sx, sy, t, { a: .1, col: '255,220,170' }); sunDisc(sx, sy, 70);
  clouds('dawn', cam, t);
  uhudLayer(cam, .3, { top: '#5a4a7a', bot: '#3a2f55', rimA: .7, rimCol: '255,210,160', sunX: 1500 });
  plain(cam, .6, 790, '#6a4a5a', '#24161f', '255,200,150');
  const turnT = L(1) + .8;
  layer(cam, .85, () => {
    for (let row = 0; row < 3; row++) {
      const n = 34, y = 900 + row * 46, s = .5 + row * .07;
      for (let i = 0; i < n; i++) {
        const id = row * n + i, base = -300 + i * 58 + (row % 2) * 29, leaver = (id * 7) % 10 < 3;
        const tt = turnT + (id % 9) * .22;
        let x, flip = false, alpha = 1;
        if (leaver && lt > tt) { x = base + tt * 22 - (lt - tt) * 30; flip = true; alpha = 1 - smooth(tt + 1, tt + 6, lt); }
        else x = base + lt * 22;
        if (alpha <= 0) continue;
        person(x, y, s, { t, ph: id * .77, pose: 'walk', weapon: id % 4 ? 'spear' : 'bow', flip, alpha, rim: [1.2, -.4], rimCol: 'rgba(255,215,160,.85)' });
      }
    }
  });
  const cnt = Math.round(lerp(1000, 700, smooth(L(2) - .2, L(2) + 1.4, lt)));
  statCard(smooth(L(0) + .3, L(0) + 1.1, lt), 960, 200, cnt.toLocaleString('en-US').replace(',', ' '), "MO'MINLAR");
  statCard(smooth(L(2) + 2.2, L(2) + 3, lt), 1460, 200, '3 000', 'QURAYSH', '#ffb8a0');
  label('qarshi', 1210, 205, { alpha: smooth(L(2) + 2.2, L(2) + 3, lt), font: 'italic 500 40px "Cormorant Garamond", Georgia, serif' });
};

SC.map = (lt, D, L) => {
  drawMap(lt, D, {
    muslims: smooth(.8, 1.8, lt),
    hill: smooth(L(1) + .2, L(1) + 1, lt),
    quraysh: smooth(L(1) + .6, L(1) + 1.6, lt), cav: smooth(L(1) + 1.6, L(1) + 2.4, lt),
    threat: smooth(L(1) + 3, L(1) + 5.5, lt), threatA: .8 * (1 - smooth(L(2) + 3.5, L(2) + 4.5, lt) * .6),
    archers: 50 * smooth(L(2) + .8, L(2) + 3, lt), archerLabel: smooth(L(2) + 2, L(2) + 3, lt),
    block: smooth(L(2) + 3.5, L(2) + 4.2, lt),
  });
};

SC.archers = (lt, D, L, t) => {
  const cut = L(2) - .4;
  blend(smooth(cut, cut + 1, lt),
    () => { const k = ease(clamp(lt / Math.max(cut, 1), 0, 1)); archersWide(t, k, { x: lerp(960, 1350, k), y: lerp(540, 690, k), z: lerp(1, 1.7, k) }); },
    () => heroShot(t, lt - cut));
  motes(t, '255,190,120', 1);
};

SC.battle = (lt, D, L, t) => {
  const push = smooth(L(2), L(2) + 5, lt);
  const cam = { x: 960 + 120 * push, y: 560, z: 1.06 };
  const [sx, sy] = scr(cam, .05, 1500, 300);
  sky(SKY.afternoon); glow(sx, sy, 800, '255,225,170', .75); sunDisc(sx, sy, 60);
  clouds('afternoon', cam, t, { dy: -30 });
  uhudLayer(cam, .3, { top: '#8a5a48', bot: '#5a3530', rimA: .4, rimCol: '255,230,190', sunX: 1500 });
  plain(cam, .5, 790, '#b08560', '#5a3a28', '255,230,190');
  // archers' hill in the distance
  layer(cam, .55, () => {
    ctx.beginPath(); ctx.moveTo(1450, 900); ctx.quadraticCurveTo(1560, 760, 1680, 755); ctx.quadraticCurveTo(1800, 760, 1920, 900); ctx.closePath();
    ctx.fillStyle = '#6a4232'; ctx.fill();
    for (let i = 0; i < 9; i++) person(1610 + i * 14, 760 + Math.abs(i - 4) * 1.2, .22, { t, ph: i, weapon: 'bow', col: '#2a1610' });
  });
  const contact = 960 + 160 * push, mF = lerp(640, contact - 20, smooth(0, 2.2, lt)), qF = lerp(1300, contact + 20, smooth(0, 2.2, lt));
  const met = lt > 2;
  layer(cam, .85, () => {
    for (let i = 0; i < 6; i++) { const x = contact - 100 + i * 40 + Math.sin(t + i) * 20; ctx.globalAlpha = met ? .5 : .15; ctx.drawImage(DUSTDAY, x - 100, 840 + (i % 2) * 30, 220, 120); }
    ctx.globalAlpha = 1;
    for (let row = 3; row >= 0; row--) {
      const y = 915 + row * 30, s = .78 + row * .07;
      for (let c = 0; c < 16; c++) {
        const x = qF + c * 46 + (row % 2) * 23;
        person(x, y, s, { t, ph: c * 1.3 + row, pose: met && c < 2 ? 'stand' : 'walk', weapon: met && c < 2 ? 'sword' : (c % 3 ? 'spear' : 'sword'), shield: c % 2 === 0, flip: true, col: '#3a1a12' });
      }
      for (let c = 0; c < 11; c++) {
        const x = mF - c * 50 - (row % 2) * 25;
        person(x, y, s, { t, ph: c * 1.7 + row * 2, pose: met && c < 2 ? 'stand' : 'walk', weapon: met && c < 2 ? 'sword' : (c % 3 ? 'spear' : 'sword'), shield: c % 2 === 1, col: '#1a120c' });
      }
    }
    // Quraysh standards falling one by one
    for (let b = 0; b < 3; b++) {
      const ft = L(1) + .4 + b * 1.1, fall = smooth(ft, ft + .7, lt), x = qF + 40 + b * 150;
      if (fall >= 1 && lt > ft + 1.5) continue;
      ctx.save(); ctx.globalAlpha = 1 - smooth(ft + .9, ft + 1.5, lt); banner(x, 925, 90, t, b, '#7a1d1d', fall * 1.45); ctx.restore();
    }
    banner(mF - 120, 925, 90, t, 9, '#1a1a1a');
  });
  // arrow volleys from the hill
  const [hx, hy] = scr(cam, .55, 1680, 745);
  for (let v = 0; v < 14; v++) {
    const st = 1 + v * 1.0; const p = (lt - st) / 1.3; if (p < 0 || p > 1) continue;
    for (let a = 0; a < 7; a++) {
      const tx = 1500 + a * 50 + (v % 3) * 40 + 120 * push, ty = 930 + (a % 3) * 12;
      const x = lerp(hx, tx, p), y = lerp(hy, ty, p) - Math.sin(p * Math.PI) * 220;
      const dx = tx - hx, dy = (ty - hy) - Math.cos(p * Math.PI) * 220 * Math.PI;
      arrow(x, y, Math.atan2(dy, dx), 22, '#1a0e08', 2);
    }
  }
};

const ROCKS = genRidge(71, -50, 900, 8, (x, p) => 760 + Math.pow(Math.max(0, x - 380) / 520, 1.8) * 360 - 60 * Math.abs(Math.sin(x * .011 + p[0])) - 20 * Math.sin(x * .03 + p[1]));
SC.hamzah = (lt, D, L, t) => {
  const cut = L(2) + Math.max(2.3, (L.E(2) - L(2)) * .5);
  const shot1 = () => {
    const pan = smooth(L(1), L(1) + 4, lt);
    const cam = { x: lerp(960, 760, pan), y: 560, z: lerp(1, 1.12, pan) };
    const [sx, sy] = scr(cam, .05, 1250, 640);
    sky(SKY.blood); glow(sx, sy, 950, '255,140,80', .7); rays(sx, sy, t, { a: .1, col: '255,170,110' }); sunDisc(sx, sy, 90, '#fff3d0', '#ffc070');
    clouds('blood', cam, t);
    uhudLayer(cam, .3, { top: '#5a1a22', bot: '#2a0a12', rimA: .8, rimCol: '255,150,90', sunX: 1250 });
    plain(cam, .55, 790, '#6a2a24', '#1a0808', '255,140,90');
    layer(cam, .65, () => {
      const r = rng(91);
      for (let i = 0; i < 26; i++) { const x = 900 + r() * 900, y = 850 + r() * 30; ctx.globalAlpha = .4; ctx.drawImage(DUST, x - 80, y - 60, 160, 80); ctx.globalAlpha = 1; person(x + Math.sin(t * .6 + i) * 10, y, .3, { t, ph: i, pose: 'stand', weapon: i % 2 ? 'sword' : 'spear', flip: i % 2 === 0, col: '#2a0a0c' }); }
    });
    ridgeLayer(cam, 1.0, ROCKS, { top: '#120608', bot: '#050203', y0: 700, y1: 1080, rimA: .7, rimCol: '255,140,90', sunX: 1250 });
    // the spear
    const sp = clamp((lt - (L(2) + .8)) / 1.4, 0, 1);
    if (sp > 0 && sp < 1) {
      const x0 = 520, y0 = 720, x1 = 2000, y1 = 760, x = lerp(x0, x1, sp), y = lerp(y0, y1, sp) - Math.sin(sp * Math.PI) * 260;
      const ang = Math.atan2((y1 - y0) - Math.cos(sp * Math.PI) * 260 * Math.PI, x1 - x0);
      ctx.save(); ctx.globalCompositeOperation = 'lighter';
      for (let k = 1; k < 8; k++) { ctx.globalAlpha = .08 * (8 - k) / 8; arrow(x - Math.cos(ang) * k * 18, y - Math.sin(ang) * k * 18, ang, 120, '#ffb070', 5); }
      ctx.restore();
      arrow(x, y, ang, 130, '#0a0405', 4);
    }
    titleBlock(0, '', '');
    const k = win(lt, L(0) + .3, L(1) + .6, .9);
    label('HAMZA IBN ABDULMUTTALIB', W / 2, 200, { alpha: k, font: '700 54px Cinzel, Georgia, serif', ls: '6px', col: '#ffd890', blur: 24 });
    label('Asadulloh — Allohning sheri', W / 2, 262, { alpha: k, font: 'italic 500 42px "Cormorant Garamond", Georgia, serif', ls: '1px' });
    label('roziyallohu anhu', W / 2, 306, { alpha: k * .9, font: 'italic 500 26px "Cormorant Garamond", Georgia, serif', ls: '1px', col: '#f0c8a0' });
  };
  const shot2 = () => {
    const tb = lt - cut;
    sky(SKY.ash);
    glow(500, 120, 900, '255,220,170', .25);
    rays(300, -100, t, { n: 5, a: .07, from: .5, span: .6, col: '255,230,190', len: 1500 });
    const g = ctx.createLinearGradient(0, 560, 0, H); g.addColorStop(0, '#4a3430'); g.addColorStop(1, '#150c0c'); ctx.fillStyle = g; ctx.fillRect(0, 560, W, H);
    const r = rng(93);
    for (let i = 0; i < 160; i++) { const y = 600 + Math.pow(r(), .7) * 480, x = r() * W; ctx.fillStyle = `rgba(20,10,10,${.2 + r() * .3})`; ctx.fillRect(x, y, 4 + (y - 560) * .05 * r() * 4, 2 + (y - 560) * .01); }
    // fallen sword
    ctx.save(); ctx.translate(960, 820); ctx.rotate(-.12);
    ctx.fillStyle = 'rgba(255,210,150,.5)'; ctx.fillRect(-300, -6, 560, 4);
    ctx.fillStyle = '#0c0606'; ctx.beginPath(); ctx.moveTo(-300, -4); ctx.lineTo(240, -6); ctx.lineTo(268, 2); ctx.lineTo(240, 8); ctx.lineTo(-300, 6); ctx.closePath(); ctx.fill();
    ctx.fillRect(-312, -26, 14, 52); ctx.fillRect(-380, -6, 70, 12); ctx.beginPath(); ctx.arc(-388, 0, 10, 0, 7); ctx.fill();
    ctx.restore();
    for (let i = 0; i < 14; i++) { const x = 700 + r() * 600, y = 760 + r() * 80 - tb * 6, s = 140 + r() * 200; ctx.globalAlpha = .35 * (1 - smooth(0, 6, tb)); ctx.drawImage(DUST, x - s / 2, y - s / 3, s, s * .6); }
    ctx.globalAlpha = 1;
    motes(t, '255,230,190', .6, 2);
    const k = smooth(.8, 2, tb);
    label('إِنَّا لِلَّهِ وَإِنَّا إِلَيْهِ رَاجِعُونَ', W / 2, 330, { alpha: k, font: '700 72px Amiri, serif', ls: '0px', col: '#fff0d0', blur: 24 });
    label('«Albatta, biz Allohnikimiz va albatta Unga qaytuvchimiz.»', W / 2, 410, { alpha: k, font: 'italic 500 36px "Cormorant Garamond", Georgia, serif', ls: '0px' });
  };
  blend(smooth(cut, cut + .8, lt), shot1, shot2);
};

const SPOIL_HILL = x => x < 640 ? 760 + 6 * Math.sin(x * .04) : 760 + Math.pow(x - 640, 1.6) * .0136;
const TENTS = (() => { const r = rng(111), a = []; for (let i = 0; i < 14; i++) a.push({ x: 1050 + r() * 700, y: 862 + r() * 26, w: 40 + r() * 40, h: 26 + r() * 20 }); return a; })();
const GLINTS = (() => { const r = rng(113), a = []; for (let i = 0; i < 40; i++) a.push({ x: 1000 + r() * 800, y: 870 + r() * 40, ph: r() * 6 }); return a; })();
SC.spoils = (lt, D, L, t) => {
  const cam = { x: 960 + 40 * (lt / D), y: 560, z: 1.04 };
  const [sx, sy] = scr(cam, .05, 1400, 430);
  sky(SKY.afternoon); glow(sx, sy, 850, '255,215,150', .8); rays(sx, sy, t, { a: .08 }); sunDisc(sx, sy, 64);
  clouds('afternoon', cam, t, { dy: -20 });
  uhudLayer(cam, .3, { top: '#94604a', bot: '#5e3a30', rimA: .45, rimCol: '255,225,180', sunX: 1400 });
  plain(cam, .55, 800, '#b88a62', '#5a3a28', '255,225,180');
  layer(cam, .6, () => {
    for (const tn of TENTS) tent(tn.x, tn.y, tn.w, tn.h, '#5a3424');
    const gl = .3 + .7 * smooth(L(1), L(1) + 2, lt);
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    for (const g of GLINTS) { const a = gl * (.5 + .5 * Math.sin(t * 4 + g.ph)); ctx.globalAlpha = a; ctx.drawImage(GOLD, g.x - 10, g.y - 10, 20, 20); }
    ctx.restore();
    // Quraysh fleeing
    const fl = lt;
    for (let i = 0; i < 40; i++) {
      const x = 1200 + (i % 10) * 26 + fl * 70 + (i * 37) % 90, y = 830 + (i % 4) * 8, a = 1 - smooth(2, 9, fl);
      if (a <= 0) continue;
      person(x, y, .28, { t, ph: i, pose: 'run', weapon: 'none', col: '#3a1a12', alpha: a });
    }
    ctx.globalAlpha = .4 * (1 - smooth(4, 10, lt)); ctx.drawImage(DUSTDAY, 1300 + lt * 60, 780, 500, 120); ctx.globalAlpha = 1;
  });
  layer(cam, .9, () => {
    ctx.beginPath(); ctx.moveTo(-200, 1500); for (let x = -200; x <= 1300; x += 8) ctx.lineTo(x, SPOIL_HILL(Math.max(x, 0))); ctx.lineTo(1300, 1500); ctx.closePath();
    const hg = ctx.createLinearGradient(0, 740, 0, 1080); hg.addColorStop(0, '#3a2018'); hg.addColorStop(1, '#120806'); ctx.fillStyle = hg; ctx.fill();
    ctx.beginPath(); for (let x = 0; x <= 1300; x += 8) x === 0 ? ctx.moveTo(x, SPOIL_HILL(x)) : ctx.lineTo(x, SPOIL_HILL(x));
    ctx.strokeStyle = rimGrad(0, 1300, 1300, .7, '255,220,170'); ctx.lineWidth = 2.5; ctx.stroke();
    const stay = new Set([2, 7, 12, 17]);
    let left = 0;
    for (let i = 0; i < 20; i++) {
      const bx = 180 + i * 23;
      if (stay.has(i)) { person(bx, SPOIL_HILL(bx) + 1, .55, { t, ph: i, weapon: 'bow', rim: [1.4, -.4], rimCol: 'rgba(255,225,170,.9)' }); continue; }
      const ts = L(2) + (L.E(2) - L(2)) * .55 + (i % 8) * .4 + (i > 10 ? .3 : 0);
      if (lt < ts) { person(bx, SPOIL_HILL(bx) + 1, .55, { t, ph: i, weapon: 'bow', rim: [1.4, -.4], rimCol: 'rgba(255,225,170,.9)' }); continue; }
      const x = bx + (lt - ts) * 70, a = 1 - smooth(1250, 1350, x);
      if (a > 0) person(x, SPOIL_HILL(x) + 1, .55, { t, ph: i, pose: 'walk', weapon: 'bow', alpha: a, rim: [1.4, -.4], rimCol: 'rgba(255,225,170,.9)' });
      if (x > 640) left++;
    }
    const n = Math.round(50 - left * 2.5);
    statCard(smooth(L(1) + .5, L(1) + 1.3, lt), 400, 240, String(n), 'TEPALIKDAGI KAMONCHILAR', undefined, 520);
  });
};

SC.khalid = (lt, D, L, t) => {
  const cut = L(1) + 3.2;
  const att = smooth(L(0) + .6, L(1) + 2.4, lt);
  const shot1 = () => drawMap(lt, D, {
    muslims: 1, mPos: 120, quraysh: .8, qScatter: .8, hill: 1, cav: 1, archers: 50, gone: 40 + 10 * smooth(.42, .55, att),
    attack: att, burst: smooth(L(1) + 2.2, L(1) + 2.6, lt), ret: smooth(L(1) + 2.4, L(1) + 3.4, lt),
  });
  const shot2 = () => {
    const tb = lt - cut, cam = { x: 960 + tb * 120, y: 560, z: 1.05 };
    const [sx, sy] = scr(cam, .05, 1100, 640);
    sky(SKY.blood); glow(sx, sy, 950, '255,130,70', .7); sunDisc(sx, sy, 80, '#fff0c8', '#ffb060');
    clouds('blood', cam, t, { speed: 2 });
    uhudLayer(cam, .3, { top: '#4a1218', bot: '#20060c', rimA: .8, rimCol: '255,140,80', sunX: 1100 });
    plain(cam, .5, 800, '#5a1e1c', '#160606', '255,130,80');
    const ret = smooth(L(2), L(2) + 3, lt);
    layer(cam, .55, () => { for (let i = 0; i < 50; i++) person(1900 - ret * 500 + (i % 12) * 26, 830 + (i % 4) * 7, .26, { t, ph: i, pose: 'run', weapon: 'sword', flip: true, col: '#2a0a0c', alpha: ret }); });
    ridgeLayer(cam, .8, DUNES[1], { top: '#1a0608', bot: '#080203', y0: 820, y1: 1080, rimA: .9, rimCol: '255,140,80', sunX: 1100 });
    layer(cam, .8, () => {
      for (let i = 0; i < 14; i++) {
        const x = cam.x * .8 - 1100 + mod(i * 150 + tb * 220 + (i % 3) * 30, 2100), y = DUNES[1][clamp(Math.round((x + 900) / 10), 0, DUNES[1].length - 1)][1] + 4;
        ctx.globalAlpha = .5; ctx.drawImage(DUST, x - 200, y - 70, 200, 80); ctx.globalAlpha = 1;
        cavalry(x, y, .72, { t, ph: i * 1.9, gallop: 1.3, weapon: i % 2 ? 'spear' : 'sword', rim: [1.5, -.5], rimCol: 'rgba(255,170,100,.9)' });
      }
    });
  };
  blend(smooth(cut, cut + 1, lt), shot1, shot2);
};

const SMOKES = (() => { const r = rng(121), a = []; for (let i = 0; i < 36; i++) a.push({ x: r() * 2400 - 200, y: 600 + r() * 420, s: 260 + r() * 420, v: 10 + r() * 30, ph: r() * 6 }); return a; })();
SC.chaos = (lt, D, L, t) => {
  const shake = 7 * (1 - smooth(L(1), L(1) + 3, lt)) + 2;
  const cam = { x: 960 + Math.sin(t * 23) * shake + Math.sin(t * 9) * shake, y: 560 + Math.cos(t * 19) * shake, z: 1.08 };
  const para = smooth(L(2) - .4, L(2) + 3, lt);
  sky(SKY.smoke);
  const [gx, gy] = scr(cam, .1, 880, 470);
  if (para > 0) { glow(gx, gy, 1100 * para + 200, '255,225,160', .8 * para); rays(gx, gy, t, { a: .16 * para, col: '255,235,180', len: 1600 }); }
  uhudLayer(cam, .3, { top: '#2a0a10', bot: '#120406', rimA: .5 + .5 * para, rimCol: para > .3 ? '255,230,170' : '255,120,70', sunX: 880, ravA: .6 });
  plain(cam, .5, 800, '#4a1414', '#120404', '255,110,70');
  for (const s of SMOKES) { if (s.y > 820) continue; const x = mod(s.x + t * s.v, 2600) - 300; ctx.globalAlpha = .7 * (1 - para * .6); ctx.drawImage(SMOKE, x - s.s / 2, s.y - s.s / 2, s.s, s.s * .7); }
  ctx.globalAlpha = 1;
  layer(cam, .8, () => {
    const r = rng(131);
    for (let i = 0; i < 64; i++) {
      const dir = r() < .5 ? 1 : -1, x0 = r() * 2200 - 140, y = 880 + r() * 110, sp = 40 + r() * 80;
      const x = mod(x0 + dir * sp * lt, 2300) - 200, s = .45 + (y - 880) / 110 * .25;
      person(x, y, s, { t, ph: i * 1.1, pose: r() < .6 ? 'run' : 'stand', weapon: ['sword', 'spear', 'bow', 'none'][i % 4], shield: i % 3 === 0, flip: dir < 0, col: '#100406', rim: [-1.4, -.5], rimCol: para > .2 ? 'rgba(255,225,170,.85)' : 'rgba(255,110,70,.75)' });
    }
    banner(600, 1000, 120, t, 1, '#1a1a1a', 1.2); banner(1400, 990, 110, t, 2, '#5a1414', -1.3);
  });
  for (const s of SMOKES) { if (s.y <= 820) continue; const x = mod(s.x - t * s.v * 1.5, 2600) - 300; ctx.globalAlpha = .55 * (1 - para * .7); ctx.drawImage(SMOKE, x - s.s / 2, s.y - s.s / 2, s.s, s.s * .7); }
  ctx.globalAlpha = 1;
  const rain = 1 - smooth(L(1), L(1) + 4, lt);
  if (rain > 0) { const r = rng(141); for (let i = 0; i < 40; i++) { const x = mod(r() * W + lt * 300, W + 200) - 100, y = mod(r() * H + lt * 900, H + 200) - 100; ctx.globalAlpha = rain * .8; arrow(x, y, 1.15, 26, '#0a0304', 2); } ctx.globalAlpha = 1; }
  const flash = win(lt, L(0) + .2, L(0) + 1.8, .4);
  if (flash > 0) { ctx.fillStyle = `rgba(60,0,0,${.35 * flash})`; ctx.fillRect(0, 0, W, H); }
  motes(t, para > .3 ? '255,225,160' : '255,120,60', .8 + para, para > .3 ? 18 : 4);
};

const TRAIL = [[260, 1040], [700, 900], [520, 820], [1000, 700], [860, 640], [1300, 540], [1180, 490], [1560, 420]];
const slopeY = x => 1010 - x * .38 + 10 * Math.sin(x * .012) + 6 * Math.sin(x * .05);
function trailAt(u) { const p = polyPartial(TRAIL, u); return p[p.length - 1]; }
SC.regroup = (lt, D, L, t) => {
  const cam = { x: 960, y: 540, z: 1 + .04 * (lt / D) };
  const [sx, sy] = scr(cam, .05, 1550, 720);
  sky(SKY.dusk); stars(t, .7, 360);
  glow(sx, sy, 900, '255,150,90', .55); sunDisc(sx, sy, 70);
  clouds('dusk', cam, t);
  ridgeLayer(cam, .2, FAR, { top: '#7a4a6a', bot: '#4a2a48', y0: 600, y1: 820, rimA: .4, sunX: 1550 });
  plain(cam, .35, 780, '#4a2632', '#1a0a12', '255,160,110');
  layer(cam, .8, () => {
    ctx.beginPath(); ctx.moveTo(-200, 1400); for (let x = -200; x <= 2300; x += 10) ctx.lineTo(x, slopeY(x)); ctx.lineTo(2300, 1400); ctx.closePath();
    const g = ctx.createLinearGradient(0, 300, 0, 1080); g.addColorStop(0, '#2e1626'); g.addColorStop(1, '#0c050a'); ctx.fillStyle = g; ctx.fill();
    ctx.beginPath(); for (let x = -200; x <= 2300; x += 10) x === -200 ? ctx.moveTo(x, slopeY(x)) : ctx.lineTo(x, slopeY(x));
    ctx.strokeStyle = rimGrad(0, 2000, 1550, .8); ctx.lineWidth = 3; ctx.stroke();
  });
  layer(cam, .8, () => {
    ctx.strokeStyle = 'rgba(255,190,140,.10)'; ctx.lineWidth = 16; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    ctx.beginPath(); TRAIL.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])); ctx.stroke();
    const r = rng(151);
    for (let i = 0; i < 18; i++) { const at = L(0) + r() * (L(2) - L(0)), x = 300 + r() * 1300, y = 900 - (x - 300) * .3 + r() * 80; const k = clamp((lt - at) / .3, 0, 1); if (k <= 0) continue; arrow(x, y - (1 - k) * 200, 1.2, 30, '#0a0406', 2.2); }
    const gather = smooth(L(2), L(2) + 6, lt);
    for (let i = 0; i < 28; i++) {
      const u = clamp(((i * 37) % 28) / 28 * .55 + lt * .012 + gather * .4 * ((i % 5) / 5 + .5), 0, .98);
      const [x, y] = trailAt(u);
      const s = .7 - u * .3;
      person(x + (i % 3) * 14 - 14, y + 4, s, { t, ph: i * 1.3, pose: u > .95 ? 'stand' : 'walk', weapon: ['spear', 'sword', 'bow'][i % 3], rim: [1.4, -.4], rimCol: 'rgba(255,180,120,.8)' });
    }
    // a tight knot of shields moving up together
    const kg = smooth(L(1), L(1) + 1.5, lt);
    if (kg > 0) {
      const u = clamp(.25 + (lt - L(1)) * .03, 0, .9), [cx, cy] = trailAt(u);
      for (let j = 0; j < 7; j++) {
        const ox = (j - 3) * 18, oy = Math.abs(j - 3) * 3;
        person(cx + ox, cy + oy, .75, { t, ph: j * .9, pose: 'walk', weapon: 'sword', shield: 'up', flip: j < 3, alpha: kg, rim: [1.4, -.4], rimCol: 'rgba(255,180,120,.8)' });
        ctx.save(); ctx.globalAlpha = kg; for (let a = 0; a < 2; a++) arrow(cx + ox + (j < 3 ? -12 : 12) + a * 4, cy + oy - 64 + a * 5, j < 3 ? -2.6 : -.5, 16, '#0a0406', 1.6); ctx.restore();
      }
    }
    glow(1560, 410, 120, '255,210,150', .25 * gather);
  });
};

const ROCKTOP = genRidge(161, -100, 2100, 8, (x, p) => 960 - 30 * Math.abs(Math.sin(x * .006 + p[0])) - 14 * Math.sin(x * .02 + p[1]) + Math.pow((x - 960) / 960, 2) * 60);
const CAMP = (() => { const r = rng(171), a = []; for (let i = 0; i < 300; i++) a.push({ x: 560 + r() * 900, y: 820 + r() * 40, h: 4 + r() * 3 }); return a; })();
SC.abusufyan = (lt, D, L, t) => {
  const cam = { x: 960, y: 540, z: 1.03 + .03 * (lt / D) };
  sky(SKY.deepDusk); stars(t, .8, 420);
  const [sx, sy] = scr(cam, .05, 600, 760); glow(sx, sy, 800, '255,120,70', .5);
  clouds('duskRed', cam, t, { alpha: .6 });
  ridgeLayer(cam, .25, FAR, { top: '#3a2244', bot: '#1e1028', y0: 600, y1: 820, rimA: .4, rimCol: '255,140,90', sunX: 600 });
  plain(cam, .5, 790, '#2a1420', '#0c050a');
  const go = smooth(L(4), L(4) + 6, lt);
  layer(cam, .5, () => {
    const ox = -go * 400;
    ctx.globalAlpha = 1 - go * .8; ctx.fillStyle = '#0c0408';
    for (const a of CAMP) { ctx.fillRect(a.x + ox, a.y - a.h, 1.6, a.h); }
    for (let i = 0; i < 30; i++) torch(600 + (i * 131) % 860 + ox, 830 + (i % 3) * 12, t, i * 1.3, .5);
    for (let i = 0; i < 10; i++) banner(620 + i * 85 + ox, 830, 26, t, i, '#5a1414');
    ctx.globalAlpha = 1;
  });
  ridgeLayer(cam, 1, ROCKTOP, { top: '#0a060c', bot: '#030204', y0: 900, y1: 1080, rimA: .6, rimCol: '255,140,90', sunX: 600 });
  // each quote appears about when the narrator reaches it (second half of the line)
  const mid = n => L(n) + (L.E(n) - L(n)) * .45;
  const cards = [
    { at: mid(0), to: L(1) - .1, txt: "U'lu Hubal! — Hubal ulug' bo'lsin!", who: 'ABU SUFYON', col: '#e8a090' },
    { at: mid(1), to: L(2) - .1, txt: "Alloh oliy va ulug'dir!", who: "MO'MINLARNING JAVOBI", col: '#f3d08a' },
    { at: mid(2), to: L(3) - .1, txt: "Bizda Uzzo bor, sizda Uzzo yo'q!", who: 'ABU SUFYON', col: '#e8a090' },
    { at: mid(3) - .4, to: L(4) + .3, txt: "Alloh bizning Mavlomiz, sizning mavlongiz yo'q!", who: "MO'MINLARNING JAVOBI", col: '#f3d08a' },
  ];
  for (const c of cards) quoteCard(win(lt, c.at, c.to, .45), c.txt, c.who, c.col, 420);
};

const GRAVES = (() => { const r = rng(181), a = []; for (let i = 0; i < 26; i++) a.push({ x: 120 + i * 68 + r() * 30, y: 965 + r() * 50, w: 40 + r() * 30, st: r() < .6 }); return a; })();
const SOULS = (() => { const r = rng(191), a = []; for (let i = 0; i < 70; i++) a.push({ x0: 200 + r() * 1500, y0: 900 + r() * 80, x1: 120 + r() * 1680, y1: 60 + r() * 380, ph: r() * 6, k: r() }); return a; })();
SC.martyrs = (lt, D, L, t) => {
  const cam = { x: 960, y: 540, z: 1.06 - .05 * (lt / D) };
  sky(SKY.night); stars(t, .8, H * .7, true);
  const [mx, my] = scr(cam, .03, 1600, 180); moon(mx, my);
  uhudLayer(cam, .3, { top: '#141a3a', bot: '#080b1e', rimA: .55, rimCol: '200,215,255', sunX: 1600, ravA: .4 });
  plain(cam, .6, 820, '#0e1226', '#04050c', '150,170,230');
  const span = Math.max(4, L(2) - L(0) + 2);
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (let i = 0; i < 70; i++) {
    const s = SOULS[i], st = L(0) + .4 + (i / 70) * span, p = clamp((lt - st) / 4, 0, 1);
    if (p <= 0) continue;
    const e = ease(p), x = lerp(s.x0, s.x1, e) + Math.sin(p * 6 + s.ph) * 20 * (1 - p), y = lerp(s.y0, s.y1, e);
    const tw = p >= 1 ? .65 + .35 * Math.sin(t * 2.4 + s.ph) : 1;
    ctx.globalAlpha = tw; ctx.drawImage(GOLD, x - 16, y - 16, 32, 32);
    ctx.fillStyle = '#fffbe8'; ctx.beginPath(); ctx.arc(x, y, 1.8, 0, 7); ctx.fill();
  }
  ctx.restore();
  layer(cam, .9, () => {
    for (const g of GRAVES) {
      ctx.fillStyle = '#05060e'; ctx.beginPath(); ctx.ellipse(g.x, g.y, g.w, 16, 0, Math.PI, 0); ctx.fill();
      ctx.strokeStyle = 'rgba(200,215,255,.25)'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.ellipse(g.x, g.y, g.w, 16, 0, Math.PI * 1.15, Math.PI * 1.85); ctx.stroke();
      if (g.st) { ctx.fillStyle = '#05060e'; ctx.fillRect(g.x - g.w * .7, g.y - 30, 7, 22); ctx.fillRect(g.x + g.w * .6, g.y - 26, 7, 18); }
    }
    ctx.fillStyle = '#020306'; ctx.fillRect(-300, 1010, 2600, 300);
  });
  label('70', W / 2, 200, { alpha: win(lt, L(0) + .4, L(1) + .5, .8), font: '700 110px Cinzel, Georgia, serif', col: '#ffe8b8', blur: 30, ls: '6px' });
  label('UHUD SHAHIDLARI', W / 2, 250, { alpha: win(lt, L(0) + .6, L(1) + .5, .8), font: '600 24px Cinzel, Georgia, serif', ls: '10px', col: '#f0d8b0' });
  motes(t, '220,230,255', .35, 2);
};

SC.lesson = (lt, D, L, t) => {
  const cam = { x: 960, y: 540, z: 1.1 - .1 * ease(clamp(lt / D, 0, 1)) };
  const rise = ease(clamp(lt / D, 0, 1)), [sx, sy] = scr(cam, .05, 900, 640 - rise * 160);
  sky(SKY.dawn); stars(t, .25 * (1 - rise), 260);
  glow(sx, sy, 1000, '255,210,150', .8); rays(sx, sy, t, { a: .14, col: '255,225,175', len: 1500 }); sunDisc(sx, sy, 80);
  clouds('dawn', cam, t);
  uhudLayer(cam, .3, { top: '#4a3a6a', bot: '#2a2044', rimA: .9, rimCol: '255,220,160', sunX: 900 });
  plain(cam, .55, 800, '#5a4256', '#1e121c', '255,210,160');
  layer(cam, .8, () => { [[200, 980, 380], [360, 990, 300], [1640, 985, 360], [1780, 995, 300]].forEach((p, i) => palm(p[0], p[1], p[2], t, i, '#140c16')); ctx.fillStyle = '#120a12'; ctx.fillRect(-300, 975, 2600, 400); });
  motes(t, '255,225,170', .8, 5);
  const v = smooth(L(2) - .2, L(2) + 1, lt);
  if (v > 0) {
    ctx.fillStyle = `rgba(10,6,16,${.45 * v})`; ctx.fillRect(0, 0, W, H);
    label('وَلَا تَهِنُوا وَلَا تَحْزَنُوا وَأَنتُمُ الْأَعْلَوْنَ إِن كُنتُم مُّؤْمِنِينَ', W / 2, 400, { alpha: v, font: '700 84px Amiri, serif', ls: '0px', col: '#fff1d0', blur: 28, shadowCol: 'rgba(255,170,80,.55)' });
    ctx.save(); ctx.globalAlpha = v; ctx.textAlign = 'center'; ctx.font = 'italic 500 48px "Cormorant Garamond", Georgia, serif'; ctx.fillStyle = '#fbf1e3'; ctx.shadowColor = 'rgba(0,0,0,.8)'; ctx.shadowBlur = 14;
    wrapText("«Bo'shashmangiz va g'amgin bo'lmangiz! Agar mo'min bo'lsangiz, sizlar ustunsiz.»", 1300).forEach((l, i) => ctx.fillText(l, W / 2, 520 + i * 60));
    ctx.restore();
    label('OLI IMRON SURASI · 139-OYAT', W / 2, 680, { alpha: smooth(L(3) - .3, L(3) + .6, lt) * v + v * .6, font: '600 26px Cinzel, Georgia, serif', ls: '8px', col: '#f3c88a' });
  }
};

SC.end = (lt, D) => {
  sky([[0, '#06040c'], [.6, '#120a18'], [1, '#1e1018']]);
  stars(lt, .6, H * .8);
  const k = smooth(.3, 1.6, lt);
  titleBlock(k, 'UHUD', 'Sabr va itoat qissasi', '', 360, 150);
  const s = smooth(1.4, 2.6, lt);
  label('MANBALAR', W / 2, 610, { alpha: s, font: '600 22px Cinzel, Georgia, serif', ls: '8px', col: '#f3c88a' });
  ['Sahihi Buxoriy', 'Ibn Hishom — «As-Siyratun-nabaviyya»', 'Safiyurrahmon Muborakpuriy — «Ar-Rahiqul-maxtum»', "Qur'oni karim — Oli Imron surasi (121–175)"].forEach((l, i) =>
    label(l, W / 2, 660 + i * 44, { alpha: s, font: 'italic 500 34px "Cormorant Garamond", Georgia, serif', ls: '0px' }));
  const n = smooth(2.6, 3.6, lt);
  label("Hurmat yuzasidan Payg'ambarimiz (s.a.v.) va ulug' sahobalar tasvirlanmagan.", W / 2, 900, { alpha: n, font: 'italic 500 28px "Cormorant Garamond", Georgia, serif', ls: '0px', col: '#e8d2b0' });
  label("OVOZ: SUN'IY INTELLEKT (GEMINI TTS)", W / 2, 945, { alpha: n * .8, font: '500 18px Cinzel, Georgia, serif', ls: '4px', col: 'rgba(240,210,170,.7)' });
};

const MAKKAH_FAR = genRidge(201, -900, 2900, 8, (x, p) => 700 - 260 * Math.exp(-Math.pow((x - 100) / 420, 2)) - 280 * Math.exp(-Math.pow((x - 1800) / 460, 2)) - 30 * Math.abs(Math.sin(x * .008 + p[0])) - 12 * Math.sin(x * .03 + p[1]));
const MAKKAH_NEAR = genRidge(202, -900, 2900, 7, (x, p) => 760 - 380 * Math.exp(-Math.pow((x - 250) / 360, 2)) - 400 * Math.exp(-Math.pow((x - 1700) / 380, 2)) - 50 * Math.abs(Math.sin(x * .009 + p[0])) - 18 * Math.sin(x * .03 + p[1]) - 6 * Math.sin(x * .09 + p[2]));

// ---------- timeline ----------
const NOSUB = { abusufyan: [0, 1, 2, 3], lesson: [2, 3] };
// Scenes whose action sits near the ground get raised so subtitles don't cover it.
const LIFT = new Set(['makkah', 'march', 'split', 'archers', 'battle', 'spoils', 'khalid', 'chaos', 'regroup', 'martyrs']);
function sceneAt(t) { const s = TL.scenes; for (let i = s.length - 1; i >= 0; i--) if (t >= s[i].a) return i; return 0; }
function drawScene(i, t, lift = true) {
  const sc = TL.scenes[i], lt = t - sc.a, D = sc.b - sc.a;
  const L = n => (sc.lines[n] ? sc.lines[n].a - sc.a : D);
  L.E = n => (sc.lines[n] ? sc.lines[n].b - sc.a : D);
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, lift && LIFT.has(sc.id) ? -70 : 0); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  SC[sc.id](lt, D, L, t);
  ctx.restore();
}
function subtitles(t, i) {
  const sc = TL.scenes[i], skip = NOSUB[sc.id] || [];
  sc.lines.forEach((l, li) => {
    if (skip.includes(li)) return;
    const k = smooth(l.a - .1, l.a + .15, t) * (1 - smooth(l.b + .1, l.b + .35, t));
    if (k <= 0) return;
    ctx.save(); ctx.globalAlpha = k; ctx.textAlign = 'center'; ctx.lineJoin = 'round';
    ctx.font = '600 38px "Cormorant Garamond", Amiri, Georgia, serif';
    const lines = wrapText(l.text, 1640);
    lines.forEach((tx, j) => {
      const y = H - 34 - (lines.length - 1 - j) * 44;
      ctx.shadowColor = 'rgba(0,0,0,.9)'; ctx.shadowBlur = 8;
      ctx.strokeStyle = 'rgba(0,0,0,.75)'; ctx.lineWidth = 5; ctx.strokeText(tx, W / 2, y);
      ctx.shadowBlur = 0; ctx.fillStyle = '#fbf1e3'; ctx.fillText(tx, W / 2, y);
    });
    ctx.restore();
  });
}
function caption(t, i) {
  const sc = TL.scenes[i]; if (!sc.caption) return;
  const k = win(t, sc.a + .6, sc.a + 5.5, .8); if (k <= 0) return;
  ctx.save(); ctx.globalAlpha = k;
  ctx.fillStyle = 'rgba(243,200,138,.9)'; ctx.fillRect(110, 100, 60 * k, 2);
  ctx.restore();
  label(sc.caption, 110, 145, { alpha: k, align: 'left', font: '600 30px Cinzel, Georgia, serif', ls: '8px', col: '#fff1d8' });
}
// o.subs=false: no burned-in subtitles and no scene lift (vertical layout puts subtitles outside the frame)
// o.from / o.to: clamp to a range of scenes (one Instagram part)
function renderAt(t, o = {}) {
  const subs = o.subs !== false;
  ctx = main; main.setTransform(1, 0, 0, 1, 0, 0);
  const i = Math.min(sceneAt(t), o.to ?? Infinity), sc = TL.scenes[i];
  const kx = i > (o.from ?? 0) ? smooth(sc.a, sc.a + .9, t) : 1;
  if (kx < 1) {
    drawScene(i - 1, t, subs);
    ctx = actxA; drawScene(i, t, subs); ctx = main;
    main.save(); main.globalAlpha = kx; main.drawImage(bufA, 0, 0); main.restore();
  } else drawScene(i, t, subs);
  ctx.drawImage(VIGNETTE, 0, 0);
  caption(t, i);
  if (subs) subtitles(t, i);
  if (o.noFade) return i;
  const f = clamp(1 - smooth(0, 1.2, t) + smooth(TL.duration - 1.6, TL.duration, t), 0, 1);
  if (f > 0) { ctx.fillStyle = `rgba(0,0,0,${f})`; ctx.fillRect(0, 0, W, H); }
  return i;
}
window.renderAt = renderAt;

// ---------- Instagram: vertical 1080x1920, film framed in the middle, subtitles below ----------
// 1: lead-up to the battle, 2: the battle, 3: aftermath and lesson
const PARTS = [['title', 'makkah', 'march', 'madinah', 'split', 'map'], ['archers', 'battle', 'hamzah', 'spoils', 'khalid', 'chaos'], ['regroup', 'abusufyan', 'martyrs', 'lesson', 'end']];
const HOLD = 3;  // seconds of "continued in part N" at the end of each part
const VW = 1080, VH = 1920, FY = 620, FH = 608;
const vcv = mk(VW, VH), vctx = vcv.getContext('2d'), tiny = mk(36, 64), tctx = tiny.getContext('2d');
function partRange(p) {
  const s = TL.scenes, ids = PARTS[p];
  const i0 = s.findIndex(x => x.id === ids[0]), i1 = s.findIndex(x => x.id === ids[ids.length - 1]);
  return { a: s[i0].a, b: s[i1].b, i0, i1, end: s[i1].b + (p < PARTS.length - 1 ? HOLD : 0) };
}
function vText(text, x, y, font, col, o = {}) {
  const g = vctx; g.save(); g.globalAlpha = o.alpha ?? 1; g.textAlign = 'center'; g.font = font;
  if ('letterSpacing' in g) g.letterSpacing = o.ls || '0px';
  if (o.grad) { const gr = g.createLinearGradient(0, y - o.size, 0, y); gr.addColorStop(0, '#fff1c9'); gr.addColorStop(.5, '#f2b45a'); gr.addColorStop(1, '#a8562a'); g.fillStyle = gr; }
  else g.fillStyle = col;
  g.shadowColor = o.shadow || 'rgba(0,0,0,.85)'; g.shadowBlur = o.blur ?? 12;
  g.fillText(text, x, y); g.restore();
}
function renderVertical(t, p) {
  const r = partRange(p), lt = t - r.a;
  const i = renderAt(t, { subs: false, from: r.i0, to: r.i1, noFade: true });
  const g = vctx; g.setTransform(1, 0, 0, 1, 0, 0);
  // soft blurred backdrop taken from the frame itself
  tctx.drawImage(cv, (W - 608) / 2, 0, 608, 1080, 0, 0, 36, 64);
  g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';
  g.drawImage(tiny, 0, 0, VW, VH);
  g.fillStyle = 'rgba(8,4,12,.6)'; g.fillRect(0, 0, VW, VH);
  g.drawImage(cv, 0, 0, W, H, 0, FY, VW, FH);
  g.fillStyle = 'rgba(240,180,100,.75)'; g.fillRect(0, FY - 3, VW, 3); g.fillRect(0, FY + FH, VW, 3);
  // header
  vText("UHUD G'AZOTI", VW / 2 + 7, 330, '700 92px Cinzel, Georgia, serif', '', { grad: true, size: 92, ls: '14px', shadow: 'rgba(255,140,60,.55)', blur: 30 });
  g.save(); g.fillStyle = 'rgba(240,180,100,.16)'; g.strokeStyle = 'rgba(240,180,100,.8)'; g.lineWidth = 2;
  g.beginPath(); g.roundRect(VW / 2 - 130, 392, 260, 70, 35); g.fill(); g.stroke(); g.restore();
  vText(`${p + 1}-QISM`, VW / 2 + 4, 441, '700 38px Cinzel, Georgia, serif', '#fff1d8', { ls: '8px' });
  vText('Sabr va itoat qissasi', VW / 2, 535, 'italic 500 42px "Cormorant Garamond", Georgia, serif', '#f6e2c4');
  // subtitles under the frame
  // the quote cards are small at this scale, so the dialogue scene keeps its subtitles here
  const sc = TL.scenes[i], skip = sc.id === 'abusufyan' ? [] : NOSUB[sc.id] || [];
  sc.lines.forEach((l, li) => {
    if (skip.includes(li)) return;
    const k = smooth(l.a - .1, l.a + .15, t) * (1 - smooth(l.b + .1, l.b + .35, t));
    if (k <= 0) return;
    g.save(); g.font = '600 56px "Cormorant Garamond", Amiri, Georgia, serif';
    const prev = ctx; ctx = g; const lines = wrapText(l.text, 960); ctx = prev;
    g.restore();
    const y0 = FY + FH + 120 + Math.max(0, 3 - lines.length) * 20;
    lines.forEach((tx, j) => vText(tx, VW / 2, y0 + j * 66, '600 56px "Cormorant Garamond", Amiri, Georgia, serif', '#fbf1e3', { alpha: k, blur: 10 }));
  });
  // "continued in the next part"
  if (p < PARTS.length - 1) {
    const k = smooth(r.b - .6, r.b + .4, t);
    if (k > 0) {
      g.fillStyle = `rgba(0,0,0,${.55 * k})`; g.fillRect(0, FY, VW, FH);
      vText('DAVOMI', VW / 2 + 5, FY + FH / 2 - 30, '600 34px Cinzel, Georgia, serif', '#f3c88a', { alpha: k, ls: '10px' });
      vText(`${p + 2}-qismda`, VW / 2, FY + FH / 2 + 50, 'italic 600 76px "Cormorant Garamond", Georgia, serif', '#fff6e6', { alpha: k, blur: 20 });
    }
  }
  const f = clamp(1 - smooth(0, .6, lt) + smooth(r.end - r.a - 1, r.end - r.a, lt), 0, 1);
  if (f > 0) { g.fillStyle = `rgba(0,0,0,${f})`; g.fillRect(0, 0, VW, VH); }
  return vcv;
}
window.renderVertical = renderVertical;
window.partRange = partRange;
window.PARTS = PARTS;
window.READY = Promise.all(['700 40px Cinzel', '600 40px "Cormorant Garamond"', 'italic 500 40px "Cormorant Garamond"', '700 40px Amiri']
  .map(f => document.fonts.load(f, 'Aaبس'))).then(() => document.fonts.ready).then(() => { cloudSet('dusk'); return true; });

// ---------- interactive playback ----------
if (location.search.includes('render')) document.body.classList.add('render');
else {
  const aud = document.getElementById('aud'), play = document.getElementById('play'), seek = document.getElementById('seek'), time = document.getElementById('time');
  let t = 0, playing = false, last = performance.now();
  play.onclick = () => { playing = !playing; play.textContent = playing ? '⏸ Pause' : '▶ Play'; if (playing) { aud.currentTime = t; aud.play().catch(() => {}); } else aud.pause(); };
  seek.oninput = () => { t = seek.value / 1000 * TL.duration; aud.currentTime = t; };
  window.seekTo = s => { t = s; playing = false; aud.pause(); play.textContent = '▶ Play'; };
  const frame = now => {
    const dt = Math.min(.05, (now - last) / 1000); last = now;
    if (playing) { t = aud.paused ? t + dt : aud.currentTime; if (t >= TL.duration) { playing = false; t = 0; play.textContent = '▶ Play'; } }
    renderAt(t);
    seek.value = t / TL.duration * 1000;
    time.textContent = `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;
    requestAnimationFrame(frame);
  };
  window.READY.then(() => requestAnimationFrame(frame));
}
