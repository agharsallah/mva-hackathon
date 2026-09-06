/**
 * The target set: the genes a drug could act on, and how each one got in.
 *
 * Two ways in, and the difference matters. A **seed** target was named by the mechanism
 * card — a human decision, citable. A **pathway** target was added mechanically: Reactome
 * was asked which pathways contain the card's protein, the pathway names were matched
 * against a stated pattern, and the participants of the matching pathways came in. So the
 * seed count is the size of the argument, and the pathway count is the size of the search.
 */

import type { PathwayRow, Track2Summary } from '../../api/types';
import { Badge } from '../../components/Badge';
import { DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { StatTile } from '../../components/StatTile';
import { int } from '../../lib/format';
import { C } from '../../lib/palette';
import { T } from './Term';

export function TargetSet({
  pathways,
  summary,
  source,
}: {
  pathways: PathwayRow[];
  summary: Track2Summary;
  source?: string;
}) {
  const t = summary.targets;
  const p = summary.pathways;

  return (
    <Exhibit
      title="Target set — seed genes, then the pathway expansion"
      legend={
        <>
          <Chip color={C.raw}>purple = the raw input</Chip> — seed targets, named by the mechanism
          card itself. <Chip color={C.machinery}>blue = neutral machinery</Chip> — targets the
          Reactome expansion added. In the pathway table, <Badge tone="good">matched</Badge> means
          the pathway&rsquo;s name matched the expansion pattern, so its participants entered the
          set; <Badge>skipped</Badge> means it did not, and contributed nobody. The participant
          count is what each pathway actually contributed.
        </>
      }
      reading={`${int(t.seed)} seed genes became ${int(t.total)} targets: ${p.matched} of the ${p.walked} Reactome pathways containing the protein matched /${p.pattern}/ and brought in ${int(t.pathway)} more. The pattern is a parameter of the expansion, not a constant — a different mechanism card passes its own, which is what makes this step reusable on another case.`}
      data={{ targets: t, pathways: p, rows: pathways }}
      source={source}
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatTile
            label="seed targets"
            tone="raw"
            value={int(t.seed)}
            sub="named by the mechanism card"
          />
          <StatTile
            label="pathway targets"
            tone="machinery"
            value={int(t.pathway)}
            sub={`participants of the ${p.matched} matching pathways`}
          />
          <StatTile
            label="targets in total"
            value={int(t.total)}
            sub="the search space for drugs"
          />
          <StatTile
            label="pathways walked"
            tone="decision"
            value={`${p.matched} / ${p.walked}`}
            sub={`matched /${p.pattern}/`}
          />
        </div>

        <p className="max-w-[95ch] text-micro leading-relaxed text-chrome-400">
          The expansion is a{' '}
          <T
            slug="pathway-expansion-reactome"
            term="pathway expansion"
            plain="asking a pathway database which other proteins work alongside this one, and treating them as targets too"
          />
          . It is what makes a drug list possible at all here: no approved drug acts on the broken
          protein itself, so every candidate has to come from a neighbour.
        </p>

        <DataTable<PathwayRow>
          rows={pathways}
          rowKey={(r) => r.st_id}
          columns={[
            {
              key: 'st_id',
              header: 'Reactome id',
              render: (r) => (
                <a
                  className="font-mono text-xs text-machinery-300 underline underline-offset-2 hover:text-machinery-200"
                  href={`https://reactome.org/content/detail/${r.st_id}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {r.st_id}
                </a>
              ),
            },
            { key: 'display_name', header: 'pathway', render: (r) => r.display_name },
            {
              key: 'matched',
              header: 'matched the pattern',
              sortValue: (r) => r.matched,
              render: (r) =>
                r.matched ? <Badge tone="good">matched</Badge> : <Badge>skipped</Badge>,
            },
            {
              key: 'n_participants',
              header: 'genes contributed',
              align: 'right',
              render: (r) => (
                <span className="tabular-nums font-mono text-xs">{int(r.n_participants)}</span>
              ),
            },
          ]}
        />
      </div>
    </Exhibit>
  );
}
