/**
 * The closest candidate pairs, as a table — the numeric twin of the line drawn in the canvas.
 *
 * The canvas answers "are these two close?" for the one pair a reader picked. This answers it
 * for every pair at once, sorted, which is what makes the exhibit an *analysis* rather than a
 * picture. The first cell of each row is a button that picks that pair in the 3D view, so the
 * table and the canvas are two views of one selection.
 *
 * Every column is either measured off the model (distance, sequence gap, confidence) or
 * copied from the annotation payload (rarity, domain, phase). Nothing is inferred.
 */

import { type Column, DataTable } from '../../../components/DataTable';
import { impactColor } from '../../../lib/palette';
import { angstromLabel, type CandidateDistance } from './distances';

const YES = '✓';
const NO = '·';

function flag(on: boolean, tone: 'good' | 'chrome' = 'good') {
  return (
    <span
      className={on ? (tone === 'good' ? 'text-good-400' : 'text-chrome-300') : 'text-chrome-600'}
    >
      {on ? YES : NO}
    </span>
  );
}

const PHASE_CLASS: Record<CandidateDistance['phase'], string> = {
  trans: 'text-good-400',
  'auto-trans': 'text-decision-400',
  cis: 'text-broken-400',
  unknown: 'text-chrome-500',
};

/**
 * The hand-off to the side-by-side comparison. Optional and additive: without it the table
 * renders exactly as it always did.
 */
export interface CompareWith {
  gene: string;
  /** Stage this gene as side A of the comparison exhibit, leaving side B where it is. */
  onCompare: () => void;
}

export function DistanceTable({
  rows,
  selected,
  onPick,
  compareWith,
}: {
  rows: readonly CandidateDistance[];
  /** `key` of the row currently drawn as a link in the canvas. */
  selected: string | null;
  onPick: (row: CandidateDistance) => void;
  compareWith?: CompareWith;
}) {
  const columns: Column<CandidateDistance>[] = [
    {
      key: 'pair',
      header: 'pair of alleles',
      sortValue: (r) => r.a.n,
      render: (r) => (
        <button
          type="button"
          onClick={() => onPick(r)}
          aria-pressed={selected === r.key}
          className={`w-full text-left transition hover:text-chrome-100 ${
            selected === r.key ? 'text-decision-300' : 'text-chrome-300'
          }`}
        >
          <span className="font-mono" style={{ color: impactColor(r.a.impact) }}>
            {r.a.aa}
            {r.a.n}
          </span>
          <span className="text-chrome-600"> ↔ </span>
          <span className="font-mono" style={{ color: impactColor(r.b.impact) }}>
            {r.b.aa}
            {r.b.n}
          </span>
          <span className="ml-1.5 text-chrome-500">
            {r.a.label} / {r.b.label}
          </span>
        </button>
      ),
    },
    {
      key: 'angstrom',
      header: 'Cα distance',
      align: 'right',
      sortValue: (r) => r.angstrom,
      render: (r) => <span className="font-mono text-chrome-200">{angstromLabel(r.angstrom)}</span>,
    },
    {
      key: 'bucket',
      header: 'geometric band',
      render: (r) => <span className="text-chrome-400">{r.bucket}</span>,
    },
    {
      key: 'sequenceGap',
      header: 'aa apart on the chain',
      align: 'right',
      sortValue: (r) => r.sequenceGap,
      render: (r) => <span className="font-mono text-chrome-500">{r.sequenceGap}</span>,
    },
    {
      key: 'bothRare',
      header: 'both rare',
      align: 'right',
      sortValue: (r) => r.bothRare,
      render: (r) => flag(r.bothRare),
    },
    {
      key: 'sameDomain',
      header: 'same domain',
      align: 'right',
      sortValue: (r) => r.sameDomain,
      render: (r) => flag(r.sameDomain, 'chrome'),
    },
    {
      key: 'confident',
      header: 'pLDDT ≥ 70 both ends',
      align: 'right',
      sortValue: (r) => r.confident,
      render: (r) => flag(r.confident),
    },
    {
      key: 'phase',
      header: 'phase',
      render: (r) => <span className={PHASE_CLASS[r.phase]}>{r.phase}</span>,
    },
  ];

  return (
    <div className="space-y-2">
      {compareWith && (
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={compareWith.onCompare}
            className="rounded-md border border-chrome-700 bg-chrome-900 px-2 py-1 text-[11px] text-chrome-400 transition hover:bg-chrome-800 hover:text-chrome-200"
          >
            compare {compareWith.gene} with…
          </button>
          <span className="text-[11px] text-chrome-600">
            puts {compareWith.gene} on side A of the side-by-side comparison below; pick side B
            there. A distance only means something next to the same distance on another fold.
          </span>
        </div>
      )}
      <DataTable
        rows={[...rows]}
        columns={columns}
        rowKey={(r) => r.key}
        empty="fewer than two of this gene's alleles landed on a modelled residue, so there is no pair to measure."
        pageSize={20}
      />
    </div>
  );
}
