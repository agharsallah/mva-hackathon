/**
 * The pair comparator — two variants of one gene, side by side, as a candidate pair.
 *
 * The pair matrix on the Panel page draws the whole grid and answers "where is phase
 * resolved?". It cannot answer the next question, which is the one a submission row is
 * actually built from: **is this specific pair worth spending a rank on?** That takes the
 * two alleles' evidence next to each other — rarity, protein consequence, ClinVar, and the
 * read evidence under all of it — plus the phase verdict for the cell they form.
 *
 * Nothing here is derived in the browser. Every field is a column of
 * `/api/panel/het-pairs?gene=`, and the phase verdict is a lookup in that payload's own
 * `pairs` list (see `comparator.ts`). The one thing this exhibit adds is the hand-off: the
 * pair leaves as a URL the probe builder stages into a row, so no coordinate is ever retyped.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import type { Origin } from '../../api/client';
import { useHetPairs, usePanelGenes } from '../../api/hooks';
import type { PanelHetPairs, PanelHetVariant } from '../../api/types';
import { Select } from '../../components/Controls';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Callout } from '../../components/Explainer';
import { Loaded } from '../../components/QueryState';
import { C } from '../../lib/palette';
import { known, useUrlState } from '../../lib/urlstate';
import { DEFAULT_GENE } from '../panel/LocusExplorer';
import { useProbeBuild } from '../probes/useProbeBuild';
import {
  defaultSelection,
  optionLabel,
  pairCheck,
  pairVerdict,
  pickIndex,
  probesPairHref,
  toRef,
} from './comparator';
import { Comparison, Flag } from './PairFields';

/**
 * The gene selection is keyed `cmp.gene`, distinct from the Panel page's `gene`, because
 * the two pages are read independently and one link should not silently re-aim the other.
 */
export function PairComparator() {
  const genes = usePanelGenes();
  const [param, setGene] = useUrlState('cmp.gene', DEFAULT_GENE);
  const [, setA] = useUrlState('cmp.a', '');
  const [, setB] = useUrlState('cmp.b', '');

  const options = (genes.data?.data ?? []).map((g) => ({ value: g.gene, label: g.gene }));
  const gene = known(
    param,
    options.map((o) => o.value),
    DEFAULT_GENE,
  );
  const q = useHetPairs(gene);

  return (
    <Exhibit
      title="Pair comparator — two alleles of one gene, held against each other"
      controls={
        <Select
          value={gene}
          options={options.length > 0 ? options : [{ value: DEFAULT_GENE, label: DEFAULT_GENE }]}
          onChange={(next) => {
            // Selection indices address *this* gene's variant list, so they cannot survive
            // a gene change. Cleared in the same tick; `useUrlState` composes same-tick writes.
            setGene(next);
            setA('');
            setB('');
          }}
          label="gene"
        />
      }
      legend={
        <>
          Two columns, one per selected allele, over the same fields. The colour of a field is what
          it means, not what it is: <Chip color={C.broken}>red = HIGH impact</Chip> (the variant
          truncates the protein), <Chip color={C.decision}>yellow = MODERATE</Chip> (it swaps an
          amino acid), <Chip color={C.machinery}>blue = LOW / MODIFIER</Chip> (silent or
          non-coding), and <Chip color={C.absent}>grey = not measured</Chip>, which is never the
          same as zero — an allele absent from gnomAD reads <span className="font-mono">novel</span>
          , the rarest thing a variant can be. The verdict bar at the bottom is the pair, not the
          alleles: <Chip color={C.good}>green = resolved trans</Chip> (opposite copies — a proven
          compound heterozygote), <Chip color={C.broken}>red = resolved cis</Chip> (same copy, so
          one intact copy remains and the pair is excluded),{' '}
          <Chip color={C.decision}>yellow = auto-trans</Chip> (the two ALT alleles of one{' '}
          <span className="font-mono">1/2</span> record, proven by genotype alone), and{' '}
          <Chip color={C.absent}>grey = unknown</Chip>, which is the honest and by far the most
          common state. The VAF cell draws the 0.5 line, where one of two chromosome copies puts a
          heterozygous allele.
        </>
      }
      reading="A pair earns a submission rank when both halves are rare and both are protein-altering, and phase has not excluded it. Cis is the only verdict that kills a pair outright; unknown does not, and grey cells are where the answer most likely is, because short-read phasing simply never reached across them."
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={520}>
        {(payload, meta) => <Card payload={payload} origin={meta.origin} />}
      </Loaded>
    </Exhibit>
  );
}

function Card({ payload, origin }: { payload: PanelHetPairs; origin: Origin }) {
  const { gene, variants, pairs } = payload;
  const [rawA, setA] = useUrlState('cmp.a', '');
  const [rawB, setB] = useUrlState('cmp.b', '');

  const [fallbackA, fallbackB] = useMemo(() => defaultSelection(variants), [variants]);
  const i = pickIndex(rawA, variants.length, fallbackA);
  const j = pickIndex(rawB, variants.length, fallbackB);

  if (variants.length < 2) {
    return (
      <p className="p-8 text-center text-sm text-zinc-500">
        {gene} has {variants.length === 0 ? 'no' : 'one'} heterozygous PASS allele, and a pair needs
        two.
      </p>
    );
  }

  const a = variants[i];
  const b = variants[j];
  const distinct = i !== j;
  const verdict = pairVerdict(pairs, i, j);
  const check = pairCheck(a, b, verdict, distinct);
  const options = variants.map((v, k) => ({ value: String(k), label: optionLabel(v, k) }));

  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-2">
        <Picker
          label="variant A"
          value={String(i)}
          options={options}
          onChange={setA}
          accent="text-blue-300"
        />
        <Picker
          label="variant B"
          value={String(j)}
          options={options}
          onChange={setB}
          accent="text-purple-300"
        />
      </div>

      {!distinct && (
        <p className="rounded-lg border border-amber-800/60 bg-amber-950/25 p-2.5 text-[11px] text-amber-300">
          Both columns point at the same allele. A pair is two different alleles — the scorer holds
          a row as a <em>set</em>, so a row whose two halves are identical is read as a
          single-variant row.
        </p>
      )}

      <Comparison a={a} b={b} />
      <VerdictBar verdict={verdict} check={check} />
      <HandOff gene={gene} a={a} b={b} check={check} origin={origin} phase={verdict.phase} />
      <Worth />
    </div>
  );
}

function Picker({
  label,
  value,
  options,
  onChange,
  accent,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
  accent: string;
}) {
  return (
    <label className="flex flex-col gap-1 rounded-lg border border-zinc-800 bg-zinc-950/40 p-2.5">
      <span className={`text-[11px] font-semibold uppercase tracking-wider ${accent}`}>
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-[11px] text-zinc-200"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

// --- the verdict and the hand-off --------------------------------------------

function VerdictBar({
  verdict,
  check,
}: {
  verdict: ReturnType<typeof pairVerdict>;
  check: ReturnType<typeof pairCheck>;
}) {
  return (
    <div
      className="rounded-lg border p-3"
      style={{ borderColor: `${verdict.color}66`, background: `${verdict.color}12` }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className="inline-block h-2.5 w-2.5 rounded-sm"
          style={{ background: verdict.color }}
        />
        <span
          className="text-xs font-semibold uppercase tracking-wider"
          style={{ color: verdict.color }}
        >
          {verdict.headline}
        </span>
      </div>
      <p className="mt-1.5 text-xs leading-relaxed text-zinc-300">{verdict.meaning}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <Flag on={check.bothRare} yes="both rare" no="one half is too common" />
        <Flag
          on={check.bothProteinAltering}
          yes="both protein-altering"
          no="one half cannot change the protein"
        />
        <Flag on={check.notCis} yes="not excluded by phase" no="excluded by phase" />
        <Flag on={check.distinct} yes="two distinct alleles" no="the same allele twice" />
      </div>
    </div>
  );
}

const FIXTURE_NOTE =
  'The API is unreachable, so this card is drawn from committed fixture rows with synthetic positions. ' +
  'Staging those into a submission would put invented coordinates in a file, so both hand-off buttons ' +
  'are disabled. Start the API (uv run mva-viz-api) and they come back.';

function HandOff({
  gene,
  a,
  b,
  check,
  origin,
  phase,
}: {
  gene: string;
  a: PanelHetVariant;
  b: PanelHetVariant;
  check: ReturnType<typeof pairCheck>;
  origin: Origin;
  phase: string;
}) {
  const navigate = useNavigate();
  const { result, error, building, build, clear } = useProbeBuild();
  const [copied, setCopied] = useState(false);
  const wantCopy = useRef(false);
  const live = origin === 'api' && check.distinct;

  // A changed selection invalidates the last built row — a stale CSV under new alleles is a lie.
  useEffect(() => {
    clear();
    setCopied(false);
  }, [a, b, clear]);

  useEffect(() => {
    if (!result || !wantCopy.current) return;
    wantCopy.current = false;
    const row = result.csv.trim().split('\n')[1];
    // The row is rendered below whether or not the clipboard is available (it is denied in
    // a headless browser and on an insecure origin), so a refusal is not an error state.
    if (result.valid && row) {
      navigator.clipboard.writeText(row).then(
        () => setCopied(true),
        () => setCopied(false),
      );
    }
  }, [result]);

  const errors = result?.problems.filter((p) => p.severity === 'error') ?? [];
  const warnings = result?.problems.filter((p) => p.severity === 'warning') ?? [];
  const dataRow = result?.valid ? (result.csv.trim().split('\n')[1] ?? '') : '';

  return (
    <div className="space-y-2 rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={!live}
          onClick={() => navigate(probesPairHref(toRef(a), toRef(b)))}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white disabled:cursor-not-allowed disabled:bg-zinc-800 disabled:text-zinc-500"
        >
          add pair to probe builder
        </button>
        <button
          type="button"
          disabled={!live || building}
          onClick={() => {
            wantCopy.current = true;
            setCopied(false);
            build({
              rows: [
                {
                  variant_1: toRef(a),
                  variant_2: toRef(b),
                  epcr: 0.99,
                  finding_type: 'primary',
                  notes: `${gene} compound-het candidate, phase ${phase}`,
                },
              ],
            });
          }}
          className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {building ? 'validating…' : copied ? 'copied the row' : 'copy CSV row'}
        </button>
        <span className="text-[11px] text-zinc-500">
          building spends nothing — the row is rendered by{' '}
          <span className="font-mono">mva.pipeline.submission</span> at epcr 0.99, never assembled
          here
        </span>
      </div>

      {!live && (
        <p className="rounded-md border border-amber-800/60 bg-amber-950/25 p-2.5 text-[11px] leading-relaxed text-amber-300">
          {origin === 'fixture'
            ? FIXTURE_NOTE
            : 'Pick two different alleles before handing a pair over.'}
        </p>
      )}

      {error && (
        <p className="rounded-md border border-red-900/60 bg-red-950/30 p-2.5 text-[11px] leading-relaxed text-red-300">
          The API did not answer: <span className="font-mono">{error.message}</span>. Nothing was
          validated, and no CSV is shown — a hand-built row is exactly the mistake this button
          exists to prevent.
        </p>
      )}

      {errors.length > 0 && (
        <ul className="rounded-md border border-red-900/60 bg-red-950/25 p-2.5 text-[11px] text-red-300">
          {errors.map((p) => (
            <li key={p.message}>{p.message}</li>
          ))}
        </ul>
      )}
      {warnings.length > 0 && (
        <ul className="rounded-md border border-amber-800/60 bg-amber-950/25 p-2.5 text-[11px] text-amber-300">
          {warnings.map((p) => (
            <li key={p.message}>{p.message}</li>
          ))}
        </ul>
      )}
      {dataRow && (
        <pre className="overflow-x-auto rounded-md border border-zinc-800 bg-zinc-950 p-2 font-mono text-[11px] text-zinc-200">
          {dataRow}
        </pre>
      )}
    </div>
  );
}

function Worth() {
  return (
    <Callout tone="neutral" title="What makes a pair worth probing">
      Three conditions, and they are cheap to check here because both halves are on screen at once.{' '}
      <strong>Both rare</strong> — a recessive cause needs two rare alleles, so one common half
      sinks the pair however damaging the other looks. <strong>Both protein-altering</strong> — a
      silent or non-coding half breaks nothing, so the second copy of the gene still works.{' '}
      <strong>Trans or unknown, never cis</strong> — cis puts both hits on one copy and leaves an
      intact one, which is the only verdict that excludes a pair outright. On the cost: building a
      row and copying it spends nothing at all, and you can do it as many times as you like.
      Uploading a file to the challenge Space spends <strong>1 of 18</strong> submissions, and that
      is the only irreversible action in the whole workflow.
    </Callout>
  );
}
