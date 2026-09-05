/**
 * The mechanism card, in the order the organisers' methods form asks for it (question 15):
 * loss- or gain-of-function first, then the pathway, then what happens downstream, then the
 * alleles the argument rests on, then the citations.
 *
 * The allele table names **classes** — a consequence and an exon count — and never a
 * position. That is the rule that makes the whole Track 2 folder committable, and it is
 * enforced by the payload rather than by this component: the card has no position to render.
 */

import type { CardAllele, MechanismCard } from '../../api/types';
import { Badge } from '../../components/Badge';
import { DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { C } from '../../lib/palette';
import { cx, WELL } from '../../lib/ui';
import { T } from './Term';

const pubmed = (pmid: string) => `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`;

export function MechanismCardExhibit({ card, source }: { card: MechanismCard; source?: string }) {
  const m = card.mechanism;
  return (
    <Exhibit
      title="Mechanism card — the hand-off from Track 1"
      legend={
        <>
          <Chip color={C.broken}>red = what is broken</Chip> — the loss of function and the
          consequence chain it sets off. <Chip color={C.machinery}>blue = machinery</Chip> — the
          pathway the protein works in. <Chip color={C.decision}>yellow = a decision point</Chip> —
          the line that rules a whole class of drugs out: fully inhibiting this protein is lethal,
          so &ldquo;more inhibition&rdquo; is not a direction. Allele rows name a{' '}
          <strong>consequence class</strong>, never a position.
        </>
      }
      reading={`${m.class} The card is version ${card.version}; it is revised, never edited, so every drug table below can be traced to the exact version of the argument that produced it.`}
      data={card}
      source={source}
    >
      <div className="space-y-3">
        <div className="grid gap-3 lg:grid-cols-3">
          <Field
            tone="broken"
            label="1 · Loss or gain of function"
            value={m.class}
            note={m.status}
          />
          <Field tone="machinery" label="2 · Pathway" value={m.pathway} note={m.immediate_effect} />
          <Field
            tone="decision"
            label="Why not simply inhibit it"
            value={m.complete_loss}
            note={`${card.case.disease} · ${card.gene.protein}`}
          />
        </div>

        <div className={cx(WELL, 'space-y-2')}>
          <h4 className="text-xs font-semibold text-chrome-200">3 · Downstream consequences</h4>
          <ol className="space-y-1">
            {m.downstream.map((d, i) => (
              <li key={d} className="grid grid-cols-[1.5rem_1fr] gap-x-2 text-sm text-chrome-300">
                <span className="font-mono text-micro text-broken-400">{i + 1} →</span>
                <span className="leading-relaxed">{d}</span>
              </li>
            ))}
          </ol>
          <p className="text-micro text-chrome-500">
            Read as a chain: each line is caused by the one above it. The last two are what the
            child presents with, which is how the chain is checked against the clinical document.
          </p>
        </div>

        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-chrome-200">
            4 · The two alleles, by class only
          </h4>
          <DataTable<CardAllele>
            rows={card.alleles}
            rowKey={(r) => r.label}
            columns={[
              { key: 'label', header: 'allele', render: (r) => <Badge>{r.label}</Badge> },
              {
                key: 'consequence',
                header: 'consequence',
                render: (r) => <span className="font-mono text-xs">{r.consequence}</span>,
              },
              { key: 'exon', header: 'exon', render: (r) => r.exon },
              {
                key: 'clinvar',
                header: 'ClinVar',
                render: (r) =>
                  r.clinvar ? (
                    <a
                      className="font-mono text-xs text-machinery-400 underline underline-offset-2"
                      href={`https://www.ncbi.nlm.nih.gov/clinvar/variation/${r.clinvar.replace(/^VCV0*/, '')}/`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {r.clinvar}
                    </a>
                  ) : (
                    <span className="text-chrome-600">no record</span>
                  ),
              },
              { key: 'classification', header: 'classification', render: (r) => r.classification },
              {
                key: 'reading',
                header: 'what it means for the protein',
                render: (r) => <span className="text-chrome-400">{r.reading}</span>,
              },
            ]}
          />
          <p className="max-w-[95ch] text-micro leading-relaxed text-chrome-500">
            The two together are a{' '}
            <T
              slug="compound-heterozygous-comp-het"
              term="compound heterozygote"
              plain="two different broken copies of one gene, one inherited from each parent"
            />
            : a dead copy plus a partly working one. That combination is the reason a{' '}
            <T
              slug="drug-repurposing"
              term="repurposing"
              plain="using an already-approved drug for a disease it was not approved for"
            />{' '}
            argument exists at all — there is still some protein left to help.
          </p>
        </div>

        <div className={cx(WELL, 'space-y-2')}>
          <h4 className="text-xs font-semibold text-chrome-200">
            5 · What this rests on, in the literature
          </h4>
          <ul className="space-y-1.5">
            {m.literature.map((lit) => (
              <li key={lit.pmid} className="flex gap-2 text-sm">
                <a
                  className="shrink-0 font-mono text-xs text-machinery-400 underline underline-offset-2 hover:text-machinery-200"
                  href={pubmed(lit.pmid)}
                  target="_blank"
                  rel="noreferrer"
                >
                  PMID:{lit.pmid}
                </a>
                <span className="text-chrome-400">{lit.role}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Exhibit>
  );
}

function Field({
  label,
  value,
  note,
  tone,
}: {
  label: string;
  value: string;
  note: string;
  tone: 'broken' | 'machinery' | 'decision';
}) {
  const rule = {
    broken: 'border-l-broken-600',
    machinery: 'border-l-machinery-600',
    decision: 'border-l-decision-500',
  }[tone];
  return (
    <div className={cx('rounded-card border-l-2 bg-panel p-3', rule)}>
      <div className="text-xs text-chrome-500">{label}</div>
      <p className="mt-1 text-sm leading-relaxed text-chrome-100">{value}</p>
      <p className="mt-1.5 text-micro leading-relaxed text-chrome-500">{note}</p>
    </div>
  );
}
