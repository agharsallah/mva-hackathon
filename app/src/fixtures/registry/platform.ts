import type {
  HealthDependencies,
  ReferenceProvenanceRow,
  Step1Payload,
  Step2Payload,
  Step3Payload,
  Step4Payload,
  Step5Payload,
  Step6Payload,
  StepsPayload,
  Submissions,
  Track2,
} from '../../api/types';
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
  // TRANSCRIBED from the live endpoint's own reply: `/api/provenance/reference` reads
  // `*provenance.json` off disk, so its offline payload is the real rows, captured from a
  // run of the route. Not synthesised — a fabricated provenance row is the one kind of
  // fixture that would be actively misleading.
  '/api/provenance/reference': {
    source: 'transcribed reference + fixture manifests',
    load: () => rows<ReferenceProvenanceRow[]>('provenance-reference'),
  },
  '/api/probe/ledger': {
    source: 'probe ledger (empty: 0/6 spent)',
    load: () => probeLedgerFixture(),
  },
  // CAPTURED from the live endpoint's own reply, then completed in two documented places.
  // CAPTURED: the real `/api/submissions` answer for this repository, taken with the
  // warehouse reachable (2026-09-05), so the lineage half is the ledger's own rows — 12
  // data_lineage edges walked from the selector tables plus the four edges
  // `resolve_submission_spec.py --record-lineage` appended for this iteration — and the
  // roots (the s3 callset object, the clinical document, the HPO and VEP inputs) carry the
  // versions and digests the ledger holds. Nothing here is completed by hand. No coordinate
  // is present: the iteration folder is coordinate-free by construction (an allele is a
  // WHERE clause over a warehouse table) and the predictions CSV, which does carry
  // positions, is named only by its digest. The `available: false` branch is covered by
  // `src/test/submissions-page.test.tsx`.
  '/api/submissions': {
    source:
      'CAPTURED /api/submissions reply, warehouse reachable (submissions/*/iteration-*/ on disk + warehouse.data_lineage + warehouse.probe_ledger + docs/science-register.json)',
    load: () => rows<Submissions>('submissions'),
  },
  // CAPTURED from the live endpoint's own reply (2026-09-06), warehouse reachable. The route
  // reads `ressources/track2/*.tsv` and their five provenance manifests, `mechanism.json`,
  // `snapshot.json`, `warehouse.data_lineage`, `docs/science-register.json` and the submission
  // folders, and joins them; this is that answer, saved verbatim. Every count, checksum, drug
  // name, trial id and citation is the snapshot's own — nothing is synthesised, which matters
  // more here than elsewhere because a fabricated drug row would read as a clinical claim.
  // No genomic position exists anywhere in it: the mechanism card is coordinate-free by rule
  // and every other table is public gene, drug, trial and citation data.
  '/api/track2': {
    source:
      'CAPTURED /api/track2 reply, warehouse reachable (ressources/track2/*.tsv + *.provenance.json + mechanism.json + snapshot.json, warehouse.data_lineage, docs/science-register.json, submissions/*/iteration-*/)',
    load: () => rows<Track2>('track2'),
  },
  // INVENTED claims. The live register is empty and its tables do not exist yet; these
  // exist so the populated layout can be reviewed before there is anything real to show.
  // CAPTURED from the live endpoint's own reply. Every field of it is assembled from
  // committed sources — the step map, the register and the methodology entries — so a
  // synthesised version would be a second, divergent copy of facts the repository already
  // states. Re-capture after declaring a step or filing a claim.
  '/api/steps': {
    source:
      'CAPTURED /api/steps reply (src/mva/science/steps.py + warehouse.hypotheses + docs/iteration2/*/methodology)',
    load: () => rows<StepsPayload>('steps'),
  },
  // CAPTURED from the live endpoint. Counts, fractions and curves: step 1 never read the
  // DNA, and gene symbols are withheld because it ran blind against iteration 1.
  '/api/steps/step-1': {
    source: 'CAPTURED /api/steps/step-1 reply (build/it2/step-1/*.json)',
    load: () => rows<Step1Payload>('steps-step-1'),
  },
  // CAPTURED from the live endpoint. Aggregates only by design: the four tables behind it
  // carry real proband positions and none of their rows is served, so this file is safe to
  // commit for the same reason the endpoint is safe to serve.
  '/api/steps/step-2': {
    source: 'CAPTURED /api/steps/step-2 reply (pg.results.it2_*, aggregated in SQL)',
    load: () => rows<Step2Payload>('steps-step-2'),
  },
  '/api/steps/step-3': {
    source: 'CAPTURED /api/steps/step-3 reply (pg.results.it2_*, aggregated in SQL)',
    load: () => rows<Step3Payload>('steps-step-3'),
  },
  '/api/steps/step-4': {
    source: 'CAPTURED /api/steps/step-4 reply (pg.results.it2_lr_*, aggregated in SQL)',
    load: () => rows<Step4Payload>('steps-step-4'),
  },
  '/api/steps/step-5': {
    source:
      'CAPTURED /api/steps/step-5 reply (pg.results.it2_pub_alleles + it2_anchors + it2_protein_* + it2_knowledge_ranks)',
    load: () => rows<Step5Payload>('steps-step-5'),
  },
  '/api/steps/step-6': {
    source:
      'CAPTURED /api/steps/step-6 reply (pg.results.it2_fusion_* + it2_route_edges, aggregated in SQL)',
    load: () => rows<Step6Payload>('steps-step-6'),
  },
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
