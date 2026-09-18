/**
 * Paediatric pointers — what is on record about giving each shortlisted drug to a child.
 *
 * The patient is a child, so "has anyone given this to a child" is the first question a
 * clinician asks of any candidate. Two public facts answer part of it: whether the US label
 * carries a **section 8.4 Pediatric Use**, and how many registered studies of the drug
 * admit children in *any* indication.
 *
 * Both are pointers and neither is a permission. A section 8.4 sometimes reads "safety and
 * effectiveness have not been established" — its presence means the manufacturer had to say
 * something, not that the answer was yes. A registry study means a protocol was filed, not
 * that it finished or worked. The counts below are aggregates over ~11k registry rows; the
 * rows themselves are never rendered, because a study of a drug for an unrelated disease is
 * not evidence about this child.
 */

import { useMemo } from 'react';

import type { LadderRow, PediatricTrialRow, ShortlistRow } from '../../api/types';
import { Badge, Flag } from '../../components/Badge';
import { DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { int } from '../../lib/format';
import { C } from '../../lib/palette';
import { cx, RULE, WELL } from '../../lib/ui';
import { pediatricLabelPerDrug, pediatricStudiesPerDrug } from './ladderModel';
import { T } from './Term';

interface PointerRow {
  drug_name: string;
  direction_id: string;
  label84: boolean;
  studies: number;
  stated: string;
}

export function PediatricPointers({
  argue,
  ladder,
  pediatricTrials,
  source,
}: {
  /** The shortlist's `argue` rows — the only drugs this panel speaks about. */
  argue: ShortlistRow[];
  ladder: LadderRow[];
  pediatricTrials: PediatricTrialRow[];
  source?: string;
}) {
  const studies = useMemo(() => pediatricStudiesPerDrug(pediatricTrials), [pediatricTrials]);
  const labels = useMemo(() => pediatricLabelPerDrug(ladder), [ladder]);

  const rows: PointerRow[] = useMemo(
    () =>
      argue.map((r) => ({
        drug_name: r.drug_name,
        direction_id: r.direction_id,
        label84: labels.get(r.drug_name) ?? false,
        studies: studies.get(r.drug_name) ?? 0,
        stated: r.pediatric_evidence || 'none found',
      })),
    [argue, labels, studies],
  );

  const withLabel = rows.filter((r) => r.label84).length;
  const withStudy = rows.filter((r) => r.studies > 0).length;

  return (
    <Exhibit
      title="Paediatric pointers — what exists on record for a child"
      legend={
        <>
          One row per shortlisted drug. <Chip color={C.good}>green = present</Chip> — the label has
          a section 8.4, or registered studies admitting children exist.{' '}
          <Chip color={C.machinery}>grey/blue = none found</Chip>, which is a real answer and not a
          gap in the search. Nothing here is a{' '}
          <Chip color={C.decision}>dose, an indication or a permission</Chip>: the counts are
          pointers to read, never a licence.
        </>
      }
      reading={`${withLabel} of ${rows.length} shortlisted drugs have a section 8.4 on their US label and ${withStudy} have at least one registered study admitting children. Both are facts about paperwork that exists, not about whether the drug helps this child.`}
      data={rows}
      source={source}
    >
      <div className="space-y-4">
        <p className="max-w-[95ch] font-serif text-note leading-relaxed text-chrome-300">
          <T
            slug="pediatric-use-label-section-8-4"
            term="Pediatric Use (label section 8.4)"
            plain="the part of a US drug label that has to discuss use in children — sometimes only to say nothing is established"
          />{' '}
          is the closest thing to a machine-readable answer here; openFDA returns it as the field{' '}
          <span className="font-mono text-micro">pediatric_use</span>. The second column counts
          registered studies of the drug that admit children in <em>any</em> indication, which is
          why it can be large for a drug nobody has ever given for this mechanism.
        </p>

        <DataTable<PointerRow>
          rows={rows}
          rowKey={(r) => `${r.drug_name}:${r.direction_id}`}
          pageSize={0}
          columns={[
            {
              key: 'drug_name',
              header: 'drug',
              render: (r) => (
                <span className="font-mono text-xs text-chrome-100">{r.drug_name}</span>
              ),
            },
            {
              key: 'direction_id',
              header: 'direction',
              render: (r) => <Badge tone="machinery">{r.direction_id}</Badge>,
            },
            {
              key: 'label84',
              header: 'label section 8.4',
              render: (r) => <Flag on={r.label84} yes="yes" no="no" />,
            },
            {
              key: 'studies',
              header: 'studies admitting children',
              align: 'right',
              render: (r) => (
                <span
                  className={cx(
                    'tabular-nums font-mono text-xs',
                    r.studies > 0 ? 'text-good-300' : 'text-chrome-600',
                  )}
                >
                  {int(r.studies)}
                </span>
              ),
            },
            {
              key: 'stated',
              header: 'as the shortlist states it',
              render: (r) => (
                <span className="inline-block max-w-[40ch] text-chrome-400">{r.stated}</span>
              ),
            },
          ]}
        />

        <div className={cx(WELL, 'border-l-2', RULE.decision)} data-testid="pediatric-caveat">
          <p className="max-w-[95ch] font-serif text-note leading-relaxed text-chrome-300">
            <strong className="text-decision-300">A pointer, never a licence.</strong> A section 8.4
            and a registry study both mean somebody filed a document about children. Neither means
            the drug is indicated, dosed or safe for <em>this</em> child, and nothing on this page
            is a treatment recommendation.
          </p>
        </div>
      </div>
    </Exhibit>
  );
}
