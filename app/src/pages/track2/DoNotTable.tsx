/**
 * The do-not table — the half of Track 2 that is actually clinically useful.
 *
 * A repurposing search naturally produces a list of things to try. For a child whose
 * spindle checkpoint is already weak, the more defensible output is a list of things that
 * would make it worse: the card names those classes up front, as **anti-directions**, with a
 * mechanism-of-action pattern the ladder matches automatically. The rows below are the
 * approved drugs that matched, plus the chemotherapy the child is already on — which is set
 * aside not because it is dangerous but because giving it is not a repurposing.
 *
 * The distinction between *do not* and *caution* is load-bearing and is stated in the rows:
 * caution rows are the standard rhabdomyosarcoma regimen, and this page is a hypothesis for
 * the treating team, never advice to withhold a treatment.
 */

import type { AntiDirection, ShortlistRow, StandardOfCare } from '../../api/types';
import { Badge } from '../../components/Badge';
import { DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { C } from '../../lib/palette';
import { cx, RULE, WELL } from '../../lib/ui';
import { DO_NOT_TONE, groupDoNot } from './ladderModel';
import { T } from './Term';

export function DoNotTable({
  rows,
  antiDirections,
  standardOfCare,
  source,
}: {
  rows: ShortlistRow[];
  antiDirections: AntiDirection[];
  standardOfCare?: StandardOfCare;
  source?: string;
}) {
  const groups = groupDoNot(rows);

  return (
    <Exhibit
      title="The do-not table — what the mechanism argues against"
      legend={
        <>
          One block per verdict, worst first. <Chip color={C.broken}>red = do not</Chip> — the
          mechanism says the drug class would deepen the defect.{' '}
          <Chip color={C.decision}>yellow = caution</Chip> — a decision point for the treating team,
          not an instruction; these are also the standard chemotherapy.{' '}
          <Chip color={C.machinery}>blue = standard of care</Chip> — already being given, so
          proposing it would not be a repurposing. Every row keeps the reason it was set aside.
        </>
      }
      reading={`${rows.length} approved drugs are set aside across ${groups.length} verdicts. A search that only ever produced candidates could not be wrong; this table is where the mechanism is allowed to say no.`}
      data={rows}
      source={source}
    >
      <div className="space-y-4">
        <p className="max-w-[95ch] font-serif text-note leading-relaxed text-chrome-300">
          An{' '}
          <T
            slug="anti-direction-the-do-not-table"
            term="anti-direction"
            plain="a drug class the mechanism says would make things worse, named on the card with a pattern the ladder matches"
          />{' '}
          is the card&rsquo;s deny-list, written before the search — a rule, not a review comment.
          The reason it bites here is{' '}
          <T
            slug="mitotic-slippage"
            term="mitotic slippage"
            plain="a cell leaving mitosis without dividing properly because the checkpoint that should have held it gave way"
          />
          : a drug that arrests dividing cells depends on the very checkpoint this child is missing.
          Separately,{' '}
          <T
            slug="standard-of-care-excluded-from-a-repurposing"
            term="standard of care"
            plain="the chemotherapy already given for this tumour — a free high rung, and not a repurposing"
          />{' '}
          is excluded for a different reason entirely: it is not dangerous, it is simply already
          happening.
        </p>

        <ul className="space-y-3" data-testid="anti-directions">
          {antiDirections.map((a) => (
            <li
              key={a.id}
              data-anti={a.id}
              className={cx(WELL, 'space-y-1 border-l-2', RULE[DO_NOT_TONE[a.status] ?? 'neutral'])}
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="machinery">{a.id}</Badge>
                <Badge tone={DO_NOT_TONE[a.status] ?? 'neutral'}>{a.status}</Badge>
                <span className="text-sm text-chrome-100">{a.name}</span>
              </div>
              <p className="text-micro text-chrome-400">
                <span className="font-semibold text-chrome-300">agents: </span>
                {a.agents}
              </p>
              <p className="max-w-[95ch] text-micro leading-relaxed text-chrome-400">{a.why}</p>
            </li>
          ))}
        </ul>

        {groups.map(([verdict, group]) => (
          <div key={verdict} data-verdict={verdict} className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge tone={DO_NOT_TONE[verdict] ?? 'neutral'}>{verdict}</Badge>
              <span className="text-xs text-chrome-400">{group.length} drugs</span>
            </div>
            <DataTable<ShortlistRow>
              rows={group}
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
                  key: 'rung',
                  header: 'rung',
                  align: 'right',
                  render: (r) => (
                    <span className="tabular-nums font-mono text-xs text-chrome-400">
                      {r.rung ?? '—'}
                    </span>
                  ),
                },
                {
                  key: 'why',
                  header: 'why it is set aside',
                  render: (r) => (
                    <span className="inline-block max-w-[60ch] text-chrome-300">{r.why}</span>
                  ),
                },
                {
                  key: 'flags',
                  header: 'flags',
                  sortable: false,
                  render: (r) => (
                    <span className="flex flex-wrap gap-1">
                      {r.flags.map((f) => (
                        <Badge key={f} tone={DO_NOT_TONE[verdict] ?? 'neutral'}>
                          {f}
                        </Badge>
                      ))}
                    </span>
                  ),
                },
              ]}
            />
          </div>
        ))}

        {standardOfCare && (
          <div className={cx(WELL, 'border-l-2', RULE.machinery)}>
            <p className="max-w-[95ch] text-micro leading-relaxed text-chrome-400">
              <span className="font-semibold text-machinery-300">
                The standard of care for this tumour:{' '}
              </span>
              {standardOfCare.drugs.join(', ').toLowerCase()}. {standardOfCare.note}
            </p>
          </div>
        )}
      </div>
    </Exhibit>
  );
}
