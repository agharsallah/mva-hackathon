/**
 * The columns of {@link StructureMetricsTable}, and nothing else.
 *
 * Split off the table because the two concerns are genuinely separate: the table owns
 * *when* 44 requests are spent and how the rows are assembled, this file owns how one row
 * reads. Every cell here renders a `null` as a **word** — `not annotated`, `not reported`,
 * `n/a — fold only` — never as a blank or a zero, for the reason the table's own doc gives.
 *
 * Nothing here names a group. The group cell shows the set's own id, tinted by the tone the
 * caller derived from the group's *rank*, and sorts by that rank.
 */

import type { ReactNode } from 'react';

import { Badge } from '../../../../components/Badge';
import type { Column } from '../../../../components/DataTable';
import { dec, int } from '../../../../lib/format';
import type { Tone } from '../../../../lib/palette';
import { angstromLabel } from '../distances';
import type { StructureRow } from './metrics';

const NA = <span className="text-chrome-700">·</span>;

/** A fraction as a percentage cell, or the word that says why there is no number. */
function share(value: number | null | undefined, absent: string): ReactNode {
  if (value === null || value === undefined) {
    return <span className="text-chrome-600">{absent}</span>;
  }
  return <span className="font-mono text-chrome-200">{dec(value * 100, 1)}</span>;
}

const SLOT_BUTTON =
  'rounded border border-chrome-700 bg-chrome-900 px-1.5 py-0.5 font-mono text-[10px] ' +
  'text-chrome-400 transition hover:bg-chrome-800 hover:text-chrome-200';

export function buildColumns(
  tones: ReadonlyMap<string, Tone>,
  onPickGene?: (gene: string) => void,
  onCompare?: (gene: string, slot: 'A' | 'B') => void,
): Column<StructureRow>[] {
  const compare: Column<StructureRow>[] = onCompare
    ? [
        {
          key: 'compare',
          header: 'compare',
          sortable: false,
          render: (row) => (
            <span className="inline-flex gap-1">
              {(['A', 'B'] as const).map((slot) => (
                <button
                  key={slot}
                  type="button"
                  onClick={() => onCompare(row.gene, slot)}
                  // The visible label is one glyph, so the accessible name has to be written
                  // out: "→B" tells a screen reader nothing about which gene it stages.
                  aria-label={`put ${row.gene} on side ${slot} of the side-by-side comparison`}
                  className={SLOT_BUTTON}
                >
                  →{slot}
                </button>
              ))}
            </span>
          ),
        },
      ]
    : [];
  return [
    {
      key: 'gene',
      header: 'gene',
      sortValue: (row) => row.gene,
      render: (row) =>
        onPickGene ? (
          <button
            type="button"
            onClick={() => onPickGene(row.gene)}
            title={`open ${row.gene} in the 3D explorer above`}
            className="font-mono text-chrome-200 transition hover:text-machinery-300"
          >
            {row.gene}
          </button>
        ) : (
          <span className="font-mono text-chrome-200">{row.gene}</span>
        ),
    },
    {
      key: 'group',
      header: 'group',
      // Sorted by the group's rank, not alphabetically by id: the set declared an order
      // and a reader sorting this column means "put the groups back the way they read".
      sortValue: (row) => row.groupOrder,
      render: (row) => (
        <Badge tone={tones.get(row.group) ?? 'neutral'} title={row.groupLabel}>
          {row.group || '—'}
        </Badge>
      ),
    },
    {
      key: 'state',
      header: 'state',
      sortValue: (row) => row.kind,
      render: (row) =>
        row.kind === 'ready' ? (
          <span className="text-good-400">ok</span>
        ) : (
          <span
            className={row.kind === 'loading' ? 'text-chrome-500' : 'text-decision-400'}
            title={row.note}
          >
            {row.kind === 'loading' ? 'loading…' : row.note}
          </span>
        ),
    },
    {
      key: 'length',
      header: 'length (aa)',
      align: 'right',
      sortValue: (row) => row.metrics?.length ?? null,
      render: (row) =>
        row.metrics ? (
          <span className="font-mono text-chrome-300">{int(row.metrics.length)}</span>
        ) : (
          NA
        ),
    },
    {
      key: 'modelled',
      header: 'modelled %',
      align: 'right',
      sortValue: (row) => row.metrics?.modelledFraction ?? null,
      render: (row) => (row.metrics ? share(row.metrics.modelledFraction, 'unknown') : NA),
    },
    {
      key: 'confident',
      header: 'pLDDT ≥ 70 %',
      align: 'right',
      sortValue: (row) => row.metrics?.confidentFraction ?? null,
      render: (row) => (row.metrics ? share(row.metrics.confidentFraction, 'not reported') : NA),
    },
    {
      key: 'helix',
      header: 'helix %',
      align: 'right',
      sortValue: (row) => row.metrics?.helixFraction ?? null,
      render: (row) => (row.metrics ? share(row.metrics.helixFraction, 'not annotated') : NA),
    },
    {
      key: 'strand',
      header: 'strand %',
      align: 'right',
      sortValue: (row) => row.metrics?.strandFraction ?? null,
      render: (row) => (row.metrics ? share(row.metrics.strandFraction, 'not annotated') : NA),
    },
    {
      key: 'domains',
      header: 'domains',
      align: 'right',
      sortValue: (row) => row.metrics?.domains.length ?? null,
      render: (row) =>
        row.metrics ? (
          <span className="font-mono text-chrome-400" title={row.metrics.domains.join(' · ')}>
            {int(row.metrics.domains.length)}
          </span>
        ) : (
          NA
        ),
    },
    {
      key: 'alleles',
      header: 'alleles placed',
      align: 'right',
      sortValue: (row) => row.metrics?.allelesPlaced ?? null,
      render: (row) =>
        row.metrics?.allelesPlaced === null || row.metrics === null ? (
          <span className="text-chrome-600">{row.metrics ? 'n/a — fold only' : '·'}</span>
        ) : (
          <span className="font-mono text-chrome-200">{int(row.metrics.allelesPlaced)}</span>
        ),
    },
    {
      key: 'closest',
      header: 'closest pair',
      align: 'right',
      sortValue: (row) => row.metrics?.closestPairAngstrom ?? null,
      render: (row) =>
        row.metrics?.closestPairAngstrom == null ? (
          <span className="text-chrome-600">{row.metrics?.inPanel ? 'under two' : NA}</span>
        ) : (
          <span
            className={
              row.metrics.closestPairConfident
                ? 'font-mono text-chrome-200'
                : 'font-mono text-chrome-500'
            }
            title={row.metrics.closestPairConfident ? '' : 'one end below pLDDT 70 — not quotable'}
          >
            {angstromLabel(row.metrics.closestPairAngstrom)}
          </span>
        ),
    },
    ...compare,
  ];
}
