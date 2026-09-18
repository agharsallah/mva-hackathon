/**
 * The hero's arithmetic, as data — no JSX, so every number on the "Track 2 in one screen"
 * panel is a pure function of the payload and can be asserted without rendering.
 *
 * Nothing here is typed in. The five approach boxes, the funnel stages, the direction
 * groups and the per-drug "why" sentence are all read off `GET /api/track2`: a re-run of
 * the snapshot changes the hero without an edit in this folder.
 */

import type {
  LadderRow,
  MeasuredFact,
  RepurposingDirection,
  ShortlistRow,
  Track2,
  Track2EvidenceRow,
} from '../../../api/types';
import type { Tone } from '../../../lib/palette';
import { isUnmeasured, isWarning, MIN_SHOWN_RUNG } from '../ladderModel';

/** The section anchors the hero links into. `Section` slugifies its own title the same way. */
export const ANCHOR = {
  mechanism: 'the-mechanism-argument',
  facts: 'measured-facts',
  ladder: 'the-evidence-ladder',
  shortlist: 'the-shortlist',
  doNot: 'the-do-not-table',
  decoy: 'the-decoy-control',
  targets: 'what-a-drug-could-aim-at',
  candidates: 'the-candidates',
  register: 'what-track-2-claimed-before-it-searched',
  catalog: 'the-tables-themselves',
} as const;

/* ── (a) the approach ───────────────────────────────────────────────────────────────── */

export interface ApproachOutcome {
  tone: Tone;
  text: string;
  anchor: string;
}

export interface ApproachStep {
  id: string;
  tone: Tone;
  /** The stage, in three or four words. */
  title: string;
  /** What that stage produced, with the payload's own counts. */
  detail: string;
  anchor: string;
  /** The last box splits: what was argued, and what was set aside. */
  outcomes?: ApproachOutcome[];
}

/** Distinct drug names in the ladder, optionally only those at or above a rung. */
function gradedDrugs(ladder: LadderRow[], minRung?: number): Set<string> {
  const out = new Set<string>();
  for (const row of ladder) {
    if (minRung !== undefined && (row.rung ?? 0) < minRung) continue;
    out.add(row.drug_name);
  }
  return out;
}

/** Distinct drugs whose rung rests on a PMID a person read. */
function curatedDrugs(ladder: LadderRow[]): Set<string> {
  const out = new Set<string>();
  for (const row of ladder) if (row.curated_rung !== null) out.add(row.drug_name);
  return out;
}

export function argueRows(data: Track2): ShortlistRow[] {
  return (data.shortlist ?? []).filter((r) => r.verdict === 'argue');
}

/** The five boxes of the approach flow, left to right. */
export function approachSteps(data: Track2): ApproachStep[] {
  const card = data.card;
  const rungs = card.evidence_ladder?.rungs.length ?? 0;
  const argue = argueRows(data).length;
  const doNot = (data.do_not ?? []).length;

  return [
    {
      id: 'input',
      tone: 'raw',
      title: 'the confirmed pair + the clinical terms',
      detail: `${card.gene.symbol}, ${card.alleles.length} alleles · ${card.case.hpo_terms.length} HPO terms · ${data.summary.card.tumour_context}`,
      anchor: ANCHOR.mechanism,
    },
    {
      id: 'card',
      tone: 'machinery',
      title: `mechanism card v${card.version}`,
      detail: `gene, ${card.alleles.length} alleles, ${(card.measured_facts ?? []).length} measured facts, ${card.repurposing_directions.length} directions`,
      anchor: ANCHOR.facts,
    },
    {
      id: 'search',
      tone: 'machinery',
      title: `${card.constraints.sources.length} public drug sources`,
      detail: `${data.summary.candidates.distinct_approved_drugs} approved drugs on ${data.summary.targets.total} targets`,
      anchor: ANCHOR.targets,
    },
    {
      id: 'grade',
      tone: 'decision',
      title: 'the evidence ladder',
      detail: `${rungs} rungs written before the search · ${(data.evidence ?? []).length} curated papers · ${(data.decoys ?? []).length} decoy genes as control`,
      anchor: ANCHOR.ladder,
    },
    {
      id: 'out',
      tone: 'good',
      title: 'what came out',
      detail: 'a shortlist and a do-not table — hypotheses for follow-up, never a prescription',
      anchor: ANCHOR.shortlist,
      outcomes: [
        { tone: 'good', text: `${argue} argued drugs`, anchor: ANCHOR.shortlist },
        { tone: 'broken', text: `${doNot} in the do-not table`, anchor: ANCHOR.doNot },
      ],
    },
  ];
}

/* ── (b) the suggestion ─────────────────────────────────────────────────────────────── */

/** The order the reader needs: the tumour first, then the two mechanism angles. */
const DIRECTION_ORDER = ['D4', 'D3', 'D2', 'D1'];

/**
 * The plain-English half of a direction's name, keyed by the card's own id.
 *
 * The technical name always comes from the payload; this is the translation beside it, in
 * the repo's `technical term (plain-English meaning)` pattern. An id the card adds later
 * falls back to the direction's own `rationale`, so a new direction is never unlabelled.
 */
const DIRECTION_GLOSS: Record<string, string> = {
  D1: 'reinforce the checkpoint itself',
  D2: 'exploit the stress of aneuploid cells',
  D3: 'raise the amount of working BubR1',
  D4: "the child's tumour",
};

export interface DirectionGroup {
  id: string;
  /** The card's own name for the direction. */
  name: string;
  /** The plain-English half. */
  gloss: string;
  rationale: string;
  rows: ShortlistRow[];
}

/** The argued rows, grouped by direction, in `DIRECTION_ORDER`. Empty groups are dropped. */
export function argueByDirection(data: Track2): DirectionGroup[] {
  const rows = argueRows(data);
  const byId = new Map<string, RepurposingDirection>();
  for (const d of data.card.repurposing_directions) byId.set(d.id, d);

  const ids = [...new Set(rows.map((r) => r.direction_id))].sort((a, b) => {
    const rank = (id: string) => {
      const i = DIRECTION_ORDER.indexOf(id);
      return i === -1 ? DIRECTION_ORDER.length : i;
    };
    return rank(a) - rank(b) || a.localeCompare(b);
  });

  return ids.map((id) => {
    const direction = byId.get(id);
    return {
      id,
      name: direction?.name ?? id,
      gloss: DIRECTION_GLOSS[id] ?? direction?.rationale ?? id,
      rationale: direction?.rationale ?? '',
      rows: rows.filter((r) => r.direction_id === id),
    };
  });
}

/**
 * A shortlist row's colour, on the same rule the ladder cells use: a drug the card warns
 * against is red whatever its rung, a curated result at rung 4 or 5 is green, a curated
 * result lower down is yellow, and an automated-only row is blue machinery.
 */
export function shortlistTone(row: ShortlistRow): Tone {
  if (isWarning(row)) return 'broken';
  if (row.curated_pmids.length > 0) return (row.rung ?? 0) >= 4 ? 'good' : 'decision';
  return 'machinery';
}

/** `LOVASTATIN` → `Lovastatin`. The tables keep the source's own casing; the cards do not. */
export function titleCase(name: string): string {
  return name
    .toLowerCase()
    .split(/(\s+|-)/)
    .map((part) => (/^[a-z]/.test(part) ? part[0]!.toUpperCase() + part.slice(1) : part))
    .join('');
}

/**
 * A proxy compound's label. The `proxy_of` column holds three shapes: a drug name in the
 * sources' own capitals (`LOVASTATIN`), an acronym (`AICAR`), and a class written as prose
 * (`HDAC2/3 loss`). Only a long all-capitals word is a shouted drug name, so only that is
 * folded — an acronym and a prose class are left exactly as the table wrote them.
 */
export function proxyLabel(name: string): string {
  return name
    .split(/(\s+)/)
    .map((word) => (/^[A-Z]{7,}$/.test(word) ? word[0] + word.slice(1).toLowerCase() : word))
    .join('');
}

/** The curated rows behind one shortlist entry, in the order the evidence table holds them. */
export function evidenceFor(evidence: Track2EvidenceRow[], row: ShortlistRow): Track2EvidenceRow[] {
  return evidence.filter(
    (e) => e.drug_name === row.drug_name && e.direction_id === row.direction_id,
  );
}

/** The compound actually tested, when the curated result was inherited rather than measured. */
export function proxyOf(rows: Track2EvidenceRow[]): string | null {
  const proxy = rows.find((e) => e.proxy && e.proxy_of.trim() !== '');
  return proxy ? proxy.proxy_of : null;
}

/** The one-sentence "why", taken from the curated claim rather than written here. */
export function claimOf(rows: Track2EvidenceRow[]): string {
  return rows.find((e) => e.claim.trim() !== '')?.claim ?? '';
}

/** The two paediatric pointers the shortlist states in words, read as flags. */
export interface PediatricMarks {
  /** The US label carries a section 8.4 Pediatric Use. */
  label: boolean;
  /** At least one registered study admits children. */
  study: boolean;
}

export function pediatricMarks(row: ShortlistRow): PediatricMarks {
  const text = row.pediatric_evidence.toLowerCase();
  return { label: text.includes('8.4'), study: text.includes('admitting children') };
}

/* ── (c) the output ─────────────────────────────────────────────────────────────────── */

export interface FunnelStage {
  label: string;
  value: number;
  tone: Tone;
  /** What the step actually tested, for the hover and the legend. */
  note: string;
}

/**
 * The search as a funnel: how many approved drugs existed, how many were graded, how many
 * cleared the submittable rung, and how many carry a result a person read.
 */
export function funnelStages(data: Track2): FunnelStage[] {
  const ladder = data.evidence_ladder ?? [];
  return [
    {
      label: 'approved drugs',
      value: data.summary.candidates.distinct_approved_drugs,
      tone: 'machinery',
      note: 'distinct market-approved molecules the public sources returned for these targets',
    },
    {
      label: 'graded',
      value: gradedDrugs(ladder).size,
      tone: 'machinery',
      note: 'placed on a rung of the ladder, on at least one direction',
    },
    {
      label: `rung ≥ ${MIN_SHOWN_RUNG}`,
      value: gradedDrugs(ladder, MIN_SHOWN_RUNG).size,
      tone: 'decision',
      note: 'above "mechanism only" — rung 1 is named, never submitted',
    },
    {
      label: 'curated result',
      value: curatedDrugs(ladder).size,
      tone: 'good',
      note: 'a PubMed paper a person read, attached to the drug and the direction',
    },
  ];
}

/** The rows the report may not argue from: the do-not table, counted by verdict. */
export function setAside(data: Track2): { total: number; byVerdict: Array<[string, number]> } {
  const rows = data.do_not ?? [];
  const counts = new Map<string, number>();
  for (const r of rows) counts.set(r.verdict, (counts.get(r.verdict) ?? 0) + 1);
  return { total: rows.length, byVerdict: [...counts.entries()].sort((a, b) => b[1] - a[1]) };
}

/** The shortlist rows that only carry a registered trial in the tumour — listed, not claimed. */
export function contextOnlyCount(data: Track2): number {
  return (data.shortlist ?? []).filter((r) => r.verdict !== 'argue').length;
}

/** The card's stated gaps: a fact whose value begins UNMEASURED. */
export function unmeasuredFacts(data: Track2): MeasuredFact[] {
  return (data.card.measured_facts ?? []).filter(isUnmeasured);
}
