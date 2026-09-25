/**
 * The zoo page's headline is the merged report's own section, not text typed into the page.
 *
 * `headlineOf` is exercised on a synthetic report (the parsing contract), and the page is
 * mounted offline to prove the headline reaches the top of `/zoo` from the captured
 * `/api/zoo/reports/merged` fixture with its entry citations intact.
 */

import { cleanup, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { modules } from '../app/modules';
import reports from '../fixtures/data/zoo-reports.json';
import { headlineOf } from '../pages/zoo/headline';
import { mountModule, stubUnreachableFetch } from './testHarness';

const zoo = modules.find((m) => m.id === 'zoo')!;

afterEach(cleanup);
beforeEach(() => {
  stubUnreachableFetch();
});

describe('headlineOf', () => {
  const report = [
    '# A merged report',
    '',
    '## The headline — one line',
    '',
    'From [entry 12](step-1/methodology/12-x.md), see ![fig](../../figures/a.svg).',
    '',
    '## 1. The lanes',
    '',
    'generated',
  ].join('\n');

  it('cuts out the headline section and stops at the next section', () => {
    const headline = headlineOf(report);
    expect(headline?.heading).toBe('The headline — one line');
    expect(headline?.body).not.toContain('The lanes');
  });

  it('reduces a repo-relative link to its text but leaves an image alone', () => {
    expect(headlineOf(report)?.body).toBe('From entry 12, see ![fig](../../figures/a.svg).');
  });

  it('answers null for a report without a headline', () => {
    expect(headlineOf('# r\n\n## 1. The lanes\n')).toBeNull();
  });
});

describe('the zoo page headline', () => {
  it('is the merged report’s headline, at the top, with its entries cited', async () => {
    const { caught } = await mountModule(zoo);
    expect(caught).toBeNull();

    const expected = headlineOf(reports.payload.merged.markdown);
    expect(expected).not.toBeNull();
    const heading = screen.getAllByText(expected!.heading)[0];
    const framing = screen.getByText('Several opinions, kept apart on purpose');
    // Above the page's own framing callout: the first thing a reader meets.
    expect(
      heading.compareDocumentPosition(framing) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(screen.getByText('hand-written summary')).toBeInTheDocument();
    // The row cells carry the entry each number is quoted from.
    for (const entry of ['129', '130', '148'])
      expect(screen.getAllByText(entry).length).toBeGreaterThan(0);
  }, 30000);
});
