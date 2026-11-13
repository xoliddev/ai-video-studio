// node render.js <ffmpeg> video          -> islom_savol_javob.mp4
// node render.js <ffmpeg> stills 3,20,40 -> stills/*.jpg
const puppeteer = require('puppeteer-core');
const { spawn } = require('child_process');
const fs = require('fs'), path = require('path');
const [FF, mode = 'video', list = ''] = process.argv.slice(2);
const FPS = 30;
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const URL = 'file:///' + path.join(__dirname, 'film.html').split(path.sep).join('/') + '?render=1';
(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--force-device-scale-factor=1'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1080, height: 1920 });
  page.on('pageerror', e => console.error('page error:', e.message));
  await page.goto(URL, { waitUntil: 'load' });
  await page.evaluate(() => window.READY);
  const grab = (t, q) => page.evaluate((t, q) => { renderAt(t); return document.getElementById('c').toDataURL('image/jpeg', q).slice(23); }, t, q);
  if (mode === 'stills') {
    fs.mkdirSync(path.join(__dirname, 'stills'), { recursive: true });
    for (const s of list.split(',').map(Number))
      fs.writeFileSync(path.join(__dirname, 'stills', `t${String(s).padStart(6, '0')}.jpg`), Buffer.from(await grab(s, .8), 'base64'));
  } else {
    const dur = await page.evaluate(() => TL.duration), N = Math.ceil(dur * FPS);
    const ff = spawn(FF, ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
      '-i', path.join(__dirname, 'narration.wav'), '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000',
      '-vf', 'scale=in_range=pc:out_range=tv,format=yuv420p', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
      '-shortest', '-movflags', '+faststart', path.join(__dirname, 'islom_savol_javob.mp4')], { stdio: ['pipe', 'inherit', 'inherit'] });
    const t0 = Date.now();
    for (let f = 0; f < N; f++) {
      const buf = Buffer.from(await grab(f / FPS, .93), 'base64');
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (f % 600 === 0) console.log(`frame ${f}/${N}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
    }
    ff.stdin.end(); await new Promise(r => ff.on('close', r));
    console.log('done', ((Date.now() - t0) / 1000).toFixed(0) + 's');
  }
  await browser.close();
})();
