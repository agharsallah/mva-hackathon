/**
 * The figure lightbox: a rendered figure is evidence, so one of them has to be citable.
 *
 * The contract asserted here is the *shareable* half — the open figure lives in the query
 * string, so the dialog is reachable by address and not only by click — plus the modal
 * behaviour a keyboard user is entitled to: Escape closes, prev/next cycles.
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';

import type { SubmissionIteration } from '../api/types';
import submissions from '../fixtures/data/submissions.json';
import { Artifacts } from '../pages/submissions/Artifacts';

const iteration = (submissions as unknown as { iterations: SubmissionIteration[] }).iterations[0]!;

function mount(search = '') {
  return render(
    <MemoryRouter initialEntries={[`/submissions${search}`]}>
      <Artifacts iteration={iteration} source="fixture: test" />
    </MemoryRouter>,
  );
}

const dialog = () => screen.queryByRole('dialog');

afterEach(cleanup);

describe('the figure lightbox', () => {
  it('opens on a thumbnail click and writes the figure into the URL', () => {
    mount();
    expect(dialog()).toBeNull();

    const first = iteration.figures[0]!;
    fireEvent.click(screen.getByLabelText(`open figure ${first.slug}`));

    const open = dialog()!;
    expect(open).toBeTruthy();
    expect(open.getAttribute('aria-modal')).toBe('true');
    expect(open.getAttribute('aria-label')).toContain(first.slug);
    expect(open.textContent).toContain(`?figure=${first.slug}`);
    expect(open.textContent).toContain(first.path);
  });

  it('opens directly from the ?figure= parameter', () => {
    const target = iteration.figures[1]!;
    mount(`?figure=${target.slug}`);
    expect(dialog()!.getAttribute('aria-label')).toContain(target.slug);
  });

  it('closes on Escape and on a backdrop click', () => {
    mount(`?figure=${iteration.figures[0]!.slug}`);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(dialog()).toBeNull();

    mount(`?figure=${iteration.figures[0]!.slug}`);
    fireEvent.click(screen.getByTestId('figure-lightbox-backdrop'));
    expect(dialog()).toBeNull();
  });

  it('cycles through the iteration figures with prev and next', () => {
    const [a, b] = [iteration.figures[0]!, iteration.figures[1]!];
    mount(`?figure=${a.slug}`);

    fireEvent.click(screen.getByText('next →'));
    expect(dialog()!.getAttribute('aria-label')).toContain(b.slug);

    fireEvent.click(screen.getByText('← prev'));
    expect(dialog()!.getAttribute('aria-label')).toContain(a.slug);

    // Wrapping backwards from the first lands on the last, so the set is a cycle.
    fireEvent.click(screen.getByText('← prev'));
    expect(dialog()!.getAttribute('aria-label')).toContain(
      iteration.figures[iteration.figures.length - 1]!.slug,
    );
  });

  it('offers the raw PNG in a new tab and a 1:1 zoom toggle', () => {
    mount(`?figure=${iteration.figures[0]!.slug}`);
    const link = screen.getByText('open PNG in new tab') as HTMLAnchorElement;
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('href')).toContain(iteration.figures[0]!.url);

    fireEvent.click(screen.getByText('zoom 1:1'));
    expect(screen.getByText('fit to window')).toBeTruthy();
  });
});
