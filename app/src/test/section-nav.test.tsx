/**
 * In-page navigation, half one: the "On this page" rail and the small-screen "Jump to
 * section" select. The ⌘K palette — the third reader of the same store — is
 * `command-palette.test.tsx`; the shared tree, the jsdom stubs and why they are needed are
 * in `sectionNavHarness.tsx`.
 *
 * Both components are driven by the section registry (`lib/sections.ts`) that a mounted
 * `Section` announces itself to, and neither is wired up by a page — which is exactly why
 * they need a test: a page can silently stop appearing in the rail (a renamed anchor, a
 * `Section` that no longer registers) with nothing else on screen changing.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Section } from '../components/Controls';
import { JourneyProvider } from '../components/journey';
import { JumpToSection, OnThisPage } from '../components/OnThisPage';
import {
  expectNoAxeViolations,
  GROUPS,
  jumpedTo,
  mount,
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

const rail = (
  <>
    {sections}
    <OnThisPage />
  </>
);

// ── the rail ────────────────────────────────────────────────────────────────────────────

describe('the "On this page" rail', () => {
  it('lists every mounted section, in document order, as an anchor to its id', async () => {
    mount(rail);

    const nav = await screen.findByRole('navigation', { name: 'On this page' });
    const links = within(nav).getAllByRole('link');

    expect(links.map((a) => a.textContent)).toEqual([
      'Coverage by chromosome',
      'Zygosity split',
      'Header fields',
      'Back to top',
    ]);
    expect(links[0]?.getAttribute('href')).toBe('#coverage-by-chromosome');
    expect(links[1]?.getAttribute('href')).toBe('#zygosity-split');
  });

  it('keeps an explicit id as the anchor instead of slugifying the title', async () => {
    mount(rail);

    const nav = await screen.findByRole('navigation', { name: 'On this page' });
    expect(within(nav).getByRole('link', { name: 'Header fields' }).getAttribute('href')).toBe(
      '#declared-fields',
    );
    // …and the section itself carries that id, so the anchor resolves.
    expect(document.getElementById('declared-fields')).not.toBeNull();
  });

  it('clicking an entry scrolls to that section instead of following the href', async () => {
    const user = userEvent.setup();
    mount(rail);

    const nav = await screen.findByRole('navigation', { name: 'On this page' });
    await user.click(within(nav).getByRole('link', { name: 'Zygosity split' }));

    expect(scrollIntoView).toHaveBeenCalledTimes(1);
    expect(jumpedTo(scrollIntoView).id).toBe('zygosity-split');
    expect(window.location.hash).toBe('#zygosity-split');
  });

  it('renders nothing with a single section — a one-item rail is noise', () => {
    mount(
      <>
        <Section title="Only one">a</Section>
        <OnThisPage />
      </>,
    );

    expect(screen.queryByRole('navigation', { name: 'On this page' })).toBeNull();
  });

  it('drops a section from the rail when it unmounts', async () => {
    function Tree({ showThird }: { showThird: boolean }) {
      return (
        <>
          <Section title="Coverage by chromosome">a</Section>
          <Section title="Zygosity split">b</Section>
          {showThird && <Section title="Header fields">c</Section>}
          <OnThisPage />
        </>
      );
    }
    const wrap = (ui: React.ReactNode) => (
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <JourneyProvider groups={GROUPS}>
            <main>{ui}</main>
          </JourneyProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );

    const { rerender } = render(wrap(<Tree showThird />));
    const nav = await screen.findByRole('navigation', { name: 'On this page' });
    expect(within(nav).queryByRole('link', { name: 'Header fields' })).not.toBeNull();

    rerender(wrap(<Tree showThird={false} />));

    expect(
      within(screen.getByRole('navigation', { name: 'On this page' })).queryByRole('link', {
        name: 'Header fields',
      }),
    ).toBeNull();
  });

  it('has no axe violations', async () => {
    const { container } = mount(rail);
    await screen.findByRole('navigation', { name: 'On this page' });

    await expectNoAxeViolations(container, 'the rail');
  });
});

// ── the jump select ─────────────────────────────────────────────────────────────────────

const jumpSelect = (
  <>
    {sections}
    <JumpToSection />
  </>
);

describe('JumpToSection', () => {
  it('offers one option per section behind a labelled select', () => {
    mount(jumpSelect);

    const select = screen.getByRole('combobox', { name: 'Jump to section' });
    const options = within(select).getAllByRole('option');

    expect(options.map((o) => o.textContent)).toEqual([
      'a section on this page',
      'Coverage by chromosome',
      'Zygosity split',
      'Header fields',
    ]);
    // The placeholder is not a destination.
    expect(options[0]).toBeDisabled();
    expect((options[3] as HTMLOptionElement).value).toBe('declared-fields');
  });

  it('scrolls to the chosen section', async () => {
    const user = userEvent.setup();
    mount(jumpSelect);

    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Jump to section' }),
      'declared-fields',
    );

    expect(scrollIntoView).toHaveBeenCalledTimes(1);
    expect(jumpedTo(scrollIntoView).id).toBe('declared-fields');
  });

  it('renders nothing with a single section', () => {
    mount(
      <>
        <Section title="Only one">a</Section>
        <JumpToSection />
      </>,
    );

    expect(screen.queryByRole('combobox', { name: 'Jump to section' })).toBeNull();
  });
});
