import type { ZooCase, ZooModel, ZooRanks } from '../../api/types/zoo';
import { useUrlState } from '../../lib/urlstate';

/**
 * The zoo page's addressing and its shared vocabulary.
 *
 * ## Why the selections live in the query string
 *
 * The contract's views are `/zoo/models/{key}` and `/zoo/gene/{symbol}`. This app's shell
 * routes from one manifest entry per page and matches a path **exactly**
 * (`app/src/app/modules/journey.ts` → `moduleAt`), so a parameterised path would mount the
 * page but leave it without its header, its position in the journey and its nav link — and
 * fixing that means editing the shell, which this page is not allowed to do. The selections
 * are therefore query parameters on the one `/zoo` route:
 *
 * | contract view            | address here                |
 * | ------------------------ | --------------------------- |
 * | `/zoo/models/{key}`      | `/zoo?model={key}`          |
 * | `/zoo/gene/{symbol}`     | `/zoo?gene={symbol}`        |
 *
 * Both are still one-URL citations — the repo's actual requirement for a view selection
 * (`lib/urlstate.ts`) — and a later shell change can redirect the path form onto these.
 *
 * ## Nothing here is this case
 *
 * There is no default gene and no default model constant. Both defaults are read from the
 * payload: the case gene comes from `ZooRanks.case`, the default lane is the first enabled
 * model the registry returned. A different illness changes `zoo.example.toml`, not this file.
 */

/** The selected lane, or null until the payload names one. */
export function useModelParam(): [string, (next: string) => void] {
  return useUrlState('model', '');
}

/** The selected gene, or '' until the case banner supplies one. */
export function useGeneParam(): [string, (next: string) => void] {
  return useUrlState('gene', '');
}

/** The case the API reported, or undefined when it reported none. */
export function caseOf(ranks: ZooRanks | undefined): ZooCase | undefined {
  return ranks?.case;
}

/** The lane a report view opens on: the asked-for one, else the first that ran. */
export function resolveModelKey(asked: string, models: ZooModel[] | undefined): string | null {
  const ran = (models ?? []).filter((m) => m.enabled);
  if (asked && (models ?? []).some((m) => m.key === asked)) return asked;
  return ran[0]?.key ?? (models ?? [])[0]?.key ?? null;
}

/** The gene a gene view opens on: the asked-for one, else the case's. */
export function resolveGene(asked: string, zooCase: ZooCase | undefined): string | null {
  const symbol = (asked || zooCase?.gene || '').trim().toUpperCase();
  return symbol || null;
}

/** Tier → what it costs to ask this model one question, in plain words. */
export const TIER_WORD: Record<number, string> = {
  1: 'precomputed lookup',
  2: 'local CPU process',
  3: 'remote GPU',
};
