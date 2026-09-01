import type { Envelope, RegionVariant, RegionWindow, SearchResolution } from '../../api/types';
import type { Params } from '../../api/client';
import { prng } from '../prng';
import { rows } from '../loader';

/**
 * FIXTURE — the universal search, offline.
 *
 * SYNTHETIC BY DESIGN, all of it. Every position here sits on a 1,000,000-based ladder:
 * this repository never commits a genomic coordinate, and the search endpoints are the
 * two that serve real ones. Nothing below is a measurement.
 *
 * MIRRORS, DOES NOT DEFINE, the grammar. `mva.viz.search` is the authority on what a
 * query means; the classifier here exists only so the page is explorable with no server,
 * and it is deliberately the smaller of the two — it accepts the three canonical forms
 * and refuses everything else by returning `undefined`, which makes the client surface
 * the real "API unreachable" error instead of inventing a resolution.
 *
 * The lookup tables (`PANEL`, `OFF_PANEL`, `IN_CALLSET`, `IN_DBSNP_ONLY`) are pure data
 * and live in `data/search-lookups.json`. Everything else here — the regexes, the
 * resolvers, the synthetic record generator — is the classifier itself and stays code.
 */

/** Kept in step with `search.MAX_SPAN` on the server. Shown in the offline cap message. */
export const FIXTURE_MAX_SPAN = 5_000_000;

/** Kept in step with `search.FLANK`. */
const FLANK = 1_000;

const REGION = /^(?:chr)?([1-9]|1\d|2[0-2]|X|Y|MT|M):(\d+)(?:-|\.\.)(\d+)$/i;
const POINT = /^(?:chr)?([1-9]|1\d|2[0-2]|X|Y|MT|M):(\d+)$/i;
const RSID = /^rs(\d+)$/i;

interface Interval {
  chrom: string;
  start: number;
  end: number;
}

interface Point {
  chrom: string;
  start: number;
}

interface Lookups {
  /** The offline panel. Intervals are SYNTHETIC — the same 1,000,000-based placeholders
   * the panel fixture uses — so the shape of a panel hit is reviewable without a coordinate. */
  panel: Record<string, Interval>;
  /** Off-panel symbols the offline Ensembl path pretends to know, so that branch is reviewable. */
  offPanel: Record<string, Interval>;
  /** rsIDs the offline callset "carries" — a hit that needs no Ensembl call. */
  inCallset: Record<string, Point>;
  /** rsIDs dbSNP knows but this offline callset never called — the resolved-but-empty case. */
  inDbsnpOnly: Record<string, Point>;
}

let cached: Promise<Lookups> | undefined;

function lookups(): Promise<Lookups> {
  return (cached ??= rows<Lookups>('search-lookups'));
}

const fmt = (n: number) => n.toLocaleString('en-US');

/**
 * Resolve one query offline, or `undefined` for anything the fixture cannot honestly
 * answer — an unparseable string, an unknown name, an over-cap window. Returning
 * `undefined` makes the client re-raise the real error rather than fake a 404.
 */
export async function searchFixture(q: string | undefined): Promise<SearchResolution | undefined> {
  const text = (q ?? '').trim();
  if (!text) return undefined;
  const compact = text.replace(/[,_\s]/g, '');

  const span = REGION.exec(compact);
  if (span) {
    const [chrom, start, end] = [span[1], Number(span[2]), Number(span[3])];
    if (start > end || end - start + 1 > FIXTURE_MAX_SPAN) return undefined;
    return {
      kind: 'region',
      chrom,
      start,
      end,
      label: `${chrom}:${fmt(start)}-${fmt(end)}`,
      source: 'the query string (parsed, no lookup)',
      note: null,
    };
  }

  const point = POINT.exec(compact);
  if (point) {
    const at = Number(point[2]);
    return {
      kind: 'region',
      chrom: point[1],
      start: Math.max(at - FLANK, 1),
      end: at + FLANK,
      label: `${point[1]}:${fmt(Math.max(at - FLANK, 1))}-${fmt(at + FLANK)}`,
      source: 'the query string (parsed, no lookup)',
      note: null,
    };
  }

  const { panel, offPanel, inCallset, inDbsnpOnly } = await lookups();

  const rs = RSID.exec(text);
  if (rs) return rsidFixture(text.toLowerCase(), inCallset, inDbsnpOnly);

  const symbol = text.toUpperCase();
  const inPanel = panel[symbol];
  if (inPanel) {
    return {
      kind: 'gene',
      ...inPanel,
      label: `${symbol} — ${inPanel.chrom}:${fmt(inPanel.start)}-${fmt(inPanel.end)}`,
      source: 'ressources/data-profile/mva_panel_grch38.bed via pg.warehouse.mva_panel_grch38',
      note: 'candidate-panel interval, padded 20 kb each side',
    };
  }
  const off = offPanel[symbol];
  if (off) {
    return {
      kind: 'gene',
      ...off,
      label: `${symbol} — ${off.chrom}:${fmt(off.start)}-${fmt(off.end)}`,
      source: 'ensembl rest /lookup/symbol/homo_sapiens',
      note: 'Ensembl gene span, unpadded — narrower than the ±20 kb the candidate panel uses',
    };
  }
  return undefined;
}

function rsidFixture(
  name: string,
  inCallset: Record<string, Point>,
  inDbsnpOnly: Record<string, Point>,
): SearchResolution | undefined {
  const called = inCallset[name];
  if (called) {
    return {
      kind: 'rsid',
      chrom: called.chrom,
      start: Math.max(called.start - FLANK, 1),
      end: called.start + FLANK,
      label: `${name} — ${called.chrom}:${fmt(called.start)}`,
      source: 'pg.warehouse.variants_raw (id scan)',
      note: `the callset names this record itself; window is ±${fmt(FLANK)} bp for context`,
    };
  }
  const known = inDbsnpOnly[name];
  if (known) {
    return {
      kind: 'rsid',
      chrom: known.chrom,
      start: Math.max(known.start - FLANK, 1),
      end: known.start + FLANK,
      label: `${name} — ${known.chrom}:${fmt(known.start)}`,
      source: 'ensembl rest /variation/human',
      note:
        'no record in the callset carries this id — the position comes from dbSNP, so an empty ' +
        `table below means the site was never called, not that the id is wrong. Window is ±${fmt(FLANK)} bp.`,
    };
  }
  return undefined;
}

/**
 * A window of SYNTHETIC records. Seeded on the window itself, so the same window always
 * draws the same rows and a screenshot is reproducible.
 *
 * The dbSNP-only rsID window (`inDbsnpOnly`) is deliberately returned **empty**: the
 * resolved-but-never-called state is the one this page exists to make legible, and a
 * fixture that quietly filled it would hide the case from review.
 */
export async function regionFixture(chrom: string, start: number, end: number): Promise<RegionWindow> {
  const { inDbsnpOnly } = await lookups();
  const empty = Object.values(inDbsnpOnly).some((v) => v.chrom === chrom && start <= v.start && v.start <= end);
  if (empty) return { chrom, start, end, n: 0, variants: [] };

  const width = Math.max(end - start + 1, 1);
  // ~1 record per 1.25 kb, the callset's rough genome-wide density, capped so the offline
  // table stays a table.
  const n = Math.min(Math.floor(width / 1250), 400);
  const rand = prng(start + width);
  const variants: RegionVariant[] = [];
  for (let i = 0; i < n; i++) {
    variants.push(record(start + Math.floor(((i + 0.5) * width) / n), rand));
  }
  return { chrom, start, end, n: variants.length, variants };
}

const BASES = ['A', 'C', 'G', 'T'];

function record(pos: number, rand: () => number): RegionVariant {
  const ref = BASES[Math.floor(rand() * 4)];
  const alt = BASES[(BASES.indexOf(ref) + 1 + Math.floor(rand() * 3)) % 4];
  const roll = rand();
  const gt = roll < 0.6 ? '0/1' : roll < 0.95 ? '1/1' : '1/2';
  const dp = 20 + Math.floor(rand() * 40);
  const qual = Math.round((60 + rand() * 900) * 10) / 10;
  const suppressed = qual < 120;
  // A 1/2 site has two ALT alleles and three AD depths, so no single alternate depth
  // exists — nulls here, exactly as the API returns them.
  if (gt === '1/2') {
    return {
      pos,
      id: null,
      ref,
      alt: `${alt},${BASES[(BASES.indexOf(alt) + 1) % 4]}`,
      qual,
      filter: suppressed ? 'LowQual' : 'PASS',
      gt,
      dp,
      ad_ref: Math.floor(dp * 0.3),
      ad_alt: null,
      vaf: null,
      gq: 20 + Math.floor(rand() * 79),
    };
  }
  const share = gt === '1/1' ? 0.94 + rand() * 0.06 : 0.35 + rand() * 0.3;
  const adAlt = Math.round(dp * share);
  return {
    pos,
    // ~88 % of the callset's records carry a dbSNP name; the offline ladder mirrors that.
    id: rand() < 0.88 ? `rs${9_000_000 + (pos % 900_000)}` : null,
    ref,
    alt,
    qual,
    filter: suppressed ? 'LowQual' : 'PASS',
    gt,
    dp,
    ad_ref: dp - adAlt,
    ad_alt: adAlt,
    vaf: Math.round((adAlt / dp) * 10000) / 10000,
    gq: 20 + Math.floor(rand() * 79),
  };
}

// --- registry adapters -------------------------------------------------------
// The registry's builders are typed as always producing an envelope, but "there is no
// honest offline answer for this query" has to stay expressible: the client checks the
// returned value and re-raises the *real* error when nothing comes back. That one cast
// lives here rather than widening the shared registry type.

const SYNTHETIC = 'SYNTHETIC positions — never real';

/** `/api/search` offline: an envelope, or nothing when the fixture cannot answer honestly. */
export async function searchEnvelope(params?: Params): Promise<Envelope<SearchResolution>> {
  const found = await searchFixture(params?.q as string | undefined);
  return (found ? { data: found, cached_at: null, source: `fixture: ${SYNTHETIC}` } : undefined) as Envelope<SearchResolution>;
}

/** `/api/callset/region` offline: always answerable, because the window is fully specified. */
export async function regionEnvelope(params?: Params): Promise<Envelope<RegionWindow>> {
  const chrom = String(params?.chrom ?? '15').replace(/^chr/i, '');
  const start = Number(params?.start ?? 1);
  const end = Number(params?.end ?? start + 1000);
  return {
    data: await regionFixture(chrom, start, end),
    cached_at: null,
    source: `fixture: ${SYNTHETIC}`,
  };
}
