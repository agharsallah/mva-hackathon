import { describe, expect, it } from 'vitest';

import type { SubmissionLineageEdge } from '../../api/types';
import { buildSubmissionGraph, foldRoots } from './lineageGraph';

const edge = (source_ref: string, source_kind: string, target: string): SubmissionLineageEdge => ({
  produced_at: '2026-09-25T00:00:00Z',
  target_schema: 'track2',
  target_table: target,
  target_rows: 1,
  source_kind,
  source_ref,
  source_version: '',
  source_sha256: 'abc',
  transform: 't',
  tool: 'tool',
  notes: '',
  is_current: true,
});

// Five file roots feed two tables; one raw root feeds the first.
const edges = [
  ...['a', 'b', 'c', 'd', 'e'].flatMap((f) => [
    edge(`files/${f}`, 'file', 'x'),
    edge(`files/${f}`, 'file', 'y'),
  ]),
  edge('callset.vcf.gz', 'raw', 'x'),
];

describe('folding the roots of a large lineage graph', () => {
  it('leaves a graph at or under the threshold unchanged', () => {
    const graph = buildSubmissionGraph(edges);
    expect(foldRoots(graph, 6)).toBe(graph);
  });

  it('folds a kind with three or more roots into one node and keeps a lone root', () => {
    const folded = foldRoots(buildSubmissionGraph(edges), 3);
    const roots = folded.nodes.filter((n) => n.level === 0).map((n) => n.label);
    expect(roots).toEqual(['callset.vcf.gz', '5 file roots']);
  });

  it('merges the re-pointed edges: one arrow per root kind and target', () => {
    const folded = foldRoots(buildSubmissionGraph(edges), 3);
    const fromFiles = folded.edges.filter((e) => e.from === 'roots:file');
    expect(fromFiles.map((e) => e.to).sort()).toEqual(['track2.x', 'track2.y']);
    expect(fromFiles[0].transform).toBe('5 edges from these roots');
  });
});
