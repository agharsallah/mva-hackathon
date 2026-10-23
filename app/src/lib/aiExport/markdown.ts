/**
 * The export format: prose, then the numbers the prose is about.
 *
 * Markdown with fenced JSON rather than either alone. A JSON-only dump loses the legend,
 * which is the only place the filtering and derivation rules of a figure are written down;
 * prose alone loses the rows an analysis has to work on. Interleaving them keeps each
 * payload directly under the sentences that say how to read it.
 */

import { SAMPLE_ID } from '../../demo';
import type { EndpointRecord, ExhibitRecord } from './types';

const NO_PAYLOAD =
  '_No structured payload captured for this exhibit — the narrative above is the whole record._';

const CAVEAT = [
  'Every `json` block below is the **endpoint payload as fetched**, and may be a superset of',
  'what the exhibit displays: filters, thresholds, sorts and derived series applied in the',
  'browser are described in that exhibit’s own Legend and Reading text, printed directly above',
  'its payload. Read the prose before treating the rows as what was on screen.',
].join(' ');

function fence(data: unknown): string {
  return ['```json', JSON.stringify(data, null, 2), '```'].join('\n');
}

function provenance(r: { source?: string; cachedAt?: string | null; origin?: string }): string[] {
  const parts: string[] = [];
  if (r.source) parts.push(`**Source:** ${r.source}`);
  if (r.cachedAt) parts.push(`**Cached at:** ${r.cachedAt}`);
  if (r.origin) parts.push(`**Origin:** ${r.origin}`);
  return parts.length > 0 ? [parts.join(' · ')] : [];
}

export function exhibitSection(r: ExhibitRecord): string {
  const lines = [`## ${r.title}`, '', `**Legend.** ${r.legend}`];
  if (r.reading) lines.push('', `**Reading.** ${r.reading}`);
  const prov = provenance(r);
  if (prov.length > 0) lines.push('', ...prov);
  lines.push('', r.data === undefined ? NO_PAYLOAD : fence(r.data));
  return lines.join('\n');
}

export function endpointSection(r: EndpointRecord): string {
  const lines = [`## \`${r.path}\``, ''];
  if (r.error) {
    lines.push(`_fetch failed: ${r.error}_`);
    return lines.join('\n');
  }
  const prov = provenance(r);
  if (prov.length > 0) lines.push(...prov, '');
  lines.push(r.data === undefined ? NO_PAYLOAD : fence(r.data));
  return lines.join('\n');
}

/** Wrap sections in a preamble that says what the document is and how to read its JSON. */
export function bundleMarkdown(
  scope: string,
  sections: string[],
  extraNotes: string[] = [],
): string {
  const head = [
    '# MVA case export',
    '',
    `**Scope:** ${scope}`,
    `**Generated:** ${new Date().toISOString()}`,
    '',
    'This document was exported from the MVA Case Explorer for analysis by a language model.',
    `It describes one whole-genome case (proband \`${SAMPLE_ID}\`, single sample, no parents).`,
    '',
    CAVEAT,
    '',
    'No patient variant coordinate appears in this document. Chromosome and position are stripped',
    'from every variant-level payload, and the exhibits whose subject *is* the coordinate — the locus',
    'tracks, the pair matrix, a searched window — export their narrative and no rows at all. What does',
    'appear is chromosome names, 1 Mb bin indices and reference gene spans: aggregates and public',
    'reference data, not this proband’s variant positions. Name genes and consequences in any answer,',
    'never positions.',
    ...extraNotes.flatMap((n) => ['', n]),
  ];
  return [head.join('\n'), ...sections].join('\n\n---\n\n') + '\n';
}

export function exhibitBundle(scope: string, records: ExhibitRecord[]): string {
  if (records.length === 0) {
    return bundleMarkdown(scope, [], ['_No exhibit was mounted when this export ran._']);
  }
  return bundleMarkdown(scope, records.map(exhibitSection));
}
