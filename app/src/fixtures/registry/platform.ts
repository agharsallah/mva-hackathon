import type { HealthDependencies } from '../../api/types';
import type { Entry } from '../loader';
import { rows } from '../loader';
import { catalogObjectsFixture } from '../shape/catalog-objects';
import { catalogColumnsFixture } from '../shape/catalog-semantics';
import { catalogTablesFixture } from '../shape/catalog-tables';
import {
  derivationsFixture,
  lineageFixture,
  probeLedgerFixture,
  sourcesFixture,
} from '../shape/provenance';
import { evidenceRegisterFixture, hypothesisRegisterFixture } from '../shape/science';
import { regionEnvelope, searchEnvelope } from '../shape/search';

/**
 * Platform-domain fixtures: the data catalogue, provenance/lineage, the probe ledger,
 * the (invented) research register, and universal search. See `shape/*.ts` for the
 * per-endpoint provenance notes this fragment does not repeat.
 */
export const platformEntries: Record<string, Entry> = {
  '/api/catalog/objects': {
    source: 'object ledger + delivery manifest',
    load: () => catalogObjectsFixture(),
  },
  '/api/catalog/tables': {
    source: 'warehouse catalogue + meta.lineage',
    load: () => catalogTablesFixture(),
  },
  '/api/catalog/columns': {
    source: 'information_schema.columns + the column-meaning registry',
    load: () => catalogColumnsFixture(),
  },
  '/api/provenance/lineage': { source: 'meta.lineage', load: () => lineageFixture() },
  '/api/provenance/derivations': { source: 'meta.derivations', load: () => derivationsFixture() },
  '/api/provenance/sources': { source: 'delivery manifest', load: () => sourcesFixture() },
  '/api/probe/ledger': {
    source: 'probe ledger (empty: 0/18 spent)',
    load: () => probeLedgerFixture(),
  },
  // INVENTED claims. The live register is empty and its tables do not exist yet; these
  // exist so the populated layout can be reviewed before there is anything real to show.
  '/api/science/hypotheses': {
    source: 'INVENTED research register',
    load: () => hypothesisRegisterFixture(),
  },
  '/api/science/evidence': {
    source: 'INVENTED research register',
    load: () => evidenceRegisterFixture(),
  },
  // Both carry their own envelope: `search` answers nothing at all for a query it cannot
  // resolve honestly, so the client re-raises the real error instead of faking a 404.
  '/api/search': { envelope: async (p) => searchEnvelope(p) },
  '/api/callset/region': { envelope: async (p) => regionEnvelope(p) },
  // SHAPED, not measured: the live endpoint does not exist yet (a Python agent is
  // building it against the same contract this was transcribed from — see
  // scratchpad/health-contract.md). Every status value and remedy string is illustrative
  // so the Status page's every state is reviewable offline before there is anything real
  // to probe.
  '/api/health/dependencies': {
    // Every detail, remedy and endpoint string below was captured from real probe runs
    // against the live services on 2026-09-02 (methodology 053) — one healthy, one with
    // Postgres, MinIO and the reads API pointed at dead ports — then reassembled so all
    // four states appear at once and infrastructure hostnames are replaced by loopback
    // defaults. The composition is shaped; none of the text is invented.
    source:
      'SHAPED composition of real probe output — captured 2026-09-02, hostnames replaced with loopback defaults',
    load: () => rows<HealthDependencies>('health-dependencies'),
  },
};
