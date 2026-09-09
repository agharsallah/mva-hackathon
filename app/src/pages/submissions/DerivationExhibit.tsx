import type { AlleleFacts, Selectors } from '../../api/types';
import { Badge } from '../../components/Badge';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Callout } from '../../components/Explainer';
import { C } from '../../lib/palette';
import { fmtEpcr } from './iteration';

/**
 * Where every number in the predictions file came from — and the proof none was typed.
 *
 * `derivation.json` is written beside the selectors by `resolve_submission_spec.py`. It holds
 * the facts each note quotes (read from the selector's own result table), each allele's
 * rarity × severity score, the epcr ladder anchored on the register's confidence for the
 * hypothesis the rank-1 row tests, and the arithmetic line by line. An iteration whose rows
 * were still typed by hand has no derivation, and this exhibit says so instead of hiding.
 */

export function DerivationExhibit({
  selectors,
  source,
}: {
  selectors: Selectors;
  source?: string;
}) {
  const derivation = selectors.derivation;
  if (!derivation) {
    return (
      <Callout tone="decision" title="This iteration typed its epcr and notes by hand">
        Later iterations derive both from the warehouse and the research register; this one predates
        that rule. The selectors still say why each row is there.
      </Callout>
    );
  }

  const facts = Object.values(derivation.alleles);
  const factColumns: Column<AlleleFacts>[] = [
    {
      key: 'name',
      header: 'allele',
      render: (f) => <span className="font-mono text-chrome-100">{f.name}</span>,
    },
    { key: 'gene', header: 'gene', render: (f) => f.gene ?? '—' },
    {
      key: 'consequence',
      header: 'consequence',
      render: (f) => (
        <span className="font-mono text-machinery-300">{(f.consequence ?? '—').split(',')[0]}</span>
      ),
    },
    {
      key: 'call',
      header: 'call',
      render: (f) =>
        [f.zygosity, f.filter, f.dp == null ? null : `DP ${f.dp}`].filter(Boolean).join(' ') || '—',
    },
    {
      key: 'gnomad',
      header: 'gnomAD',
      align: 'right',
      render: (f) => (f.gnomad_af == null ? 'absent' : f.gnomad_af.toPrecision(3)),
    },
    {
      key: 'clinvar',
      header: 'ClinVar',
      render: (f) =>
        f.clin_sig ? (
          <Badge tone={f.is_clinvar_plp ? 'broken' : 'machinery'}>{f.clin_sig}</Badge>
        ) : (
          <span className="text-chrome-600">not listed</span>
        ),
    },
    {
      key: 'score',
      header: 'rarity × severity',
      align: 'right',
      render: (f) => f.score.toFixed(3),
    },
  ];

  const anchor = derivation.anchor;
  return (
    <Exhibit
      title="Derivation — no number in the file was typed"
      legend={
        <>
          Top: what the result table says about each allele, and the ranker&rsquo;s single-allele
          score. <Chip color={C.broken}>red badge = ClinVar pathogenic / likely pathogenic</Chip>{' '}
          <Chip color={C.machinery}>blue = any other ClinVar record</Chip>. Bottom: the arithmetic,
          one line per derived value — the anchor, each pair score, each share, each prior.
        </>
      }
      reading={`The rank-1 row (${anchor.row ?? '?'}) takes the register's suggested confidence for ${
        anchor.hypothesis ?? '?'
      } — ${anchor.confidence == null ? '?' : fmtEpcr(anchor.confidence)}, a transparent triage heuristic and not a calibrated posterior. Every other primary row is a share of what is left, in proportion to its pair score; secondary rows sit below the lowest primary. The tool refuses a typed epcr, a typed note, a number inside a rationale, and an anchor the ranker would not itself put first.`}
      data={derivation}
      source={source}
    >
      <div className="space-y-4" data-testid="derivation-body">
        <DataTable rows={facts} columns={factColumns} rowKey={(f) => f.name} />
        <pre className="overflow-x-auto rounded border border-chrome-800 bg-chrome-950 p-3 text-xs text-chrome-300">
          {derivation.arithmetic.join('\n')}
        </pre>
      </div>
    </Exhibit>
  );
}
