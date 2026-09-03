import '@testing-library/jest-dom/vitest';

// jsdom has no WebGL, and `HTMLCanvasElement.prototype.getContext` is not implemented at all:
// calling it emits `Error: Not implemented: HTMLCanvasElement.prototype.getContext (without
// installing the canvas npm package)` through jsdom's virtual console.
//
// Measured 2026-09-03 with this checkout (jsdom 25.0.1, vitest 3.2.7): the call returns `null`
// and vitest prints that jsdomError to **stderr**, not through `console.error` — a spy on
// `console.error` recorded zero calls. So it does not, today, break gate 2
// (`modules.test.tsx`, which asserts `console.error` was never called). The stub is here for
// the other two reasons:
//   1. it keeps a ~12-line stack trace per 3D mount out of the test output, and
//   2. it makes `src/viz3d/core/capability.ts`'s `hasWebGL()` deterministically false, so
//      every page test renders `SceneFallback` — the keyboard path, which is also the thing
//      `a11y.test.tsx` can actually audit — instead of depending on jsdom internals.
// A test that wants the canvas path mocks `core/capability` directly; see
// `src/viz3d/components/Viz3dCanvas.test.tsx`.
//
// It is scoped to the WebGL context ids only. Replacing `getContext` wholesale also handed
// `null` to any future `'2d'` caller, which is a silent failure in a test nobody has written
// yet; other ids are delegated to jsdom's own implementation. That implementation is the one
// that throws/logs in jsdom, so the delegation is wrapped — a `'2d'` caller gets the same
// `null` it would have got, without this file being the reason.
const WEBGL_IDS = new Set(['webgl', 'webgl2', 'experimental-webgl']);
const original = HTMLCanvasElement.prototype.getContext;

HTMLCanvasElement.prototype.getContext = function getContext(
  this: HTMLCanvasElement,
  id: string,
  ...rest: unknown[]
) {
  if (WEBGL_IDS.has(id)) return null;
  try {
    return (original as unknown as (...args: unknown[]) => unknown).call(this, id, ...rest) ?? null;
  } catch {
    return null;
  }
} as HTMLCanvasElement['getContext'];
