/**
 * Two rules the Status page cannot get wrong.
 *
 * 1. It must account for EVERY check the API reports. The board groups by `kind`, and an
 *    earlier version rendered only the four kinds it knew — so a check with any other kind
 *    silently vanished from the one page whose job is to account for all of them.
 * 2. Offline, an endpoint must not claim to be loopback when this checkout is configured
 *    against a server.
 */

import { describe, expect, it } from 'vitest';

import type { DependencyCheck } from '../api/types';
import { endpointFor } from '../pages/status/configured';
import { groupChecks } from '../pages/status/verdict';

const check = (id: string, kind: string): DependencyCheck =>
  ({
    id,
    name: id,
    kind,
    status: 'up',
    latency_ms: 1,
    detail: '',
    remedy: null,
    powers: [],
    endpoint: null,
  }) as unknown as DependencyCheck;

describe('groupChecks', () => {
  it('keeps every check when all kinds are known', () => {
    const checks = [
      check('viz-api', 'internal'),
      check('reads-api', 'upstream'),
      check('ensembl', 'third-party'),
      check('reference-snapshots', 'snapshot'),
    ];
    const grouped = groupChecks(checks);
    expect(grouped.flatMap((g) => g.checks)).toHaveLength(checks.length);
  });

  it('shows a check whose kind this build does not know, instead of dropping it', () => {
    const checks = [check('viz-api', 'internal'), check('something-new', 'quantum-uplink')];
    const grouped = groupChecks(checks);
    expect(grouped.flatMap((g) => g.checks).map((c) => c.id)).toContain('something-new');
    expect(grouped.find((g) => g.key === 'other')?.title).toBe('Other');
  });

  it('drops empty groups but never a check', () => {
    const grouped = groupChecks([check('viz-api', 'internal')]);
    expect(grouped).toHaveLength(1);
    expect(grouped[0].checks).toHaveLength(1);
  });
});

describe('endpointFor', () => {
  it('trusts the payload when the API answered', () => {
    expect(endpointFor('warehouse', 'db.example:5432/mva', 'api')).toEqual({
      value: 'db.example:5432/mva',
      fromEnv: false,
    });
  });

  it('returns nothing when neither the payload nor the build has an address', () => {
    expect(endpointFor('viz-api', null, 'api')).toBeNull();
  });

  it('falls back to the payload offline when the build inlined no configuration', () => {
    // In a test run there is no __CONFIGURED_ENDPOINTS__ define, which is the same state as
    // a build made without a repo-root .env.
    expect(endpointFor('warehouse', 'placeholder:5432/mva', 'fixture')).toEqual({
      value: 'placeholder:5432/mva',
      fromEnv: false,
    });
  });
});
