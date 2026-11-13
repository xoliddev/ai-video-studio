// Renders film.html frame by frame in headless Chrome and pipes JPEGs into ffmpeg.
//   node render.js <ffmpeg> video            -> uhud.mp4 (needs mix.wav)
//   node render.js <ffmpeg> stills 10,50,90  -> stills/*.jpg
const puppeteer = require('puppeteer-core');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const [FF, mode = 'video', list = ''] = process.argv.slice(2);
const FPS = 30;
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const URL = 'http://127.0.0.1:8765/film.html?render=1';

(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--force-device-scale-factor=1', '--disable-gpu-vsync'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });
  page.on('pageerror', e => console.error('page error:', e.message));
  await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 120000 });
  await page.evaluate(() => window.READY);
  const grab = (t, q) => page.evaluate((t, q) => { renderAt(t); return document.getElementById('c').toDataURL('image/jpeg', q).slice(23); }, t, q);

  const grabV = (t, p, q) => page.evaluate((t, p, q) => renderVertical(t, p).toDataURL('image/jpeg', q).slice(23), t, p, q);

  if (mode === 'vstills') {
    // list: "part:time,part:time" (time relative to the part start)
    fs.mkdirSync(path.join(__dirname, 'stills'), { recursive: true });
    for (const item of list.split(',')) {
      const [p, s] = item.split(':').map(Number);
      const r = await page.evaluate(p => partRange(p), p);
      fs.writeFileSync(path.join(__dirname, 'stills', `p${p + 1}_${String(s).padStart(4, '0')}.jpg`), Buffer.from(await grabV(r.a + s, p, .8), 'base64'));
    }
  } else if (mode === 'parts') {
    const parts = list ? list.split(',').map(Number) : [...Array(await page.evaluate(() => PARTS.length)).keys()];
    for (const p of parts) {
      const r = await page.evaluate(p => partRange(p), p);
      const len = r.end - r.a, speech = r.b - r.a, N = Math.ceil(len * FPS);
      const out = path.join(__dirname, `uhud_qism_${p + 1}.mp4`);
      const ff = spawn(FF, ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
        '-ss', r.a.toFixed(3), '-t', speech.toFixed(3), '-i', path.join(__dirname, 'mix.wav'),
        '-af', `apad=pad_dur=${(len - speech + .5).toFixed(2)},afade=t=in:d=0.4,afade=t=out:st=${(len - 1.2).toFixed(2)}:d=1.2`,
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
        '-t', len.toFixed(3), '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
      const t0 = Date.now();
      for (let f = 0; f < N; f++) {
        const buf = Buffer.from(await grabV(r.a + f / FPS, p, .92), 'base64');
        if (!ff.stdin.write(buf)) await new Promise(res => ff.stdin.once('drain', res));
        if (f % 600 === 0) console.log(`part ${p + 1}: frame ${f}/${N}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
      }
      ff.stdin.end();
      await new Promise(res => ff.on('close', res));
      console.log(`part ${p + 1} done: ${len.toFixed(1)}s`);
    }
  } else if (mode === 'stills') {
    fs.mkdirSync(path.join(__dirname, 'stills'), { recursive: true });
    for (const s of list.split(',').map(Number)) {
      fs.writeFileSync(path.join(__dirname, 'stills', `t${String(s).padStart(5, '0')}.jpg`), Buffer.from(await grab(s, .8), 'base64'));
    }
  } else {
    const dur = await page.evaluate(() => TL.duration);
    const N = Math.ceil(dur * FPS);
    const ff = spawn(FF, ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
      '-i', path.join(__dirname, 'mix.wav'), '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
      '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', path.join(__dirname, 'uhud.mp4')], { stdio: ['pipe', 'inherit', 'inherit'] });
    const t0 = Date.now();
    for (let f = 0; f < N; f++) {
      const buf = Buffer.from(await grab(f / FPS, .93), 'base64');
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (f % 300 === 0) console.log(`frame ${f}/${N}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
    }
    ff.stdin.end();
    await new Promise(r => ff.on('close', r));
    console.log('done', ((Date.now() - t0) / 1000).toFixed(0) + 's');
  }
  await browser.close();
})();
