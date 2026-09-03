import { act, render, screen } from '@testing-library/react';
import { BrowserRouter, MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';

import { useUrlKnownOption } from './useUrlKnownOption';

const VOCAB = ['BUB1B', 'TP53'] as const;
type Gene = (typeof VOCAB)[number];

function Probe({ options = VOCAB }: { options?: readonly Gene[] }) {
  const [gene] = useUrlKnownOption<Gene>(
    'gene',
    'BUB1B',
    options,
    (raw) => raw.toUpperCase() as Gene,
  );
  return <output>{gene}</output>;
}

afterEach(() => window.history.replaceState(null, '', '/'));

describe('useUrlKnownOption with a normaliser', () => {
  it('resolves a lower-case spelling to the vocabulary instead of the fallback', () => {
    render(
      <MemoryRouter initialEntries={['/panel?gene=tp53']}>
        <Probe />
      </MemoryRouter>,
    );
    expect(screen.getByRole('status')).toHaveTextContent('TP53');
  });

  it('leaves the URL alone while the vocabulary has not arrived', () => {
    window.history.replaceState(null, '', '/panel?gene=tp53&other=1');
    render(
      <BrowserRouter>
        <Probe options={[]} />
      </BrowserRouter>,
    );
    expect(window.location.search).toBe('?gene=tp53&other=1');
  });

  it('rewrites the address bar to the canonical spelling once the vocabulary confirms it', () => {
    window.history.replaceState(null, '', '/panel?gene=tp53&other=1');
    act(() => {
      render(
        <BrowserRouter>
          <Probe />
        </BrowserRouter>,
      );
    });
    const params = new URLSearchParams(window.location.search);
    expect(params.get('gene')).toBe('TP53');
    // Sibling keys survive: the setter merges, never replaces.
    expect(params.get('other')).toBe('1');
  });
});
