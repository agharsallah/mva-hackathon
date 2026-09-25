import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

import { EmptyState } from '../../components/EmptyState';
import { cx } from '../../lib/ui';
import { useUrlState } from '../../lib/urlstate';
import { CatalogPanel } from './CatalogPanel';
import type { CatalogOption } from './model';

/**
 * The catalogue explorer: one picker over both numberings. `?cat=iteration2` opens a
 * research iteration's catalogue; `?cat=track2/iteration-4` opens a submission folder's,
 * which arrives with `/api/submissions`. The selection lives in the URL, so a link from a
 * research iteration's page lands on its own data.
 */
export function CatalogExplorer({
  options,
  fallback,
  source,
  folderSource,
}: {
  options: CatalogOption[];
  fallback: string;
  source?: string;
  folderSource?: string;
}) {
  const keys = options.map((o) => o.key);
  const [picked, setPicked] = useUrlState('cat', fallback, keys);
  const option = options.find((o) => o.key === picked) ?? options[0];
  const ref = useRef<HTMLDivElement>(null);
  const { hash } = useLocation();

  // `/iterations?cat=iteration2#data-catalog` comes from a research page: the section is
  // below the fold of a lazily loaded page, so it scrolls itself into view once it exists.
  useEffect(() => {
    if (hash === '#data-catalog') ref.current?.scrollIntoView({ block: 'start' });
  }, [hash]);

  if (!option) return <EmptyState>No iteration to catalogue.</EmptyState>;

  return (
    <div ref={ref} className="scroll-mt-28 space-y-3">
      <div className="space-y-2">
        <PickerRow
          label="research iterations"
          options={options.filter((o) => o.group === 'research')}
          picked={option.key}
          onPick={setPicked}
        />
        <PickerRow
          label="submission folders"
          options={options.filter((o) => o.group === 'submission')}
          picked={option.key}
          onPick={setPicked}
        />
      </div>
      {option.catalog ? (
        <CatalogPanel
          catalog={option.catalog}
          title={`The data ${option.label} rests on`}
          source={option.group === 'research' ? source : folderSource}
        />
      ) : (
        <EmptyState>
          This folder’s catalogue arrives with the submission dossier payload, which has not loaded
          (or failed). Its coverage counts are in the folder table above.
        </EmptyState>
      )}
    </div>
  );
}

function PickerRow({
  label,
  options,
  picked,
  onPick,
}: {
  label: string;
  options: CatalogOption[];
  picked: string;
  onPick: (key: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label={label}>
      <span className="w-36 shrink-0 text-micro text-chrome-400">{label}</span>
      {options.map((o) => {
        const on = o.key === picked;
        const n = o.catalog?.coverage.datasets;
        return (
          <button
            key={o.key}
            type="button"
            aria-pressed={on}
            onClick={() => onPick(o.key)}
            className={cx(
              'rounded-control border px-2 py-1 font-mono text-micro transition',
              on
                ? 'border-machinery-700 bg-machinery-950/60 text-machinery-200'
                : 'border-line-strong bg-chrome-900 text-chrome-300 hover:bg-chrome-800',
            )}
          >
            {o.key}
            {n !== undefined && <span className="ml-1.5 text-chrome-500">{n}</span>}
          </button>
        );
      })}
    </div>
  );
}
