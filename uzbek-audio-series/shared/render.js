// Shared renderer for every episode: opens <episode>/reel.html in headless Chrome,
// seeks frame by frame and pipes JPEG screenshots into ffmpeg together with <episode>/mix.wav.
//
// Usage (from uzbek-audio-series/):
//   node shared/render.js tungi-taksi-ep1 stills 2,10,40,120   -> tungi-taksi-ep1/stills/*.jpg
//   node shared/render.js tungi-taksi-ep1 video                -> tungi-taksi-ep1/tungi-taksi-ep1.mp4
//
// Env: CHROME_PATH (Chrome/Chromium executable), FFMPEG (optional; defaults to imageio-ffmpeg's binary).
const puppeteer = require('puppeteer-core');
const { spawn, execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const [epArg, mode = 'video', list = ''] = process.argv.slice(2);
if (!epArg) {
  console.error('usage: node shared/render.js <episode-dir> [video|stills] [t1,t2,...]');
  process.exit(1);
}
const EP = path.resolve(epArg);
const FPS = 24; // cinematic frame rate
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const FF = process.env.FFMPEG ||
  execFileSync('python', ['-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())']).toString().trim();
const URL = 'file:///' + path.join(EP, 'reel.html').replace(/\\/g, '/');

(async () => {
  console.log('Launching headless Chrome for', path.basename(EP));
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--force-device-scale-factor=1', '--allow-file-access-from-files', '--disable-gpu-vsync']
  });

  const page = await browser.newPage();
  page.on('pageerror', e => console.error('Page error:', e.message));
  await page.setViewport({ width: 1080, height: 1920 });
  await page.goto(URL, { waitUntil: 'load', timeout: 90000 });
  await page.evaluate(() => window.READY);

  const shot = async (t, q = 88) => {
    await page.evaluate(t => seek(t), t);
    return page.screenshot({ type: 'jpeg', quality: q, clip: { x: 0, y: 0, width: 1080, height: 1920 } });
  };

  if (mode === 'stills') {
    const outDir = path.join(EP, 'stills');
    fs.mkdirSync(outDir, { recursive: true });
    const times = list.split(',').map(Number);
    for (const t of times) {
      const p = path.join(outDir, `t_${t.toFixed(1).padStart(5, '0')}.jpg`);
      fs.writeFileSync(p, await shot(t, 92));
      console.log('Saved still:', p);
    }
  } else {
    const dur = await page.evaluate(() => DURATION);
    const N = Math.ceil(dur * FPS);
    const out = path.join(EP, path.basename(EP) + '.mp4');
    console.log(`Rendering ${N} frames at ${FPS} FPS (${dur.toFixed(2)}s) into: ${out}`);

    const ff = spawn(FF, [
      '-y', '-loglevel', 'error',
      '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
      '-i', path.join(EP, 'mix.wav'),
      '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p',
      '-c:a', 'aac', '-b:a', '192k',
      '-shortest', '-movflags', '+faststart',
      out
    ], { stdio: ['pipe', 'inherit', 'inherit'] });

    const t0 = Date.now();
    for (let f = 0; f < N; f++) {
      const buf = await shot(f / FPS, 88);
      if (!ff.stdin.write(buf)) {
        await new Promise(r => ff.stdin.once('drain', r));
      }
      if (f % 200 === 0 || f === N - 1) {
        const elapsed = (Date.now() - t0) / 1000;
        const fpsActual = f / (elapsed || 1);
        const remain = (N - f) / (fpsActual || 1);
        console.log(`Frame ${f}/${N} (${(f / N * 100).toFixed(1)}%) | ${fpsActual.toFixed(1)} fps | ETA: ${remain.toFixed(0)}s`);
      }
    }
    ff.stdin.end();
    await new Promise(r => ff.on('close', r));
    console.log('Render complete! File:', out);
  }

  await browser.close();
})();
