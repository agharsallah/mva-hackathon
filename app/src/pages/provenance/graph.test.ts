/**
 * The reference-service join, tested for the one property that matters: it must not
 * fabricate a lineage edge.
 *
 * `warehouse.data_lineage` records derivations (table X computed from object Y). Reference
 * data has none — it was fetched — so every edge this join adds is marked `manifest`, and
 * the lineage edges `buildGraph` produced must come through untouched.
 */

import { describe, expect, it } from 'vitest';

import type { LineageRow, ReferenceProvenanceRow } from '../../api/types';
import { buildGraph, REFERENCE_SINK, referenceJoin, withReferenceServices } from './graph';

const lineage = (over: Partial<LineageRow> = {}): LineageRow => ({
  produced_at: '2026-09-01T00:00:00+00:00',
  target_schema: 'raw',
  target_table: 'variants',
  target_rows: 10,
  source_kind: 'object',
  source_ref: 'delivery/proband.vcf.gz',
  source_version: null,
  source_sha256: 'abc',
  transform: 'load',
  tool: 'mva-load',
  notes: null,
  ...over,
});

const manifest = (over: Partial<ReferenceProvenanceRow> = {}): ReferenceProvenanceRow => ({
  name: 'structure_genes',
  kind: 'reference',
  path: 'ressources/reference/structure_genes.provenance.json',
  built_at: '2026-09-03T12:05:55+00:00',
  built_by: 'tools/build_gene_set.py',
  code_version: 'cb066b8',
  inputs: [
    {
      name: 'Ensembl REST',
      url: 'https://rest.ensembl.org',
      release: '116',
      sha256: null,
      bytes: null,
    },
    {
      name: 'spec',
      url: 'file://ressources/reference/structure_genes.spec.tsv',
      release: null,
      sha256: 'b6ac',
      bytes: 2311,
    },
  ],
  outputs: [
    { path: 'ressources/reference/structure_genes.tsv', sha256: '1124', bytes: 2569, rows: 23 },
  ],
  note: 'note',
  ...over,
});

describe('referenceJoin', () => {
  it('makes one node per distinct remote host and ignores file:// reads', () => {
    const join = referenceJoin([
      manifest(),
      manifest({
        name: 'protein-structure fixtures',
        kind: 'fixture',
        inputs: [
          {
            name: 'Ensembl REST',
            url: 'https://rest.ensembl.org',
            release: '116',
            sha256: null,
            bytes: null,
          },
          {
            name: 'AlphaFold',
            url: 'https://alphafold.ebi.ac.uk/api/prediction/{accession}',
            release: '6',
            sha256: null,
            bytes: null,
          },
        ],
        outputs: [
          { path: 'app/src/fixtures/data/protein/TP53.json', sha256: 'ff', bytes: 100, rows: 393 },
          { path: 'app/src/fixtures/data/protein/BUB1B.json', sha256: 'ee', bytes: 50, rows: 1050 },
        ],
      }),
    ]);
    expect(join.services.map((s) => s.host)).toEqual(['alphafold.ebi.ac.uk', 'rest.ensembl.org']);
    // Each host carries the release(s) it was pinned at, de-duplicated across manifests.
    expect(join.services.find((s) => s.host === 'rest.ensembl.org')?.releases).toEqual(['116']);
    expect(join.services.find((s) => s.host === 'alphafold.ebi.ac.uk')?.releases).toEqual(['6']);
    expect(join.sink).toEqual({ files: 3, bytes: 2719 });
  });

  it('yields no sink at all when nothing was fetched from a service', () => {
    const local = manifest({
      inputs: [{ name: 'spec', url: 'file://spec.tsv', release: null, sha256: 'b6', bytes: 1 }],
    });
    expect(referenceJoin([local])).toEqual({ services: [], sink: null });
    expect(referenceJoin([])).toEqual({ services: [], sink: null });
  });
});

describe('withReferenceServices', () => {
  const base = buildGraph([lineage(), lineage({ target_schema: 'results', target_table: 'qc' })]);

  it('adds the services as dotted manifest edges and touches no lineage edge', () => {
    const before = buildGraph([lineage()]);
    const after = withReferenceServices(buildGraph([lineage()]), referenceJoin([manifest()]));

    expect(after.edges.filter((e) => e.kind === 'lineage')).toEqual(
      before.edges.filter((e) => e.kind === 'lineage'),
    );
    const added = after.edges.filter((e) => e.kind === 'manifest');
    expect(added).toHaveLength(1);
    expect(added[0]?.to).toBe(REFERENCE_SINK);
    expect(added[0]?.transform).toContain('not in warehouse.data_lineage');
  });

  it('marks every added node as a service, so the renderer can dash them', () => {
    const after = withReferenceServices(base, referenceJoin([manifest()]));
    const services = after.nodes.filter((n) => n.kind === 'service');
    expect(services.map((n) => n.id)).toEqual(
      expect.arrayContaining(['service:rest.ensembl.org', REFERENCE_SINK]),
    );
    // A file count is not a row count: the sink must not claim rows.
    expect(after.nodes.find((n) => n.id === REFERENCE_SINK)?.rows).toBeNull();
  });

  it('is a no-op when there is nothing to join, so the graph keeps its lineage-only claim', () => {
    const untouched = buildGraph([lineage()]);
    expect(withReferenceServices(untouched, { services: [], sink: null })).toBe(untouched);
  });

  it('counts the sink in `levels`, so an empty lineage still draws it inside the viewBox', () => {
    // The regression: with no lineage rows the graph is one level deep, and returning
    // `graph.levels` unchanged made `LineageGraph`'s width one node wide while the sink was
    // placed a level to the right of it.
    const empty = buildGraph([]);
    expect(empty.levels).toBe(1);
    const after = withReferenceServices(empty, referenceJoin([manifest()]));
    expect(after.nodes.find((n) => n.id === REFERENCE_SINK)?.level).toBe(1);
    expect(after.levels).toBe(2);
  });

  it('copies the nodes it re-slots, so calling it twice on one graph is safe', () => {
    const graph = buildGraph([lineage()]);
    const before = graph.nodes.map((n) => `${n.id}:${n.slot}`);
    const once = withReferenceServices(graph, referenceJoin([manifest()]));
    const twice = withReferenceServices(graph, referenceJoin([manifest()]));
    expect(graph.nodes.map((n) => `${n.id}:${n.slot}`)).toEqual(before);
    expect(twice.nodes.map((n) => `${n.id}:${n.slot}`)).toEqual(
      once.nodes.map((n) => `${n.id}:${n.slot}`),
    );
  });

  it('re-slots every level so no two nodes overlap after the append', () => {
    const after = withReferenceServices(base, referenceJoin([manifest()]));
    const seen = new Set<string>();
    for (const n of after.nodes) {
      const cell = `${n.level}:${n.slot}`;
      expect(seen.has(cell)).toBe(false);
      seen.add(cell);
    }
  });
});
