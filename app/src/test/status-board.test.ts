/**
 * Four rules the Status page cannot get wrong.
 *
 * 1. It must account for EVERY check the API reports. The board groups by `kind`, and an
 *    earlier version rendered only the four kinds it knew — so a check with any other kind
 *    silently vanished from the one page whose job is to account for all of them.
 * 2. Offline, an endpoint must not claim to be loopback when this checkout is configured
 *    against a server.
 * 3. A masked address must not leave the host or the port readable — including inside a
 *    remedy's `ssh -L` line, where the same port appears twice.
 * 4. A card's age must be stated in the coarsest useful unit, because rows on this board
 *    no longer share one timestamp: re-probing one service leaves the rest as measured.
 */

import { describe, expect, it } from 'vitest';

import type { DependencyCheck } from '../api/types';
import { endpointFor } from '../pages/status/configured';
import { maskAddresses, maskOptional } from '../pages/status/redact';
import { agoLabel, groupChecks, probeAge } from '../pages/status/verdict';

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

describe('maskAddresses', () => {
  it('hides the host and the port of a URL, keeping the scheme and the path', () => {
    const masked = maskAddresses('http://10.0.0.4:9012/mva/reads/runs.parquet');
    expect(masked).toBe('http://••••:••••/mva/reads/runs.parquet');
    expect(masked).not.toContain('9012');
    expect(masked).not.toContain('10.0.0.4');
  });

  it("hides the user, host and port of Postgres' own describe() shape", () => {
    const masked = maskAddresses('mva@db.example:5432/mva (password: set, schemas: a + b)');
    expect(masked).toBe('••••@••••:••••/mva (password: set, schemas: a + b)');
  });

  it('leaves an address that has no host or port alone', () => {
    const rows = 'pg.warehouse.gnomad_constraint + pg.warehouse.clinvar_panel';
    expect(maskAddresses(rows)).toBe(rows);
  });

  it('hides the local port of a tunnel command, not only the remote one', () => {
    // The port appears twice in `-L 9012:host:9012`; masking only the `host:9012` half
    // would publish the number the mask exists to hide.
    const masked = maskAddresses('ssh -N -L 9012:localhost:9012 you@server.example');
    expect(masked).not.toContain('9012');
    expect(masked).not.toContain('server.example');
  });

  it('is idempotent, so re-masking already-masked text is safe', () => {
    const once = maskAddresses('http://host.example:9012/mva');
    expect(maskAddresses(once)).toBe(once);
  });

  it('does not mask a URL query that merely contains an = and a slash', () => {
    const masked = maskAddresses(
      'https://rest.ensembl.org/info/ping?content-type=application/json',
    );
    expect(masked).toBe('https://••••/info/ping?content-type=application/json');
  });

  it('passes a null remedy through, and reveals when not masked', () => {
    expect(maskOptional(null, true)).toBeNull();
    expect(maskOptional('http://host:9012', false)).toBe('http://host:9012');
  });
});

describe('probe age', () => {
  it("reads a check's own timestamp, not the payload's", () => {
    const now = Date.parse('2026-09-03T12:00:00+00:00');
    expect(probeAge('2026-09-03T11:58:00+00:00', now)).toBe(120);
  });

  it('never reports a negative age when a clock is ahead', () => {
    const now = Date.parse('2026-09-03T12:00:00+00:00');
    expect(probeAge('2026-09-03T12:00:30+00:00', now)).toBe(0);
  });

  it('degrades to 0 rather than NaN on an unparseable timestamp', () => {
    expect(probeAge('not a date')).toBe(0);
  });

  it('states the age in the coarsest useful unit', () => {
    expect(agoLabel(3)).toBe('just now');
    expect(agoLabel(45)).toBe('45 s ago');
    expect(agoLabel(600)).toBe('10 m ago');
    expect(agoLabel(7200)).toBe('2 h ago');
  });
});
