/**
 * The model-zoo page, offline.
 *
 * Gate 2 already proves the module mounts and gate 3 that it is accessible. What a generic
 * smoke test cannot see is everything this page exists to get *right*, and each of those is
 * asserted here:
 *
 *   1. the case (gene, iteration, label) is the one the API reported — nothing on the page is
 *      typed in, so a different configuration would move every one of these strings;
 *   2. a lane with **no opinion** on the case pair is drawn and labelled as having none, and
 *      never as a rank, a percentile or a zero — the one misreading that would invert the
 *      page's meaning;
 *   3. `skipped_genes_recorded: false` is shown as "not recorded", not as an empty list;
 *   4. the agreement matrix carries **n** beside every ρ, because a correlation without its
 *      overlap is not a claim;
 *   5. the report view marks the one written section as written;
 *   6. no HGVS spelling of the patient's alleles reaches the DOM from the gene view.
 *
 * No Plotly chart is on this page — every figure here is DOM or SVG — so the module is not
 * stubbed, unlike in the tests of the chart pages.
 */

import { cleanup, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { modules } from '../app/modules';
import mergeFixture from '../fixtures/data/zoo-merge.json';
import { mountModule, stubUnreachableFetch } from './testHarness';

const zoo = modules.find((m) => m.id === 'zoo')!;

/** An HGVS coding or protein spelling, the one field the committed fixture redacts. */
const HGVS = /\b(c\.\d+[ACGT>]|p\.[A-Z][a-z]{2}\d+)/;

afterEach(cleanup);
beforeEach(() => {
  stubUnreachableFetch();
});

describe('the model zoo page', () => {
  it('shows the case the API reported, and says where it was read from', async () => {
    const { caught } = await mountModule(zoo);
    expect(caught).toBeNull();

    // The gene, the iteration and the case label all come from the payload.
    expect(screen.getAllByText('BUB1B').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/iteration4/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Mosaic Variegated Aneuploidy/).length).toBeGreaterThan(0);
    // …and the page names the configuration key rather than asserting the gene on its own.
    expect(screen.getAllByText(/zoo\.example\.toml/).length).toBeGreaterThan(0);
  }, 30000);

  it('draws a lane with no opinion as no opinion, never as a rank or a zero', async () => {
    await mountModule(zoo);

    // Three of the four lanes scored only one half of the pair and are recorded as silent.
    const silent = screen.getAllByText(/no opinion/);
    expect(silent.length).toBeGreaterThanOrEqual(3);

    // The hatched bar is a distinct element from a ranked bar: it carries the "no opinion"
    // title and no width-derived rank, which is what stops it reading as a bottom rank.
    const hatched = document.querySelectorAll('[title^="no opinion"]');
    expect(hatched.length).toBeGreaterThanOrEqual(3);

    // The one lane that did rank the pair prints its rank and its lane size.
    expect(screen.getAllByText(/rank 11,980 of 50,696/).length).toBeGreaterThan(0);
  }, 30000);

  it('says the skipped genes were not recorded rather than showing an empty list', async () => {
    await mountModule(zoo);
    expect(screen.getByText(/not recorded by this run/)).toBeInTheDocument();
  }, 30000);

  it('prints n beside every ρ in the agreement matrix', async () => {
    await mountModule(zoo);

    const matrix = screen.getByRole('table', {
      name: /Spearman rank correlation between every pair of model lanes/i,
    });
    // Every lane × every lane, each cell carrying its own overlap count — sized from the
    // captured payload, so a capture with more lanes does not need this test edited.
    const lanes = mergeFixture.payload.matrix.models.length;
    expect(within(matrix).getAllByText(/^n /).length).toBe(lanes * lanes);
    // The measured ρ between the two protein lanes, with the overlap it stands on.
    expect(within(matrix).getAllByText('0.580').length).toBeGreaterThan(0);
    expect(within(matrix).getAllByText('n 3,943').length).toBeGreaterThan(0);
  }, 30000);

  it('marks the report’s one written section as written', async () => {
    await mountModule(zoo);
    expect(screen.getAllByText('written, not computed').length).toBe(1);
    expect(screen.getAllByText(/Generator marker/).length).toBe(1);
  }, 30000);

  it('shows the case gene’s alleles without any HGVS spelling of them', async () => {
    await mountModule(zoo);

    // The gene view opened on the case gene and found its two allele records.
    expect(screen.getAllByText('93e077ae83ac2642').length).toBeGreaterThan(0);
    expect(screen.getAllByText('addc19de8fa29228').length).toBeGreaterThan(0);

    expect(document.body.textContent ?? '').not.toMatch(HGVS);
  }, 30000);
});
