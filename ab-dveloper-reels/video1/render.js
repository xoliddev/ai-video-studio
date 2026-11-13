// node render.js cues            -> sfx_cues.json (sound cue sheet defined in reel.html)
// node render.js stills 1,5,9.5  -> stills/*.jpg
// node render.js video           -> libos_reel.mp4 (needs mix.wav)
const puppeteer = require('puppeteer-core');
const { spawn, execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const [mode = 'video', list = ''] = process.argv.slice(2);
const FPS = 30;
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const FF = execFileSync('python', ['-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())']).toString().trim();
const URL = 'file:///' + path.join(__dirname, 'reel.html').replace(/\\/g, '/') + '?render=1';

(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--force-device-scale-factor=1', '--allow-file-access-from-files'] });
  const page = await browser.newPage();
  page.on('pageerror', e => console.error('page error:', e.message));
  await page.setViewport({ width: 1080, height: 1920 });
  await page.goto(URL, { waitUntil: 'networkidle0', timeout: 120000 });
  await page.evaluate(() => window.READY);
  const shot = async (t, q) => { await page.evaluate(t => seek(t), t); return page.screenshot({ type: 'jpeg', quality: q, clip: { x: 0, y: 0, width: 1080, height: 1920 } }); };

  if (mode === 'cues') {
    const cues = await page.evaluate(() => ({ duration: TL.duration, cues: SFX }));
    fs.writeFileSync(path.join(__dirname, 'sfx_cues.json'), JSON.stringify(cues, null, 1));
    console.log(cues.cues.length, 'cues');
  } else if (mode === 'stills') {
    fs.mkdirSync(path.join(__dirname, 'stills'), { recursive: true });
    for (const s of list.split(',').map(Number)) fs.writeFileSync(path.join(__dirname, 'stills', `t${s.toFixed(2).padStart(6, '0')}.jpg`), await shot(s, 80));
  } else {
    const dur = await page.evaluate(() => TL.duration), N = Math.ceil(dur * FPS);
    const out = path.join(__dirname, 'libos_reel.mp4');
    const ff = spawn(FF, ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
      '-i', path.join(__dirname, 'mix.wav'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p',
      '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
    const t0 = Date.now();
    for (let f = 0; f < N; f++) {
      const buf = await shot(f / FPS, 92);
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (f % 150 === 0) console.log(`frame ${f}/${N} ${((Date.now() - t0) / 1000).toFixed(0)}s`);
    }
    ff.stdin.end();
    await new Promise(r => ff.on('close', r));
    console.log('done', out);
  }
  await browser.close();
})();
