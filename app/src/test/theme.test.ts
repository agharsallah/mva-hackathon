/**
 * The theme switch, from both ends: the store the reader drives, and the palette the charts
 * read.
 *
 * The pairing is the point. The DOM half of the light theme is a CSS selector nothing in
 * JavaScript can observe under jsdom, so what is checked here is the half that *is*
 * observable and the half that can silently rot: that flipping the store re-points every
 * structural colour (`C.ink` and friends) while leaving the data marks (`C.good`, the 500
 * stops) exactly where they were. A regression that froze `C` at import time — the obvious
 * way to write it — fails the third test below.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import {
  C,
  DENSITY_SCALE,
  LIGHT_RAMP,
  mirrorRamp,
  mirrorShade,
  RAMP,
  SHADES,
} from '../lib/palette';
import { themeStore } from '../lib/theme';

const STORAGE_KEY = 'mva.theme';

beforeEach(() => {
  localStorage.clear();
  themeStore.set('dark');
});

afterEach(() => {
  themeStore.set('dark');
  localStorage.clear();
});

describe('the mirror', () => {
  it('maps shade N to shade 1000 - N, and 500 to itself', () => {
    for (const shade of SHADES) expect(mirrorShade(shade)).toBe(1000 - shade);
    expect(mirrorShade(500)).toBe(500);
    // The mirror is only well defined because the step set is symmetric: every mirrored
    // shade has to be a shade that exists, or a family would gain a hole in light mode.
    for (const shade of SHADES) expect(SHADES).toContain(mirrorShade(shade));
  });

  it('is its own inverse, and leaves the dark ramp untouched', () => {
    expect(mirrorRamp(LIGHT_RAMP)).toEqual(RAMP);
    expect(LIGHT_RAMP.chrome[950]).toBe(RAMP.chrome[50]);
    expect(LIGHT_RAMP.good[500]).toBe(RAMP.good[500]);
  });
});

describe('themeStore', () => {
  it('defaults to dark with no stored choice and no light OS preference', () => {
    // jsdom's matchMedia is absent by default, so `initial()` fell through to dark at import.
    expect(themeStore.get()).toBe('dark');
  });

  it('writes the document attribute, the colour scheme and localStorage on a toggle', () => {
    themeStore.toggle();
    expect(themeStore.get()).toBe('light');
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(document.documentElement.style.colorScheme).toBe('light');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('light');

    themeStore.toggle();
    expect(themeStore.get()).toBe('dark');
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('dark');
  });

  it('notifies subscribers, and stops once unsubscribed', () => {
    let calls = 0;
    const stop = themeStore.subscribe(() => calls++);
    themeStore.set('light');
    expect(calls).toBe(1);
    themeStore.set('light'); // same value: no work, no notification
    expect(calls).toBe(1);
    stop();
    themeStore.set('dark');
    expect(calls).toBe(1);
  });
});

describe('the canvas palette follows the theme', () => {
  it('re-points every structural colour', () => {
    const darkInk = C.ink;
    const darkPaper = C.paper;
    const darkGrid = C.grid;
    themeStore.set('light');
    expect(C.ink).not.toBe(darkInk);
    expect(C.paper).not.toBe(darkPaper);
    expect(C.grid).not.toBe(darkGrid);
    // Not just "different" — the mirrored value, so ink stays as far from paper as it was.
    expect(C.ink).toBe(RAMP.chrome[mirrorShade(200)]);
    expect(C.paper).toBe(RAMP.chrome[mirrorShade(950)]);
  });

  it('leaves the data marks alone, so a legend stays true across a switch', () => {
    const marks = [C.good, C.broken, C.decision, C.machinery, C.raw, C.absent];
    themeStore.set('light');
    expect([C.good, C.broken, C.decision, C.machinery, C.raw, C.absent]).toEqual(marks);
    expect(C.good).toBe(RAMP.good[500]);
  });

  it('rebuilds the chrome-anchored scales so their cold end is the page, not black', () => {
    expect(DENSITY_SCALE[0][1]).toBe(RAMP.chrome[950]);
    themeStore.set('light');
    expect(DENSITY_SCALE[0][1]).toBe(RAMP.chrome[50]);
    expect(DENSITY_SCALE[0][1]).toBe(C.paper);
  });
});
