/**
 * The two controls on a dependency card, tested through the DOM because that is where
 * their whole value is: masked-by-default has to be true of what is *rendered*, and
 * "re-probe this one service" has to send one id, not seven.
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { DependencyCheck } from '../api/types';
import { DependencyCard } from '../pages/status/DependencyCard';

const CHECK: DependencyCheck = {
  id: 'object-store',
  name: 'Object store (MinIO/S3)',
  kind: 'internal',
  status: 'down',
  latency_ms: 12,
  timeout_ms: 10_000,
  checked_at: '2026-09-03T11:58:00+00:00',
  detail: 'cannot reach the object store at store.example:9012',
  remedy: 'open the tunnel:  ssh -N -L 9012:store.example:9012 you@server.example',
  powers: ['Reads'],
  endpoint: 'http://store.example:9012/mva',
};

function mount(overrides: Partial<Parameters<typeof DependencyCard>[0]> = {}) {
  const onReprobe = vi.fn();
  const view = render(
    <DependencyCard
      check={CHECK}
      origin="api"
      revealAll={false}
      reprobing={false}
      onReprobe={onReprobe}
      {...overrides}
    />,
  );
  return { onReprobe, view };
}

describe('DependencyCard', () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  it('renders no host or port until asked', () => {
    const { view } = mount();
    const text = view.container.textContent ?? '';
    expect(text).not.toContain('store.example');
    expect(text).not.toContain('9012'); // not in the endpoint, the detail, or the remedy
    expect(text).toContain('••••');
  });

  it("reveals this card's address on show, and hides it again", async () => {
    const user = userEvent.setup();
    const { view } = mount();
    await user.click(screen.getByRole('button', { name: /show the address/i }));
    expect(view.container.textContent).toContain('store.example:9012');
    await user.click(screen.getByRole('button', { name: /hide the address/i }));
    expect(view.container.textContent).not.toContain('store.example:9012');
  });

  it('offers no per-card toggle while the board reveals everything', () => {
    const { view } = mount({ revealAll: true });
    expect(screen.queryByRole('button', { name: /the address/i })).toBeNull();
    expect(view.container.textContent).toContain('store.example:9012');
  });

  it('re-probes exactly this check', async () => {
    const user = userEvent.setup();
    const { onReprobe } = mount();
    await user.click(screen.getByRole('button', { name: /re-probe Object store/i }));
    expect(onReprobe).toHaveBeenCalledTimes(1);
    expect(onReprobe).toHaveBeenCalledWith('object-store');
  });

  it('disables its own button while that probe is in flight', () => {
    mount({ reprobing: true });
    expect(screen.getByRole('button', { name: /re-probe Object store/i })).toBeDisabled();
  });

  it('disables re-probing in fixture mode, where there is no API to probe', () => {
    mount({ origin: 'fixture' });
    expect(screen.getByRole('button', { name: /re-probe Object store/i })).toBeDisabled();
  });

  it('says what the budget was, next to the latency it was measured against', () => {
    const { view } = mount();
    expect(view.container.textContent).toContain('12 ms');
    expect(view.container.textContent).toContain('budget 10 s');
  });

  it('states how old this row is, so a partial re-probe cannot mislead', () => {
    const { view } = mount({
      check: { ...CHECK, checked_at: new Date(Date.now() - 600_000).toISOString() },
    });
    expect(view.container.textContent).toContain('10 m ago');
  });
});
