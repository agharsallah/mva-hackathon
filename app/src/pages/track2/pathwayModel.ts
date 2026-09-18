/**
 * The mechanism as a chain, as data.
 *
 * The card states the chain in prose (`mechanism.immediate_effect` + `mechanism.downstream`)
 * and the directions in a list. Neither says *where on the chain* each direction attaches,
 * which is the one thing a reader needs to judge a repurposing argument — so the spine and
 * its branches are derived here, and `PathwayDiagram` only draws them.
 */

import type { RepurposingDirection, ShortlistRow, Track2 } from '../../api/types';
import type { Tone } from '../../lib/palette';
import { titleCase } from './hero/heroModel';

export interface Branch {
  id: string;
  tone: Tone;
  /** A direction with no approved agent is drawn dotted: an angle that exists, with nothing on it. */
  dotted?: boolean;
  title: string;
  detail: string;
  drugs: string[];
}

export interface Stage {
  id: string;
  tone: Tone;
  title: string;
  detail: string;
  branches: Branch[];
}

/** The argued drug names for one direction, title-cased, in shortlist order. */
function drugsFor(rows: ShortlistRow[], directionId: string): string[] {
  return rows
    .filter((r) => r.verdict === 'argue' && r.direction_id === directionId)
    .map((r) => titleCase(r.drug_name));
}

function directionTitle(
  directions: RepurposingDirection[],
  id: string,
  gloss: string,
): { title: string; detail: string } {
  const found = directions.find((d) => d.id === id);
  return { title: `${id} — ${gloss}`, detail: found?.name ?? id };
}

export function stages(data: Track2): Stage[] {
  const rows = data.shortlist ?? [];
  const directions = data.card.repurposing_directions;
  const anti = data.card.anti_directions ?? [];
  const unmeasured = (data.card.measured_facts ?? []).some((f) =>
    /^UNMEASURED\b/i.test(f.value.trim()),
  );
  const d1 = directionTitle(directions, 'D1', 'reinforce the checkpoint');
  const a2 = anti.find((a) => a.id === 'A2');

  return [
    {
      id: 'alleles',
      tone: 'raw',
      title: `${data.card.gene.symbol}: one null allele + one hypomorph`,
      detail: data.card.alleles.map((a) => `${a.label} (${a.consequence})`).join(' + '),
      branches: [],
    },
    {
      id: 'protein',
      tone: 'machinery',
      title: `less ${data.card.gene.protein.split(' (')[0]}, leaky checkpoint`,
      detail: data.card.mechanism.immediate_effect,
      branches: [
        {
          id: 'D3',
          tone: 'decision',
          ...directionTitle(directions, 'D3', 'stabilise the remaining BubR1'),
          drugs: drugsFor(rows, 'D3'),
        },
        {
          id: 'D1',
          tone: 'broken',
          dotted: true,
          title: `${d1.title}: no approved drug`,
          detail:
            'the direction the mechanism points at first, and the one nothing on the market reaches — checkpoint agonists do not exist',
          drugs: [],
        },
        {
          id: 'A2',
          tone: 'broken',
          dotted: true,
          title: 'spindle poisons need the checkpoint: caution',
          detail: a2?.agents ?? 'vinca alkaloids and taxanes',
          drugs: [],
        },
      ],
    },
    {
      id: 'missegregation',
      tone: 'broken',
      title: 'chromosomes separate too early',
      detail: data.card.mechanism.downstream[0] ?? '',
      branches: [],
    },
    {
      id: 'aneuploidy',
      tone: 'broken',
      title: `aneuploid cells${unmeasured ? ' (burden UNMEASURED)' : ''}`,
      detail: data.card.mechanism.downstream[2] ?? data.card.mechanism.downstream[1] ?? '',
      branches: [
        {
          id: 'D2',
          tone: 'decision',
          ...directionTitle(directions, 'D2', 'exploit their stress'),
          drugs: drugsFor(rows, 'D2'),
        },
      ],
    },
    {
      id: 'tumour',
      tone: 'broken',
      title: data.summary.card.tumour_context,
      detail: data.card.mechanism.downstream[3] ?? '',
      branches: [
        {
          id: 'D4',
          tone: 'decision',
          ...directionTitle(directions, 'D4', 'the tumour itself'),
          drugs: drugsFor(rows, 'D4'),
        },
      ],
    },
  ];
}
