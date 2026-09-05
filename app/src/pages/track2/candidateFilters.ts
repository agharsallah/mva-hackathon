/**
 * Pure derivations over the candidate table.
 *
 * Kept out of the component so the filter semantics are one testable function rather than a
 * chain of `.filter()` calls inside a render, and so the page can compute the per-direction
 * counts the directions table needs without duplicating the "approved" rule.
 */

import type { CandidateRow } from '../../api/types';
import type { Bar } from './CandidateCharts';

export interface CandidateFilters {
  /** Default ON: the challenge's Track 2 definition is market-approved drugs only. */
  approvedOnly: boolean;
  /** A direction id (`D1`), or `all`. */
  direction: string;
  /** A source name (`chembl`), or `all`. */
  source: string;
  /** Free text over drug name, target, mechanism of action and drug id. */
  text: string;
}

export const DEFAULT_FILTERS: CandidateFilters = {
  approvedOnly: true,
  direction: 'all',
  source: 'all',
  text: '',
};

export function filterCandidates(rows: CandidateRow[], f: CandidateFilters): CandidateRow[] {
  const needle = f.text.trim().toLowerCase();
  return rows.filter((r) => {
    if (f.approvedOnly && !r.approved) return false;
    if (f.direction !== 'all' && !r.direction_ids.includes(f.direction)) return false;
    if (f.source !== 'all' && !r.source.includes(f.source)) return false;
    if (!needle) return true;
    const hay = `${r.drug_name} ${r.drug_id} ${r.target_symbol} ${r.interaction_or_moa} ${r.action_type}`;
    return hay.toLowerCase().includes(needle);
  });
}

/** Every direction id present in the table, sorted — the picker's options, never hard-coded. */
export function directionIds(rows: CandidateRow[]): string[] {
  const set = new Set<string>();
  for (const r of rows) for (const d of r.direction_ids) set.add(d);
  return [...set].sort();
}

/** Every source name present in the table, sorted. */
export function sourceNames(rows: CandidateRow[]): string[] {
  const set = new Set<string>();
  for (const r of rows) for (const s of r.source) set.add(s);
  return [...set].sort();
}

/** Approved drug-target rows per direction id — what the directions table counts. */
export function approvedPerDirection(rows: CandidateRow[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const r of rows) {
    if (!r.approved) continue;
    for (const d of r.direction_ids) out[d] = (out[d] ?? 0) + 1;
  }
  return out;
}

/**
 * Distinct **approved drug names** per seed target, biggest first.
 *
 * Distinct names, not rows: the same molecule appears once per source that reported it, so
 * counting rows would rank a well-catalogued target above a well-drugged one.
 */
export function approvedDrugsPerSeedTarget(rows: CandidateRow[], top = 12): Bar[] {
  const perTarget = new Map<string, Set<string>>();
  for (const r of rows) {
    if (r.target_role !== 'seed' || !r.approved) continue;
    const key = r.target_symbol;
    if (!perTarget.has(key)) perTarget.set(key, new Set());
    perTarget.get(key)!.add(r.drug_name.toLowerCase());
  }
  return [...perTarget.entries()]
    .map(([label, drugs]) => ({ label, value: drugs.size }))
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label))
    .slice(0, top);
}

/** Rows per source API, with the approved subset drawn in front of the total. */
export function rowsPerSource(rows: CandidateRow[]): Bar[] {
  const total = new Map<string, number>();
  const approved = new Map<string, number>();
  for (const r of rows) {
    for (const s of r.source) {
      total.set(s, (total.get(s) ?? 0) + 1);
      if (r.approved) approved.set(s, (approved.get(s) ?? 0) + 1);
    }
  }
  return [...total.entries()]
    .map(([label, t]) => ({ label, value: approved.get(label) ?? 0, total: t }))
    .sort((a, b) => (b.total ?? 0) - (a.total ?? 0));
}
