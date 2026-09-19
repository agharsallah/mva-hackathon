/**
 * The Track 2 hero — "Track 2 in one screen".
 *
 * `track2-page.test.tsx` asserts the report below; this file asserts the panel that now
 * opens it, because the hero is the part a reviewer reads first and the part most likely to
 * drift from the payload it claims to summarise.
 *
 *   1. the approach flow is five boxes, each an anchor into the section that shows its
 *      working, and every count in it is the fixture's own;
 *   2. the suggestion is one card per argued row, grouped tumour-first, with the paper;
 *   3. the caution strip names the two spindle poisons that are standard chemotherapy and
 *      says what the flag is for;
 *   4. the funnel and the stated gap (F8) read off the ladder, not off a constant;
 *   5. the pathway diagram draws both dead ends — the direction with no approved drug and
 *      the class the mechanism warns against;
 *   6. the hero precedes the process material in document order.
 *
 * The funnel draws through the shared `Plot` wrapper, so `plotly.js-dist-min` is stubbed —
 * `vi.mock` is hoisted per file, which is why it cannot live in the harness.
 */

import { cleanup, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Track2 } from '../api/types';
import { modules } from '../app/modules';
import fixture from '../fixtures/data/track2.json';
import { mountModule, stubUnreachableFetch } from './testHarness';

vi.mock('plotly.js-dist-min', () => ({
  default: { react: vi.fn().mockResolvedValue(undefined), purge: vi.fn() },
}));

const track2 = modules.find((m) => m.id === 'track2')!;

/** The committed offline payload, so every count below is the fixture's own. */
const data = fixture as unknown as Track2;
const argue = (data.shortlist ?? []).filter((r) => r.verdict === 'argue');
const group = (verdict: string) => (data.do_not ?? []).filter((r) => r.verdict === verdict);
const grouped = (n: number): string => n.toLocaleString('en-US');

afterEach(cleanup);
beforeEach(() => {
  stubUnreachableFetch();
});

describe('the Track 2 hero', () => {
  it('opens with the hero: five approach boxes, every count read off the payload', async () => {
    await mountModule(track2);

    const flow = screen.getByTestId('approach-flow');
    expect(flow.querySelectorAll('li[data-box]').length).toBe(5);

    const text = flow.textContent ?? '';
    expect(text).toContain(`mechanism card v${data.card.version}`);
    expect(text).toContain(`${data.card.constraints.sources.length} public drug sources`);
    expect(text).toContain(String(data.summary.candidates.distinct_approved_drugs));
    expect(text).toContain(String(data.summary.targets.total));
    expect(text).toContain(`${argue.length} argued drugs`);
    expect(text).toContain(`${(data.do_not ?? []).length} in the do-not table`);
    // Each box is an anchor into the section that shows its working.
    expect(flow.querySelectorAll('a[href^="#"]').length).toBeGreaterThanOrEqual(5);
  }, 30000);

  it('shows every argued drug as a card, grouped by direction, with its paper', async () => {
    await mountModule(track2);

    const panel = screen.getByTestId('suggestion-panel');
    const cards = panel.querySelectorAll('li[data-drug]');
    expect(cards.length).toBe(argue.length);

    // The tumour direction is read first, then the two mechanism angles.
    const groups = [...panel.querySelectorAll('section[data-direction]')].map((el) =>
      el.getAttribute('data-direction'),
    );
    expect(groups[0]).toBe('D4');
    expect(new Set(groups)).toEqual(new Set(argue.map((r) => r.direction_id)));

    // A card whose curated result was inherited says which compound was actually tested.
    expect(panel.textContent).toMatch(/proxy · /);
    expect(within(panel).getAllByRole('link', { name: /^PMID / }).length).toBeGreaterThan(0);
  }, 30000);

  it('flags the caution rows, naming the two that are standard chemotherapy', async () => {
    await mountModule(track2);

    const strip = screen.getByTestId('caution-strip');
    expect(strip.querySelectorAll('[data-testid="caution-chips"] li').length).toBe(
      group('caution').length,
    );
    expect(strip.textContent).toContain('Vincristine');
    expect(strip.textContent).toContain('Vinorelbine');
    expect(strip.textContent).toContain('never advice to withhold');
  }, 30000);

  it('draws the funnel and the stated gap beside it', async () => {
    await mountModule(track2);

    const output = screen.getByTestId('output-panel');
    const rung2 = new Set(
      (data.evidence_ladder ?? []).filter((r) => (r.rung ?? 0) >= 2).map((r) => r.drug_name),
    ).size;
    const curated = new Set(
      (data.evidence_ladder ?? []).filter((r) => r.curated_rung !== null).map((r) => r.drug_name),
    ).size;
    expect(output.textContent).toContain(grouped(rung2));
    expect(output.textContent).toContain(grouped(curated));
    expect(output.textContent).toContain(grouped((data.do_not ?? []).length));

    // The card's stated gaps drive the chip: a yellow chip per UNMEASURED fact, or one green
    // chip when every fact is measured. The test reads which case the fixture is in.
    const gaps = (data.card.measured_facts ?? []).filter((f) => /^UNMEASURED\b/i.test(f.value));
    if (gaps.length > 0) {
      const chips = screen.getByTestId('unmeasured-chips').textContent ?? '';
      for (const gap of gaps) expect(chips).toContain(`${gap.id} unmeasured`);
    } else {
      const chip = screen.getByTestId('measured-chip').textContent ?? '';
      expect(chip).toContain(`all ${(data.card.measured_facts ?? []).length} card facts measured`);
      expect(chip).toContain('F8');
    }

    expect(screen.getByTestId('artefact-links').querySelectorAll('a').length).toBeGreaterThan(4);
  }, 30000);

  it('draws the pathway from the alleles to each intervention point', async () => {
    await mountModule(track2);

    const diagram = screen.getByTestId('pathway-diagram');
    const stages = [...diagram.querySelectorAll('li[data-stage]')].map((el) =>
      el.getAttribute('data-stage'),
    );
    expect(stages).toEqual(['alleles', 'protein', 'missegregation', 'aneuploidy', 'tumour']);

    // The two dead ends are the honest half of the picture.
    expect(diagram.textContent).toContain('no approved drug');
    expect(diagram.textContent).toContain('spindle poisons need the checkpoint: caution');

    // The drug names under a yellow branch are the shortlist's, not a second list.
    const d4 = diagram.querySelector('[data-branch="D4"]')!;
    for (const row of argue.filter((r) => r.direction_id === 'D4'))
      expect(d4.textContent!.toLowerCase()).toContain(row.drug_name.toLowerCase());
  }, 30000);

  it('puts the hero before the process material in document order', async () => {
    await mountModule(track2);

    const hero = document.getElementById('track-2-in-one-screen')!;
    const strategy = document.getElementById('strategy')!;
    expect(hero, 'no hero section').toBeTruthy();
    expect(strategy, 'no strategy section').toBeTruthy();
    expect(hero.compareDocumentPosition(strategy) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    // …and the stale "waits for every Track 1 iteration" tile is gone.
    expect(document.body.textContent).toContain('the shortlist above is the current suggestion');
  }, 30000);
});
