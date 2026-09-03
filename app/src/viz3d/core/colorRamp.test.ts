import { describe, expect, it } from 'vitest';

import { C, DENSITY_SCALE, QUALITY_SCALE, RAMP, TONE_MARK } from '../../lib/palette';
import {
  absentRgb,
  hexToRgb,
  linearizeColors,
  normalise,
  rampColors,
  sampleScale,
  srgbToLinear,
  toneRgb,
} from './colorRamp';

/** A Float32Array stores float32, so a buffer read is compared per channel, not deep-equal. */
const expectRgb = (got: readonly number[], want: readonly number[]): void =>
  want.forEach((channel, i) => expect(got[i]).toBeCloseTo(channel, 6));

/** Both halves of the palette must agree, so a stop is checked against the ramp it names. */
describe('sampleScale', () => {
  it('returns the first stop exactly at t = 0', () => {
    expect(sampleScale(DENSITY_SCALE, 0)).toEqual(hexToRgb(RAMP.chrome[950]));
    expect(hexToRgb(DENSITY_SCALE[0][1])).toEqual(hexToRgb(RAMP.chrome[950]));
  });

  it('returns the last stop exactly at t = 1', () => {
    expect(sampleScale(DENSITY_SCALE, 1)).toEqual(hexToRgb(RAMP.raw[200]));
  });

  it('lands on a declared interior stop exactly', () => {
    expect(sampleScale(QUALITY_SCALE, 0.6)).toEqual(hexToRgb(RAMP.decision[500]));
  });

  it('interpolates linearly between two stops', () => {
    const a = hexToRgb(DENSITY_SCALE[0][1]);
    const b = hexToRgb(DENSITY_SCALE[1][1]);
    const mid = sampleScale(DENSITY_SCALE, 0.075);
    mid.forEach((channel, i) => expect(channel).toBeCloseTo((a[i] + b[i]) / 2, 5));
  });

  it('clamps out-of-range and non-finite positions instead of extrapolating', () => {
    expect(sampleScale(DENSITY_SCALE, -3)).toEqual(sampleScale(DENSITY_SCALE, 0));
    expect(sampleScale(DENSITY_SCALE, 9)).toEqual(sampleScale(DENSITY_SCALE, 1));
    expect(sampleScale(DENSITY_SCALE, NaN)).toEqual(sampleScale(DENSITY_SCALE, 0));
  });
});

describe('hexToRgb', () => {
  it('reads a six-digit stop', () => {
    expect(hexToRgb(RAMP.chrome[50]).every((c) => c >= 0 && c <= 1)).toBe(true);
  });

  it('ignores a trailing alpha pair, so C.machineryFill parses as its base colour', () => {
    expect(hexToRgb(C.machineryFill)).toEqual(hexToRgb(RAMP.machinery[900]));
  });
});

describe('rampColors', () => {
  it('emits three floats per value', () => {
    expect(rampColors([0, 1, 2], DENSITY_SCALE, [0, 2])).toHaveLength(9);
  });

  it('paints a null in the absent grey rather than interpolating over it', () => {
    const out = rampColors([0, null], DENSITY_SCALE, [0, 1]);
    expectRgb([out[3], out[4], out[5]], absentRgb());
  });

  it('maps the domain ends onto the scale ends', () => {
    const out = rampColors([10, 20], DENSITY_SCALE, [10, 20]);
    expectRgb([out[0], out[1], out[2]], sampleScale(DENSITY_SCALE, 0));
    expectRgb([out[3], out[4], out[5]], sampleScale(DENSITY_SCALE, 1));
  });
});

describe('normalise', () => {
  it('reads a zero-width domain as 0 instead of dividing by zero', () => {
    expect(normalise(5, [5, 5])).toBe(0);
  });

  it('clamps outside the domain', () => {
    expect(normalise(-1, [0, 10])).toBe(0);
    expect(normalise(99, [0, 10])).toBe(1);
  });
});

describe('tone and colour space', () => {
  it('resolves a tone through TONE_MARK, never a hex of its own', () => {
    expect(toneRgb('good')).toEqual(hexToRgb(TONE_MARK.good));
  });

  it('srgbToLinear is monotonic and fixes the endpoints', () => {
    expect(srgbToLinear(0)).toBe(0);
    expect(srgbToLinear(1)).toBeCloseTo(1, 6);
    expect(srgbToLinear(0.5)).toBeLessThan(0.5);
  });

  it('linearizeColors works in place over the whole buffer', () => {
    const buffer = new Float32Array([0, 0.5, 1]);
    expect(linearizeColors(buffer)).toBe(buffer);
    expect(buffer[1]).toBeCloseTo(srgbToLinear(0.5), 6);
  });
});
