/**
 * Browser-measurement helpers shared by the `viz3d` verification drivers, split out of
 * `verify-protein-explorer.mjs` to keep each file inside the repo's 400-line rule.
 *
 * Nothing here knows about the protein exhibit: it is playwright resolution, a frame-rate
 * counter, a "how much of the canvas is painted" probe and a bounding-box comparison.
 */

import { execFileSync } from 'node:child_process';
import { existsSync, readdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import os from 'node:os';
import path from 'node:path';

/**
 * Which Chromium to drive. A globally installed `playwright` pins a browser build number that
 * the machine's `ms-playwright` cache may not hold (they are updated independently), and
 * `npx playwright install` is a 150 MB download. So: an explicit `--chromium=<path>`, else the
 * newest Chromium already in the cache, else playwright's own default.
 */
export function chromiumPath(explicit) {
  if (explicit) return explicit;
  const cache = path.join(os.homedir(), 'Library', 'Caches', 'ms-playwright');
  if (!existsSync(cache)) return undefined;
  const builds = readdirSync(cache)
    .filter((name) => /^chromium-\d+$/.test(name))
    .sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]));
  for (const build of builds) {
    for (const exe of [
      'chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',
      'chrome-mac/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',
      'chrome-linux/chrome',
    ]) {
      const full = path.join(cache, build, exe);
      if (existsSync(full)) return full;
    }
  }
  return undefined;
}

/** Resolve playwright from this package, the repo, or the global npm root. */
export async function loadPlaywright(here, repo) {
  const roots = [here, repo];
  try {
    roots.push(execFileSync('npm', ['root', '-g'], { encoding: 'utf8' }).trim());
  } catch {
    /* npm not on PATH: the two local roots are still worth trying */
  }
  for (const root of roots) {
    try {
      const require = createRequire(path.join(root, 'noop.js'));
      // playwright ships CommonJS, so a dynamic `import()` of it puts the exports on `default`.
      const mod = await import(require.resolve('playwright'));
      if (mod.chromium ?? mod.default?.chromium) return mod.default ?? mod;
    } catch {
      /* try the next root */
    }
  }
  throw new Error(
    'playwright not found. Install it for this machine (`npm i -g playwright && npx playwright ' +
      'install chromium`) — it is deliberately not an app dependency.',
  );
}

/** Frames the browser scheduled per second, over a fixed wall-clock window. See the note above. */
export const measureFps = (page, ms) =>
  page.evaluate(
    (window) =>
      new Promise((resolve) => {
        let frames = 0;
        const started = performance.now();
        const tick = () => {
          frames++;
          if (performance.now() - started < window) globalThis.requestAnimationFrame(tick);
          else {
            const elapsed = performance.now() - started;
            resolve({
              frames,
              ms: Math.round(elapsed),
              fps: +(frames / (elapsed / 1000)).toFixed(1),
            });
          }
        };
        globalThis.requestAnimationFrame(tick);
      }),
    ms,
  );

/**
 * How much of the canvas the figure covers: the bounding box of every non-transparent pixel,
 * as a fraction of each canvas side. The renderer clears to alpha 0, so "drawn" == "opaque".
 *
 * The measurement is a `drawImage` of the WebGL canvas into a 240-px-wide 2D canvas, read back
 * with `getImageData`. Not `gl.readPixels`: on SwiftShader, resolving the multisampled default
 * framebuffer at 1206 x 520 while the render loop runs blocked for **minutes** per call
 * (measured, which is why this path exists). The downscale is also why the number is quoted to
 * the nearest per cent and not finer.
 *
 * It runs inside a `requestAnimationFrame` callback so the drawing buffer still holds a
 * rendered frame: `WebGLRenderer` is created without `preserveDrawingBuffer`, and three's own
 * loop callback was registered before this one, so by the time this runs the frame is drawn.
 */
export const measureFill = (page, nth = 0) =>
  page.evaluate(
    // `nth` selects among several 3D canvases on one page — the side-by-side protein
    // comparison mounts two beside the single-gene explorer. Default 0 = the first, which is
    // what every earlier caller measured.
    (index) =>
      new Promise((resolve) => {
        globalThis.requestAnimationFrame(() => {
          const canvas = globalThis.document.querySelectorAll('canvas[role="img"]')[index];
          if (!canvas) return resolve(null);
          const w = 240;
          const h = Math.max(1, Math.round((w * canvas.height) / canvas.width));
          const small = globalThis.document.createElement('canvas');
          small.width = w;
          small.height = h;
          const ctx = small.getContext('2d', { willReadFrequently: true });
          ctx.clearRect(0, 0, w, h);
          ctx.drawImage(canvas, 0, 0, w, h);
          const px = ctx.getImageData(0, 0, w, h).data;
          let minX = w;
          let maxX = -1;
          let minY = h;
          let maxY = -1;
          let drawn = 0;
          for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
              if (px[(y * w + x) * 4 + 3] <= 10) continue;
              drawn++;
              if (x < minX) minX = x;
              if (x > maxX) maxX = x;
              if (y < minY) minY = y;
              if (y > maxY) maxY = y;
            }
          }
          if (maxX < 0) {
            return resolve({
              width: 0,
              height: 0,
              shorterSide: 0,
              box: null,
              ink: 0,
              canvas: [w, h],
            });
          }
          const width = (maxX - minX + 1) / w;
          const height = (maxY - minY + 1) / h;
          resolve({
            width: +width.toFixed(3),
            height: +height.toFixed(3),
            // The fraction of the *shorter* canvas side the figure spans along that side.
            shorterSide: +(canvas.width <= canvas.height ? width : height).toFixed(3),
            box: [minX / w, minY / h, maxX / w, maxY / h].map((n) => +n.toFixed(3)),
            // Share of the canvas actually painted — a tube is thin, so this is small even
            // when the bounding box fills the frame.
            ink: +(drawn / (w * h)).toFixed(3),
            canvas: [canvas.width, canvas.height],
          });
        });
      }),
    nth,
  );

/** Largest per-edge move of the drawn figure's bounding box, as a fraction of the canvas. */
export const boxDrift = (a, b) =>
  a?.box && b?.box ? +Math.max(...a.box.map((n, i) => Math.abs(n - b.box[i]))).toFixed(3) : null;

/**
 * `--key=value` and `--key value` both, so a usage line can be pasted as written.
 *
 * Shared because every driver in this folder takes the same three: `--url`, `--out`,
 * `--chromium`.
 */
export function parseArgs(argv) {
  const args = new Map();
  for (let i = 2; i < argv.length; i++) {
    const token = argv[i];
    if (!token.startsWith('--')) continue;
    const [key, ...rest] = token.slice(2).split('=');
    if (rest.length > 0) args.set(key, rest.join('='));
    else if (argv[i + 1] && !argv[i + 1].startsWith('--')) args.set(key, argv[++i]);
    else args.set(key, 'true');
  }
  return args;
}

/**
 * A clipped *page* screenshot around one element, not an element screenshot.
 *
 * Playwright's element screenshot waits for the element to be "stable", and a canvas driven
 * by a render loop never satisfies that. `above`/`below` widen the clip so the controls and
 * the legend that decode the picture land in the same frame.
 */
export async function clipShot(page, target, file, { above = 150, below = 260 } = {}) {
  await target.scrollIntoViewIfNeeded();
  const box = await target.boundingBox();
  const top = Math.max(0, box.y - above);
  await page.screenshot({
    path: file,
    clip: {
      x: 0,
      y: top,
      width: page.viewportSize().width,
      height: Math.min(box.height + (box.y - top) + below, page.viewportSize().height - top),
    },
  });
  return file;
}
