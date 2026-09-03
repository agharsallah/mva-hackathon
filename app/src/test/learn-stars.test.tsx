/**
 * Starring a definition keeps it, across a remount, in this browser.
 *
 * The Learn page is mounted the way gate 2 mounts every module (offline, in a MemoryRouter
 * at its own route). Starring DNA must put it in the rail's Starred list; unmounting and
 * mounting again must find it still there (jsdom's localStorage persists within a test);
 * unstarring from the list must remove it and restore the empty state.
 */

import { cleanup, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { modules } from '../app/modules';
import { mountModule, stubUnreachableFetch } from './testHarness';

vi.mock('plotly.js-dist-min', () => ({
  default: { react: vi.fn().mockResolvedValue(undefined), purge: vi.fn() },
}));

const learn = modules.find((m) => m.id === 'learn')!;

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

beforeEach(() => {
  stubUnreachableFetch();
  window.localStorage.clear();
});

const starredList = () => screen.getByRole('group', { name: 'Starred definitions' });

describe('starred definitions', () => {
  it('star → listed; remount → still listed; unstar from the list → gone', async () => {
    const user = userEvent.setup();
    await mountModule(learn);

    expect(within(starredList()).queryByText('DNA')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Star DNA' }));
    expect(within(starredList()).getByText('DNA')).toBeTruthy();
    // Two ways back out: the star on the card and the star in the list.
    expect(screen.getAllByRole('button', { name: 'Unstar DNA' })).toHaveLength(2);
    expect(JSON.parse(window.localStorage.getItem('mva.learn.starred') ?? '[]')).toEqual(['dna']);

    cleanup();
    await mountModule(learn);
    expect(within(starredList()).getByText('DNA')).toBeTruthy();

    await user.click(within(starredList()).getByRole('button', { name: 'Unstar DNA' }));
    expect(within(starredList()).queryByText('DNA')).toBeNull();
    expect(within(starredList()).getByText(/Star a definition to keep it here/)).toBeTruthy();
  }, 20_000);

  it('folds a long list behind "show all", and unfolds it', async () => {
    const user = userEvent.setup();
    // Eight starred words seeded straight into storage, more than the six shown by default —
    // announced with the `storage` event another tab's write would fire, so the store re-reads.
    window.localStorage.setItem(
      'mva.learn.starred',
      JSON.stringify([
        'dna',
        'genome',
        'chromosome',
        'gene',
        'protein',
        'exon',
        'intron',
        'allele',
      ]),
    );
    window.dispatchEvent(new StorageEvent('storage', { key: 'mva.learn.starred' }));
    await mountModule(learn);
    const list = starredList();
    // Counted as elements: jsdom gives `<li>` inside `<details>` no accessible listitem role.
    expect(list.querySelectorAll('li')).toHaveLength(6);
    expect(within(list).queryByText('Allele')).toBeNull();

    await user.click(within(list).getByRole('button', { name: /show all 8/i }));
    expect(list.querySelectorAll('li')).toHaveLength(8);
    expect(within(list).getByText('Allele')).toBeTruthy();

    await user.click(within(list).getByRole('button', { name: /show fewer/i }));
    expect(list.querySelectorAll('li')).toHaveLength(6);
  }, 20_000);
});
