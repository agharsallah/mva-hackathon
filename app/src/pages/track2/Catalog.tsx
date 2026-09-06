/**
 * The five snapshot tables, each with its columns explained and its manifest facts.
 *
 * This is the part a reviewer needs and a report usually omits: what every column means in
 * plain English, how many rows there are, the checksum of the file, when it was built, by
 * which commit, by what rule, and which public APIs were read to produce it. A drug name
 * with no such trail is a rumour.
 */

import { useState } from 'react';

import type { Track2CatalogTable } from '../../api/types';
import { Badge } from '../../components/Badge';
import { Select } from '../../components/Controls';
import { DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { StatTile } from '../../components/StatTile';
import { int } from '../../lib/format';
import { C } from '../../lib/palette';
import { cx, WELL } from '../../lib/ui';
import { T } from './Term';

export function Catalog({ catalog, source }: { catalog: Track2CatalogTable[]; source?: string }) {
  const [picked, setPicked] = useState(catalog[0]?.table ?? '');
  const table = catalog.find((t) => t.table === picked) ?? catalog[0];
  if (!table) return null;

  return (
    <Exhibit
      title="Catalog — every column, and where the table came from"
      legend={
        <>
          <Chip color={C.machinery}>blue = neutral machinery</Chip> — the table&rsquo;s own facts:
          rows, checksum, build time, the commit that produced it.{' '}
          <Chip color={C.raw}>purple = the raw input</Chip> — the public APIs read to build it, each
          with the instant it was retrieved and a roll-up digest of its cached replies. A{' '}
          <Badge>version —</Badge> means that API states no release number, recorded as a gap rather
          than faked.
        </>
      }
      reading={`${catalog.length} tables, ${int(catalog.reduce((n, t) => n + t.rows, 0))} rows in total, all built by ${table.code_version} at ${table.built_at}. Every one carries a sha256 of the file itself, so the report can name bytes it does not have to carry.`}
      data={catalog}
      source={source}
      controls={
        <Select
          label="table"
          value={picked}
          options={catalog.map((t) => ({ value: t.table, label: `${t.table} (${int(t.rows)})` }))}
          onChange={setPicked}
        />
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatTile label="rows" tone="machinery" value={int(table.rows)} sub={table.path} />
          <StatTile
            label="sha256"
            value={<span className="font-mono text-sm">{table.sha256.slice(0, 12)}</span>}
            sub="of the file on disk"
            hint={table.sha256}
          />
          <StatTile label="built at" value={table.built_at.slice(0, 16)} sub={table.code_version} />
          <StatTile
            label="public APIs read"
            tone="raw"
            value={table.inputs.length}
            sub={table.inputs.map((i) => i.name).join(' · ')}
          />
        </div>

        <div className={cx(WELL, 'space-y-1')}>
          <h4 className="text-xs font-semibold text-chrome-200">How the rows were produced</h4>
          <p className="max-w-[100ch] text-micro leading-relaxed text-chrome-400">{table.method}</p>
        </div>

        <DataTable<Track2CatalogTable['columns'][number]>
          rows={table.columns}
          rowKey={(r) => r.name}
          columns={[
            {
              key: 'name',
              header: 'column',
              render: (r) => <span className="font-mono text-xs text-chrome-100">{r.name}</span>,
            },
            {
              key: 'type',
              header: 'type',
              render: (r) => <Badge tone="machinery">{r.type}</Badge>,
            },
            {
              key: 'description',
              header: 'what it means',
              render: (r) => <span className="text-chrome-400">{r.description}</span>,
            },
          ]}
        />

        <DataTable<Track2CatalogTable['inputs'][number]>
          rows={table.inputs}
          rowKey={(r) => `${r.name}|${r.url}`}
          columns={[
            { key: 'name', header: 'source', render: (r) => <Badge tone="raw">{r.name}</Badge> },
            {
              key: 'url',
              header: 'endpoint',
              render: (r) => <span className="font-mono text-micro break-all">{r.url}</span>,
            },
            {
              key: 'version',
              header: 'version',
              render: (r) => r.version ?? <Badge>version —</Badge>,
            },
            {
              key: 'retrieved_at',
              header: 'retrieved',
              render: (r) => r.retrieved_at.slice(0, 19),
            },
            {
              key: 'sha256',
              header: 'reply digest',
              render: (r) => (
                <span className="font-mono text-micro" title={r.sha256}>
                  {r.sha256.slice(0, 12)}
                </span>
              ),
            },
          ]}
        />

        <p className="max-w-[95ch] text-micro leading-relaxed text-chrome-400">
          Each digest is a roll-up over every cached reply this build read from that API — a public
          endpoint has no single byte stream to hash, so the{' '}
          <T
            slug="checksum-sha-256"
            term="sha256"
            plain="a content hash: it names bytes without carrying them"
          />{' '}
          is computed over the sorted digests of the replies instead. It is reproducible from the
          cache and changes the moment any reply changes.
        </p>
      </div>
    </Exhibit>
  );
}
