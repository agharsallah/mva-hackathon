import { describe, expect, it } from 'vitest';

import { int } from './format';

// Smoke test: proves `npm run test` actually runs Vitest against this project
// (jsdom environment, path resolution, TS transform) end to end.
describe('int', () => {
  it('formats with thousands separators', () => {
    expect(int(1000)).toBe('1,000');
  });

  it('renders the em dash for null/undefined', () => {
    expect(int(null)).toBe('—');
    expect(int(undefined)).toBe('—');
  });
});
