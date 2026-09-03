/**
 * `hasWebGL` — the one seam a test stubs to choose between the canvas and the fallback.
 *
 * Its own file, with one export, for exactly that reason: `vi.mock('../core/capability')` is
 * a two-line mock. In jsdom the answer is always false (there is no GL implementation, and
 * `src/test/setup.ts` stubs `getContext` to `null` so the attempt does not even log), so every
 * page test renders `SceneFallback` — the keyboard path — which is also what axe audits.
 */

let cached: boolean | null = null;

export function hasWebGL(): boolean {
  if (cached !== null) return cached;
  cached = detect();
  return cached;
}

function detect(): boolean {
  if (typeof document === 'undefined') return false;
  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl2') ?? canvas.getContext('webgl');
    return gl !== null;
  } catch {
    return false;
  }
}
