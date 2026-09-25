import { useState } from 'react';

import type { IterationsOverview } from '../../api/types';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Callout } from '../../components/Explainer';
import { StatTile } from '../../components/StatTile';
import { TONE_MARK } from '../../lib/palette';
import { cx } from '../../lib/ui';
import { type CatalogOption, LINEAGE_MEANING, LINEAGE_TONE, lineageCounts } from './model';
import { type Segment, SegmentBar } from './SegmentBar';

/**
 * Lineage health: how much of the ledger names the entry that produced each edge, and — per
 * iteration — how many of the datasets its entries name are explained by an edge, a manifest,
 * or nothing. One bar per catalogue, length = datasets named, so size and coverage read
 * together on one axis.
 */

const GOOD = TONE_MARK[LINEAGE_TONE.edge];
const MANIFEST = TONE_MARK[LINEAGE_TONE.manifest];
const NONE = TONE_MARK[LINEAGE_TONE.none];

interface Row {
  key: string;
  group: CatalogOption['group'];
  segments: Segment[];
  total: number;
  covered: number;
}

/** A catalogue's three-way split; a folder whose dossier has not loaded falls back to its tally. */
function rowsOf(options: CatalogOption[], data: IterationsOverview): Row[] {
  return options.map((o) => {
    if (o.catalog) {
      const n = lineageCounts(o.catalog.datasets);
      return {
        key: o.key,
        group: o.group,
        total: o.catalog.datasets.length,
        covered: n.edge + n.manifest,
        segments: [
          { key: 'edge', value: n.edge, color: GOOD, label: 'edge' },
          { key: 'manifest', value: n.manifest, color: MANIFEST, label: 'manifest' },
          { key: 'none', value: n.none, color: NONE, label: 'none' },
        ],
      };
    }
    const c = data.submissions.find((s) => s.key === o.key)?.catalog;
    const covered = c?.with_lineage ?? 0;
    const total = c?.datasets ?? 0;
    return {
      key: o.key,
      group: o.group,
      total,
      covered,
      segments: [
        { key: 'with', value: covered, color: GOOD, label: 'edge or manifest' },
        { key: 'none', value: total - covered, color: NONE, label: 'none' },
      ],
    };
  });
}

export function LineageHealth({
  data,
  options,
  source,
}: {
  data: IterationsOverview;
  options: CatalogOption[];
  source?: string;
}) {
  const { ledger } = data;
  const rows = rowsOf(options, data);
  const max = Math.max(1, ...rows.map((r) => r.total));
  const [hover, setHover] = useState<{ row: string; seg: Segment } | null>(null);
  const share = ledger.edges === 0 ? null : Math.round((100 * ledger.attributed) / ledger.edges);

  return (
    <div className="space-y-4">
      {!ledger.available && (
        <Callout tone="broken" title="Ledger unreachable">
          The warehouse could not be read, so the attribution count below is not measured.{' '}
          <span className="font-mono text-micro">{ledger.note}</span>
        </Callout>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        <StatTile
          label="ledger edges"
          value={ledger.available ? ledger.edges : '—'}
          tone="machinery"
          sub="rows of warehouse.data_lineage (append-only)"
        />
        <StatTile
          label="attributed to an entry"
          value={share === null ? '—' : `${share}%`}
          tone={share === null ? 'neutral' : share === 100 ? 'good' : 'decision'}
          sub={`${ledger.attributed} of ${ledger.edges} edges name the methodology entry that wrote them`}
        />
        <StatTile
          label="catalogues fully covered"
          value={`${rows.filter((r) => r.total > 0 && r.covered === r.total).length} / ${rows.filter((r) => r.total > 0).length}`}
          tone="neutral"
          sub="non-empty catalogues where every dataset named has an edge or a manifest"
        />
      </div>
      {ledger.note && ledger.available && (
        <p className="font-mono text-micro text-chrome-500">{ledger.note}</p>
      )}

      <Exhibit
        title="Lineage coverage, iteration by iteration"
        legend={
          <>
            One bar per catalogue; its length is the number of datasets the entries name (longest ={' '}
            {max}). <Chip color={GOOD}>green edge</Chip> = {LINEAGE_MEANING.edge} ·{' '}
            <Chip color={MANIFEST}>blue manifest</Chip> = {LINEAGE_MEANING.manifest} ·{' '}
            <Chip color={NONE}>red none</Chip> = {LINEAGE_MEANING.none}. A folder bar with two
            colours only is drawn from its tally, before its dossier payload arrived. Hover a
            segment for its count.
          </>
        }
        reading="Red is the worklist: a dataset an entry names that no edge or manifest explains. A cited dataset may legitimately have no record of its own (an entry can name a table it only read), so read red as “unexplained here”, not “wrong”."
        data={rows.map((r) => ({ key: r.key, total: r.total, covered: r.covered }))}
        source={source}
      >
        <div className="space-y-1.5">
          {rows.map((r, i) => {
            const firstFolder = i > 0 && r.group !== rows[i - 1].group;
            return (
              <div
                key={r.key}
                className={cx(
                  'grid grid-cols-[10.5rem_1fr_7.5rem] items-center gap-3',
                  firstFolder && 'mt-3 border-t border-line-soft pt-3',
                )}
              >
                <span className="truncate font-mono text-micro text-chrome-300">{r.key}</span>
                <SegmentBar
                  label={r.key}
                  height={14}
                  scale={max}
                  segments={r.segments}
                  onHover={(seg) => setHover(seg ? { row: r.key, seg } : null)}
                />
                <span className="text-right font-mono text-micro text-chrome-400">
                  {r.covered}/{r.total}
                  {r.total > 0 && (
                    <span className="text-chrome-500">
                      {' '}
                      · {Math.round((100 * r.covered) / r.total)}%
                    </span>
                  )}
                </span>
              </div>
            );
          })}
          <div className="min-h-[26px] pt-2 text-micro">
            {hover ? (
              <>
                <span className="font-mono text-chrome-200">{hover.row}</span>
                <span className="text-chrome-400"> — {hover.seg.value} datasets with lineage </span>
                <span className="font-mono text-chrome-200">{hover.seg.label}</span>
              </>
            ) : (
              <span className="text-chrome-600">hover a segment to read its count</span>
            )}
          </div>
        </div>
      </Exhibit>
    </div>
  );
}
