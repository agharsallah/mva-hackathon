/**
 * The comparison table: one row per field, one column per selected allele.
 *
 * Split out of `PairComparator.tsx` for the repo's 400-line rule, and it splits cleanly —
 * this module is a **declaration of the fields**, not logic. Every entry is one column of
 * `/api/panel/het-pairs` rendered with the one rule that field carries (null AF is "novel",
 * null phase is "unphased", an unannotated allele's flags are unknown rather than false).
 * Nothing here computes anything about the pair; that is the verdict's job.
 */

import type { ReactNode } from 'react';

import type { PanelHetVariant } from '../../api/types';
import { C, impactTone } from '../../lib/palette';
import { TEXT } from '../../lib/ui';
import { coordinate, variantLabel } from './comparator';
import { af } from './rarity';

// --- the side-by-side table --------------------------------------------------

interface Field {
  label: string;
  hint?: string;
  render: (v: PanelHetVariant) => ReactNode;
}

const dim = (text: string) => <span className="text-chrome-400">{text}</span>;

const FIELDS: Field[] = [
  {
    label: 'consequence',
    hint: "VEP's prediction of what the allele does to the gene product, and its severity bucket.",
    render: (v) =>
      v.annotated ? (
        <span className={TEXT[impactTone(v.impact ?? '')]}>
          {variantLabel(v)} <span className="text-chrome-400">· {v.impact}</span>
        </span>
      ) : (
        dim('VEP never saw this allele — every annotation field below is unknown, not false')
      ),
  },
  {
    label: 'ClinVar',
    hint: 'Clinical-lab assertions about this variant. Absent means nobody has submitted one.',
    render: (v) =>
      v.clin_sig ? <span className="text-decision-300">{v.clin_sig}</span> : dim('no assertion'),
  },
  {
    label: 'gnomAD AF',
    hint: 'Frequency across ~800k mostly-healthy genomes. Absent from the database ⇒ "novel", never 0.',
    render: (v) =>
      !v.annotated ? (
        dim('unknown')
      ) : (
        <span className={v.gnomad_af === null ? 'text-good-300' : 'text-chrome-200'}>
          {af(v.gnomad_af)}
        </span>
      ),
  },
  {
    label: 'gnomAD grpmax',
    hint: 'Highest AF in any single population group — the number that catches "rare overall, common in one ancestry".',
    render: (v) => (!v.annotated ? dim('unknown') : <span>{af(v.gnomad_af_grpmax)}</span>),
  },
  {
    label: 'recessive filters',
    hint: 'The two server-side booleans: rare enough for a recessive model, and able to change the protein.',
    render: (v) => (
      <span className="flex flex-wrap gap-2">
        <Flag on={v.is_rare_recessive} yes="rare" no="too common" />
        <Flag on={v.is_protein_altering} yes="protein-altering" no="not protein-altering" />
      </span>
    ),
  },
  {
    label: 'rsID',
    render: (v) => (v.rsid ? <span className="font-mono">{v.rsid}</span> : dim('none')),
  },
  {
    label: 'position',
    hint: 'The patient coordinate. Shown here, never in the primary label, and never committed to the repo.',
    render: (v) => <span className="font-mono text-chrome-400">{coordinate(v)}</span>,
  },
  {
    label: 'GT',
    hint: 'Genotype call. 0/1 = one ALT copy; 1/2 = two different ALT alleles, one per copy.',
    render: (v) => (
      <span className="font-mono">
        {v.gt}
        {v.gt === '1/2' && <span className="text-chrome-400"> · allele {v.allele_ix}</span>}
      </span>
    ),
  },
  {
    label: 'FILTER',
    hint: 'This endpoint serves heterozygous PASS alleles only, so FILTER is PASS by construction — it is not read off the row.',
    render: () => (
      <span>
        <span className="font-mono text-good-300">PASS</span> {dim('(by construction)')}
      </span>
    ),
  },
  {
    label: 'QUAL',
    hint: "The caller's phred-scaled confidence that a variant exists at this site.",
    render: (v) =>
      v.qual === null ? dim('—') : <span className="font-mono">{v.qual.toFixed(0)}</span>,
  },
  {
    label: 'DP',
    hint: 'Sequencing depth at the site: how many reads the call rests on.',
    render: (v) => (v.dp === null ? dim('—') : <span className="font-mono">{v.dp}×</span>),
  },
  {
    label: 'VAF',
    hint: 'Share of reads carrying the ALT. A clean heterozygote sits near 0.5.',
    render: (v) => <Vaf vaf={v.vaf} />,
  },
  {
    label: 'phase (PGT / PID)',
    hint: "Sentieon's read-backed phasing, raw. PID names the island the read pairs cover; PGT which copy inside it.",
    render: (v) =>
      v.pgt || v.pid ? (
        <span className="font-mono">
          {v.pgt ?? '—'} <span className="text-chrome-400">/ {v.pid ?? '—'}</span>
        </span>
      ) : (
        dim('unphased — no read pair spanned this allele and a neighbour')
      ),
  },
];

export function Flag({ on, yes, no }: { on: boolean | null; yes: string; no: string }) {
  if (on === null)
    return (
      <span className="rounded-pill bg-chrome-800 px-2 py-0.5 text-micro text-chrome-400">
        unknown
      </span>
    );
  return (
    <span
      className={`rounded-pill px-2 py-0.5 text-micro ${
        on ? 'bg-good-950/60 text-good-300' : 'bg-chrome-800 text-chrome-400'
      }`}
    >
      {on ? yes : no}
    </span>
  );
}

/** The 0.5 line is the whole point of the cell, so it is drawn rather than described. */
function Vaf({ vaf }: { vaf: number | null }) {
  if (vaf === null) return dim('— (1/2 record: no single ALT fraction is defined)');
  const clean = Math.abs(vaf - 0.5) <= 0.15;
  return (
    <span className="inline-block">
      <span className="font-mono" style={{ color: clean ? C.good : C.decision }}>
        {vaf.toFixed(3)}
      </span>
      <span className="relative mt-1 block h-1.5 w-[160px] rounded-sm bg-chrome-800">
        <span className="absolute inset-y-[-2px] left-1/2 w-px bg-chrome-500" />
        <span
          className="absolute inset-y-[-3px] w-[3px] rounded-sm"
          style={{
            left: `${Math.min(100, Math.max(0, vaf * 100))}%`,
            background: clean ? C.good : C.decision,
          }}
        />
      </span>
      <span className="mt-0.5 block text-micro text-chrome-600">
        0 — 0.5 (one of two copies) — 1
      </span>
    </span>
  );
}

export function Comparison({ a, b }: { a: PanelHetVariant; b: PanelHetVariant }) {
  return (
    <div className="overflow-x-auto rounded-card border border-line">
      <table className="w-full border-collapse text-xs">
        <thead className="bg-chrome-900 text-chrome-400">
          <tr>
            <th className="w-40 border-b border-line px-2 py-2 text-left font-medium">field</th>
            <th className="border-b border-line px-2 py-2 text-left font-medium text-machinery-300">
              A
            </th>
            <th className="border-b border-line px-2 py-2 text-left font-medium text-raw-300">B</th>
          </tr>
        </thead>
        <tbody>
          {FIELDS.map((f) => (
            <tr key={f.label} className="odd:bg-chrome-900/30">
              <td
                className="border-b border-line-soft px-2 py-2 align-top text-chrome-400"
                title={f.hint}
              >
                {f.label}
              </td>
              <td className="border-b border-line-soft px-2 py-2 align-top text-chrome-300">
                {f.render(a)}
              </td>
              <td className="border-b border-line-soft px-2 py-2 align-top text-chrome-300">
                {f.render(b)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
