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
import { DataTable, type Column } from '../../components/DataTable';
import { Loaded } from '../../components/QueryState';
import { Toggle } from '../../components/Controls';
import { usePanelAnnotations } from '../../api/hooks';
import type { PanelAnnotationRow } from '../../api/types';
import type { VariantRef } from '../../api/types/probebuild';
import { impactColor } from '../../lib/palette';
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
      render: (r) => <span className="text-zinc-200">{r.gene ?? '—'}</span>,
    },
    {
      key: 'consequence',
      header: 'consequence',
      render: (r) => (
        <span style={{ color: impactColor(r.impact) }} title={r.impact}>
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
            className="rounded border border-zinc-700 px-1.5 py-0.5 text-[10px] text-zinc-300 hover:bg-zinc-800 disabled:opacity-30"
          >
            + single
          </button>
          <button
            type="button"
            disabled={!canAdd}
            onClick={() => pair(r)}
            className="rounded border border-blue-800 px-1.5 py-0.5 text-[10px] text-blue-300 hover:bg-blue-950/60 disabled:opacity-30"
          >
            {pending ? '+ close pair' : '+ pair'}
          </button>
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-3 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs font-medium text-zinc-300">Candidates</div>
        <Toggle on={wide} onChange={setWide}>
          {wide ? 'every annotated panel allele' : 'rare + protein-altering only'}
        </Toggle>
      </div>

      {pending && (
        <div className="flex items-center justify-between gap-2 rounded-lg border border-amber-800/60 bg-amber-950/25 px-3 py-1.5 text-[11px] text-amber-300">
          <span>
            pairing with <span className="font-mono">{variantLabel(pending.ref)}</span> — pick the second
            allele
          </span>
          <button type="button" onClick={() => setPending(null)} className="text-amber-400 underline">
            cancel
          </button>
        </div>
      )}

      <Loaded query={annotations} height={220}>
        {(rows) => {
          const shown = wide ? rows : rows.filter((r) => r.is_rare_recessive && r.is_protein_altering);
          return (
            <DataTable
              rows={shown}
              columns={columns(shown)}
              rowKey={(r, i) => `${r.chrom}-${r.pos}-${r.ref}-${r.alt}-${i}`}
              maxHeight={260}
              filterable
              filterPlaceholder="gene, consequence…"
              empty={wide ? 'no annotated panel alleles' : 'no allele is both rare and protein-altering'}
            />
          );
        }}
      </Loaded>

      <div>
        <label className="text-[11px] font-medium text-zinc-400">
          From elsewhere
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={FREE_PLACEHOLDER}
            spellCheck={false}
            rows={5}
            className="mt-1 w-full resize-y rounded-lg border border-zinc-700 bg-zinc-950 p-2.5 font-mono text-[11px] text-zinc-100 placeholder:text-zinc-600 focus:border-blue-700 focus:outline-none"
          />
        </label>
        <div className="mt-1.5 flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={good.length === 0 || !canAdd}
            onClick={() => {
              good.forEach((p) => onAdd(p.variant1!, p.variant2 ?? null, 'typed'));
              setText('');
            }}
            className="rounded-md border border-zinc-700 px-2 py-1 text-[11px] text-zinc-300 hover:bg-zinc-800 disabled:opacity-30"
          >
            add {good.length || ''} row{good.length === 1 ? '' : 's'}
          </button>
          {bad.length > 0 && <span className="text-[11px] text-red-400">{bad.length} line(s) rejected</span>}
        </div>
        {bad.length > 0 && (
          <ul className="mt-1 space-y-0.5 text-[11px] text-red-400">
            {bad.map((p) => (
              <li key={p.line}>
                line {p.line}: {p.problem}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
