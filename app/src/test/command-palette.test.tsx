/**
 * In-page navigation, half two: the ⌘K / Ctrl+K jump palette. The rail and the jump select —
 * the other two readers of the same section registry — are `section-nav.test.tsx`; the shared
 * tree, the jsdom stubs and why they are needed are in `sectionNavHarness.tsx`.
 *
 * What is worth pinning here is that the palette is the app's only keyboard-only route
 * between two places, and its dialog is a `lazy()` chunk: every test below opens it with the
 * hotkey and awaits the dialog, which is also the assertion that the chunk resolves at all.
 */

import { cleanup, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { CommandPalette } from '../components/CommandPalette';
import {
  expectNoAxeViolations,
  jumpedTo,
  mount,
  openPalette,
  restoreLayoutApis,
  sections,
  stubLayoutApis,
} from './sectionNavHarness';

let scrollIntoView: ReturnType<typeof vi.fn>;

beforeEach(() => {
  scrollIntoView = stubLayoutApis();
});

afterEach(() => {
  cleanup();
  restoreLayoutApis();
  vi.restoreAllMocks();
});

/** Reports the router's current path, so a navigation is assertable without a real page. */
function Probe() {
  const { pathname } = useLocation();
  return <span data-testid="pathname">{pathname}</span>;
}

const palette = (
  <>
    {sections}
    <CommandPalette />
    <Probe />
  </>
);

describe('the ⌘K palette', () => {
  it('opens on Meta+K and focuses the search box', async () => {
    mount(palette);

    const dialog = await openPalette();
    expect(within(dialog).getByRole('combobox')).toHaveFocus();
  });

  it("lists this page's sections, the app's pages and the app-wide actions", async () => {
    mount(palette);

    const dialog = await openPalette();
    const options = within(dialog).getAllByRole('option');

    // Sections first — the palette answers "somewhere on this page" before "another page".
    expect(options.slice(0, 3).map((o) => o.textContent)).toEqual([
      'Coverage by chromosome',
      'Zygosity split',
      'Header fields',
    ]);
    // Then the journey's pages, by title, hinted with their group and nav label.
    expect(options[3]?.textContent).toBe('The callsetData · Callset');
    expect(options[4]?.textContent).toBe('The readsData · Reads');
    expect(options).toHaveLength(9); // 3 sections + 2 pages + 4 actions
  });

  it('filters the listbox to what was typed', async () => {
    const user = userEvent.setup();
    mount(palette);

    const dialog = await openPalette();
    await user.type(within(dialog).getByRole('combobox'), 'callset');

    const options = within(dialog).getAllByRole('option');
    expect(options).toHaveLength(1);
    expect(options[0]?.textContent).toContain('The callset');
  });

  it('says so when nothing matches, rather than showing an empty box', async () => {
    const user = userEvent.setup();
    mount(palette);

    const dialog = await openPalette();
    await user.type(within(dialog).getByRole('combobox'), 'chromothripsis');

    expect(within(dialog).queryAllByRole('option')).toHaveLength(0);
    expect(dialog).toHaveTextContent('Nothing matches');
  });

  it('navigates to the page under the cursor on ArrowDown then Enter', async () => {
    const user = userEvent.setup();
    mount(palette);

    const dialog = await openPalette();
    // "the" is in both page titles and in no section title, so the list is pages first.
    await user.type(within(dialog).getByRole('combobox'), 'the');
    const options = within(dialog).getAllByRole('option');
    expect(options[0]?.textContent).toContain('The callset');
    expect(options[1]?.textContent).toContain('The reads');

    await user.keyboard('{ArrowDown}');
    expect(within(dialog).getAllByRole('option')[1]).toHaveAttribute('aria-selected', 'true');

    await user.keyboard('{Enter}');

    expect(screen.getByTestId('pathname')).toHaveTextContent('/reads');
    expect(screen.queryByRole('dialog', { name: 'Jump to' })).toBeNull();
  });

  it('scrolls to a section chosen from the palette', async () => {
    const user = userEvent.setup();
    mount(palette);

    const dialog = await openPalette();
    await user.type(within(dialog).getByRole('combobox'), 'zygosity');
    await user.keyboard('{Enter}');

    expect(scrollIntoView).toHaveBeenCalledTimes(1);
    expect(jumpedTo(scrollIntoView).id).toBe('zygosity-split');
    expect(screen.queryByRole('dialog', { name: 'Jump to' })).toBeNull();
  });

  it('closes on Escape and hands focus back to the button that opened it', async () => {
    const user = userEvent.setup();
    mount(palette);

    await openPalette();
    await user.keyboard('{Escape}');

    expect(screen.queryByRole('dialog', { name: 'Jump to' })).toBeNull();
    expect(screen.getByRole('button', { name: /jump to/i })).toHaveFocus();
  });

  it('has no axe violations while open', async () => {
    const { container } = mount(palette);
    await openPalette();

    await expectNoAxeViolations(container, 'the open palette');
  });
});
