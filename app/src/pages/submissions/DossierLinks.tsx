import { useIterations } from '../../api/hooks';
import type { SubmissionIteration } from '../../api/types';
import { HubLinks } from '../iterations/HubLinks';
import { type HubLink, primaryResearch } from '../iterations/model';
import { iterationLabel } from '../steps/route';

/**
 * Where this folder sits among the iterations: a link to the hub, and one to each research
 * iteration the folder cites, on the folder's own track. The citations come from
 * `/api/iterations`; until it answers (or if it fails) only the hub link shows — the dossier
 * never waits on it.
 */
export function DossierLinks({ iteration }: { iteration: SubmissionIteration }) {
  const q = useIterations();
  const key = `${iteration.track}/iteration-${iteration.number}`;
  const data = q.data?.data;
  const overview = data?.submissions.find((s) => s.key === key);
  const cited = overview?.research ?? [];
  const primary = overview ? primaryResearch(overview) : null;

  const links: HubLink[] = [
    { to: '/iterations', label: 'every iteration, both tracks' },
    ...cited.flatMap<HubLink>((r) => {
      const route = data?.research.find((x) => x.iteration === r)?.routes[
        iteration.track as 'track1' | 'track2'
      ];
      const built = r === primary;
      const label = `${built ? 'built from' : 'quotes'} research ${iterationLabel(r)}`;
      return route ? [{ to: route, label, title: `the steps of ${r} on this track` }] : [];
    }),
    {
      to: `/iterations?cat=${key}#data-catalog`,
      label: 'this folder in the catalogue',
      title: 'the datasets beside every other iteration’s',
    },
  ];

  return <HubLinks links={links} lead="Where it sits" />;
}
