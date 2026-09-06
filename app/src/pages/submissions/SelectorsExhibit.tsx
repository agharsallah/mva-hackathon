import type { SelectorRow, Selectors } from '../../api/types';
import { Badge } from '../../components/Badge';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Callout } from '../../components/Explainer';
import { C } from '../../lib/palette';
import { whereClause } from './iteration';

/**
 * The submitted rows, and the alleles they are made of — without a single coordinate.
 *
 * The predictions CSV holds `(chrom, pos, ref, alt)` for every row. None of that is in this
 * repository. What is committed instead is a **selector**: a `WHERE` clause over a
 * warehouse result table that must match exactly one row. `resolve_submission_spec.py`
 * turns the clauses into positions on a machine with database access, and a `--check` run
 * proved the resolution is identical to the file that was actually built.
 *
 * That is the whole reason this page can exist. A coordinate identifies the patient; a
 * clause identifies the *reasoning*, and the reasoning is what a judge needs to read.
 */

interface AlleleRow {
  name: string;
  table: string;
  clause: string;
}

export function SelectorsExhibit({ selectors, source }: { selectors: Selectors; source?: string }) {
  const alleles: AlleleRow[] = Object.entries(selectors.alleles).map(([name, spec]) => ({
    name,
    table: spec.table,
    clause: whereClause(spec),
  }));

  const rowColumns: Column<SelectorRow>[] = [
    { key: 'rank', header: 'rank', align: 'right', render: (r) => r.rank },
    {
      key: 'label',
      header: 'label',
      render: (r) => <span className="font-medium text-chrome-100">{r.label}</span>,
    },
    {
      key: 'variant',
      header: 'variant',
      render: (r) => <span className="font-mono text-machinery-300">{r.variant}</span>,
    },
    {
      key: 'partner',
      header: 'partner',
      render: (r) =>
        r.partner ? (
          <span className="font-mono text-machinery-300">{r.partner}</span>
        ) : (
          <span className="text-chrome-600">— single</span>
        ),
    },
    { key: 'epcr', header: 'epcr', align: 'right', render: (r) => r.epcr.toFixed(2) },
    {
      key: 'finding_type',
      header: 'finding',
      render: (r) => (
        <Badge tone={r.finding_type === 'primary' ? 'good' : 'machinery'}>{r.finding_type}</Badge>
      ),
    },
    {
      key: 'notes',
      header: 'notes — what the organisers receive',
      render: (r) => <span className="text-chrome-400">{r.notes}</span>,
    },
  ];

  const alleleColumns: Column<AlleleRow>[] = [
    {
      key: 'name',
      header: 'allele',
      render: (a) => <span className="font-mono text-chrome-100">{a.name}</span>,
    },
    {
      key: 'table',
      header: 'table',
      render: (a) => <span className="font-mono text-chrome-400">{a.table}</span>,
    },
    {
      key: 'clause',
      header: 'must match exactly one row where…',
      render: (a) => <span className="font-mono text-machinery-300">{a.clause}</span>,
    },
  ];

  return (
    <Exhibit
      title="Selectors — the submission, coordinate-free"
      legend={
        <>
          Top table: the rows of the predictions file, in submitted order.{' '}
          <Chip color={C.good}>green = primary</Chip> — a scored answer to the challenge question.{' '}
          <Chip color={C.machinery}>blue = secondary</Chip> — an incidental finding reported for
          clinical follow-up and, under the published scorer, unable to lower the primary
          row&rsquo;s F-max. Bottom table: one row per named allele, and the clause that picks it
          out. Every value in both tables is a gene symbol, a consequence class or a flag —{' '}
          <strong>no position appears anywhere</strong>.
        </>
      }
      reading="Read the two tables together: the top says what was claimed and how confidently, the bottom says what each name means. A reviewer can re-run the bottom half against the warehouse and get the top half back, which is the property that makes an uncommitted CSV auditable."
      data={selectors}
      source={source}
    >
      <div className="space-y-4" data-testid="selectors-body">
        <DataTable rows={selectors.rows} columns={rowColumns} rowKey={(r) => String(r.rank)} />

        <Callout tone="raw" title="Why there is no coordinate on this page">
          A genomic position is patient data: two of them identify this child in any public callset.
          The repository&rsquo;s one binding rule is that none is ever committed, and a test
          enforces it on every run. So the submission is stored as the <em>reasoning</em> — gene,
          consequence, rarity, ClinVar status — and resolved to positions only in a gitignored file
          on a machine with database access. The uploaded CSV is identified here by its sha256 and
          nothing else.
        </Callout>

        <DataTable rows={alleles} columns={alleleColumns} rowKey={(a) => a.name} />
      </div>
    </Exhibit>
  );
}
