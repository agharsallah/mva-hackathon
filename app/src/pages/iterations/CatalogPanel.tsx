import type { ReactNode } from 'react';

import type { IterationCatalog } from '../../api/types';
import { Badge } from '../../components/Badge';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Callout } from '../../components/Explainer';
import { StatTile } from '../../components/StatTile';
import { TONE_MARK } from '../../lib/palette';
import { CatalogTable } from './CatalogTable';
import { coverageShare, coverageTone, LINEAGE_TONE, lineageCounts } from './model';
import { SegmentBar } from './SegmentBar';

/**
 * One iteration's data catalogue, framed: coverage tiles, the lineage split as one bar, and
 * the table. The catalogue is derived by the API, never typed — every dataset the entries
 * name, joined to `warehouse.data_lineage` and to the manifest beside a file.
 */
export function CatalogPanel({
  catalog,
  title,
  source,
  controls,
}: {
  catalog: IterationCatalog;
  title: string;
  source?: string;
  controls?: ReactNode;
}) {
  const c = catalog.coverage;
  const counts = lineageCounts(catalog.datasets);
  const share = coverageShare(c);

  return (
    <Exhibit
      title={title}
      id="data-catalog-table"
      controls={controls}
      legend={
        <>
          One row per dataset the entries name. Lineage badge:{' '}
          <Chip color={TONE_MARK.good}>green edge</Chip> = a{' '}
          <span className="font-mono">warehouse.data_lineage</span> row records what produced it ·{' '}
          <Chip color={TONE_MARK.machinery}>blue manifest</Chip> = a{' '}
          <span className="font-mono">*.provenance.json</span> beside the file names its upstream
          (fetched data has nothing to derive) · <Chip color={TONE_MARK.broken}>red none</Chip> =
          named, but no record explains it. Role: <Badge tone="good">produced</Badge> = an edge or
          manifest attributes it to one of these entries; <Badge tone="neutral">cited</Badge> = only
          named. Open <em>inputs</em> for the upstream refs and their short sha256.
        </>
      }
      reading={
        c.datasets === 0
          ? 'These entries name no dataset the catalogue recognises.'
          : `${c.with_lineage} of ${c.datasets} datasets (${share ?? 0}%) have a lineage record; ${c.produced} are attributed to these entries rather than only named by them.`
      }
      data={catalog}
      source={source}
    >
      <div className="space-y-4">
        {!catalog.available && (
          <Callout tone="broken" title="Ledger unreachable — tables read as “none” for that reason">
            The warehouse could not be read, so no table could be joined to its lineage edge. That
            is a missing measurement, not missing lineage.{' '}
            <span className="font-mono text-micro">{catalog.note}</span>
          </Callout>
        )}
        {catalog.available && catalog.note && (
          <p className="font-mono text-micro text-chrome-500">{catalog.note}</p>
        )}

        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <StatTile
            label="datasets named"
            value={c.datasets}
            sub={`${catalog.entries.length} entries scanned`}
          />
          <StatTile
            label="with lineage"
            value={share === null ? '—' : `${share}%`}
            tone={coverageTone(c)}
            sub={`${c.with_lineage} of ${c.datasets} · edge or manifest`}
          />
          <StatTile
            label="produced here"
            value={c.produced}
            tone={c.produced > 0 ? 'good' : 'neutral'}
            sub="attributed to these entries"
          />
          <StatTile label="warehouse tables" value={c.tables} tone="machinery" />
          <StatTile label="files" value={c.files} tone="machinery" sub="committed or build/" />
        </div>

        <SegmentBar
          label="lineage status"
          height={10}
          segments={(['edge', 'manifest', 'none'] as const).map((k) => ({
            key: k,
            value: counts[k],
            color: TONE_MARK[LINEAGE_TONE[k]],
            label: k,
          }))}
        />

        <CatalogTable catalog={catalog} />
      </div>
    </Exhibit>
  );
}
