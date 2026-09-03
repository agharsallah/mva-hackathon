/**
 * The left half of the builder: which alleles can go into the payload.
 *
 * Two sources, because a probe row comes from two places. The panel table is the pipeline's
 * own shortlist — `/api/panel/annotations`, filtered by default to the rows that are both
 * rare-recessive-compatible and protein-altering, which is the set the compound-het
 * hypothesis is actually about. The free-entry box is for everything else: an allele found
 * on the Search page, quoted in a paper, or returned by an earlier probe.
 *
 * Nobody types a coordinate twice. Clicking a candidate moves the exact values the API
 * served, and the free-entry box parses text once into the same shape.
 */

import { useMemo, useState } from 'react';

import { usePanelAnnotations } from '../../api/hooks';
import type { PanelAnnotationRow } from '../../api/types';
import type { VariantRef } from '../../api/types/probebuild';
import { Card } from '../../components/Card';
import { Toggle } from '../../components/Controls';
import { type Column, DataTable } from '../../components/DataTable';
import { Loaded } from '../../components/QueryState';
import { impactTone } from '../../lib/palette';
import { TEXT } from '../../lib/ui';
import { parseLines, variantLabel } from './probePayload';

const FREE_PLACEHOLDER = `# one row per line. " + " joins a pair into ONE row:
# 15:12345 C>T + 15:12399 G>A
# a single allele on its own line fishes for a partial match:
# 7:54321 A>G`;

export interface PickerProps {
  /** Add a row. `second` null makes it a single-variant row. */
  onAdd: (first: VariantRef, second: VariantRef | null, label: string) => void;
  /** False once the payload holds ten rows — the scorer's hard cap. */
  canAdd: boolean;
}

const toRef = (r: PanelAnnotationRow): VariantRef => ({
  chrom: r.chrom,
  pos: r.pos,
  ref: r.ref,
  alt: r.alt,
});

export function CandidatePicker({ onAdd, canAdd }: PickerProps) {
  const annotations = usePanelAnnotations();
  const [wide, setWide] = useState(false);
  const [pending, setPending] = useState<{ ref: VariantRef; label: string } | null>(null);
  const [text, setText] = useState('');

  const parsed = useMemo(() => parseLines(text), [text]);
  const good = parsed.filter((p) => p.variant1);
  const bad = parsed.filter((p) => p.problem);

  /** Pairing is two clicks: the first stages an allele, the second closes the row. */
  function pair(row: PanelAnnotationRow) {
    const ref = toRef(row);
    const label = row.gene ?? 'intergenic';
    if (!pending) {
      setPending({ ref, label });
      return;
    }
    onAdd(pending.ref, ref, `${pending.label} pair`);
    setPending(null);
  }

  const columns = (rows: PanelAnnotationRow[]): Column<PanelAnnotationRow>[] => [
    {
      key: 'gene',
      header: 'gene',
      render: (r) => <span className="text-chrome-200">{r.gene ?? '—'}</span>,
    },
    {
      key: 'consequence',
      header: 'consequence',
      render: (r) => (
        <span className={TEXT[impactTone(r.impact)]} title={r.impact}>
          {r.consequence}
        </span>
      ),
    },
    {
      key: 'gnomad_af_grpmax',
      header: 'gnomAD max',
      align: 'right',
      render: (r) => (r.gnomad_af_grpmax === null ? '—' : r.gnomad_af_grpmax.toExponential(1)),
    },
    { key: 'gt', header: 'GT', render: (r) => <span className="font-mono">{r.gt}</span> },
    {
      key: 'add',
      header: `add (${rows.length})`,
      sortable: false,
      render: (r) => (
        <span className="flex gap-1">
          <button
            type="button"
            disabled={!canAdd}
            onClick={() => onAdd(toRef(r), null, r.gene ?? 'intergenic')}
            className="rounded-pill border border-line-strong px-2 py-0.5 text-micro text-chrome-300 hover:bg-chrome-800 disabled:opacity-30"
          >
            + single
          </button>
          <button
            type="button"
            disabled={!canAdd}
            onClick={() => pair(r)}
            className="rounded-pill border border-machinery-800 px-2 py-0.5 text-micro text-machinery-300 hover:bg-machinery-950/60 disabled:opacity-30"
          >
            {pending ? '+ close pair' : '+ pair'}
          </button>
        </span>
      ),
    },
  ];

  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs font-medium text-chrome-300">Candidates</div>
        <Toggle on={wide} onChange={setWide}>
          {wide ? 'every annotated panel allele' : 'rare + protein-altering only'}
        </Toggle>
      </div>

      {pending && (
        <div className="flex items-center justify-between gap-2 rounded-card border border-decision-800/60 bg-decision-950/25 px-3 py-2 text-micro text-decision-300">
          <span>
            pairing with <span className="font-mono">{variantLabel(pending.ref)}</span> — pick the
            second allele
          </span>
          <button
            type="button"
            onClick={() => setPending(null)}
            className="text-decision-400 underline"
          >
            cancel
          </button>
        </div>
      )}

      <Loaded query={annotations} height={220}>
        {(rows) => {
          const shown = wide
            ? rows
            : rows.filter((r) => r.is_rare_recessive && r.is_protein_altering);
          return (
            <DataTable
              rows={shown}
              columns={columns(shown)}
              rowKey={(r, i) => `${r.chrom}-${r.pos}-${r.ref}-${r.alt}-${i}`}
              maxHeight={260}
              filterable
              filterPlaceholder="gene, consequence…"
              empty={
                wide ? 'no annotated panel alleles' : 'no allele is both rare and protein-altering'
              }
            />
          );
        }}
      </Loaded>

      <div>
        <label className="text-micro font-medium text-chrome-400">
          From elsewhere
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={FREE_PLACEHOLDER}
            spellCheck={false}
            rows={5}
            className="mt-1 w-full resize-y rounded-card border border-line-strong bg-chrome-950 p-3 font-mono text-micro text-chrome-100 placeholder:text-chrome-600 focus:border-machinery-700 focus:outline-none"
          />
        </label>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={good.length === 0 || !canAdd}
            onClick={() => {
              good.forEach((p) => onAdd(p.variant1!, p.variant2 ?? null, 'typed'));
              setText('');
            }}
            className="rounded-control border border-line-strong px-2 py-1 text-micro text-chrome-300 hover:bg-chrome-800 disabled:opacity-30"
          >
            add {good.length || ''} row{good.length === 1 ? '' : 's'}
          </button>
          {bad.length > 0 && (
            <span className="text-micro text-broken-400">{bad.length} line(s) rejected</span>
          )}
        </div>
        {bad.length > 0 && (
          <ul className="mt-1 space-y-0.5 text-micro text-broken-400">
            {bad.map((p) => (
              <li key={p.line}>
                line {p.line}: {p.problem}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
