import { useState } from 'react';

import type { DependencyCheck } from '../../api/types';
import { Callout, FieldList } from '../../components';
import { int, iso } from '../../lib/format';
import { endpointFor } from './configured';
import { maskAddresses, maskOptional } from './redact';
import { agoLabel, probeAge, statusLabel, statusTone } from './verdict';

/**
 * One card per check. This is the point of the page: a broken dependency has to leave
 * behind a message a developer can act on, not a red dot. So the card's `remedy` —
 * multi-line shell advice from the endpoint — is rendered as preformatted, wrapping text
 * inside the card itself, not tucked behind a hover or a link.
 *
 * The card also carries the two controls that belong to *this* dependency rather than to
 * the board: re-probe just this one, and reveal just this one's address.
 */

/** ms → the unit a human reads: `891 ms`, `12 s`. */
function duration(ms: number): string {
  return ms < 1000 ? `${int(ms)} ms` : `${(ms / 1000).toFixed(ms % 1000 === 0 ? 0 : 1)} s`;
}

function ReprobeButton({
  name,
  running,
  disabled,
  onClick,
}: {
  name: string;
  running: boolean;
  /** Fixture mode: there is no API to probe, so the button would be a lie. */
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={running || disabled}
      aria-label={`re-probe ${name}`}
      title={disabled ? 'fixture mode — no API to probe' : `probe ${name} again, and only ${name}`}
      className="rounded-control border border-line-strong bg-chrome-900/70 px-2 py-0.5 text-micro text-chrome-300 transition hover:bg-chrome-800 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {running ? 'probing…' : 're-probe'}
    </button>
  );
}

export interface DependencyCardProps {
  check: DependencyCheck;
  origin: 'api' | 'fixture';
  /** Board-level "reveal addresses". When on, the card's own toggle is not offered. */
  revealAll: boolean;
  reprobing: boolean;
  onReprobe: (id: string) => void;
}

export function DependencyCard({
  check,
  origin,
  revealAll,
  reprobing,
  onReprobe,
}: DependencyCardProps) {
  const [revealed, setRevealed] = useState(false);
  const masked = !(revealAll || revealed);
  const tone = statusTone(check.status);
  // Offline, the committed fixture cannot know this checkout's hosts, so the address comes
  // from the repo-root .env instead and says so — a loopback placeholder would be a lie
  // for anyone whose services run on a server.
  const endpoint = endpointFor(check.id, check.endpoint, origin);
  const address = endpoint
    ? `${masked ? maskAddresses(endpoint.value) : endpoint.value}${
        endpoint.fromEnv ? '  (configured in .env)' : ''
      }`
    : '—';
  const age = check.checked_at ? probeAge(check.checked_at) : null;
  const budget = Number.isFinite(check.timeout_ms) ? duration(check.timeout_ms) : null;

  const fields = [
    {
      key: 'latency',
      label: 'latency',
      // `timeout_ms` and `checked_at` arrive from an API newer than this field pair. A
      // long-running server predates the app that talks to it — the same skew
      // `client.ts` handles for a missing route — so both degrade instead of rendering
      // `NaN` while someone restarts the API.
      value:
        check.latency_ms === null
          ? '—'
          : [duration(check.latency_ms), budget && `budget ${budget}`].filter(Boolean).join(' · '),
    },
    {
      key: 'probed',
      label: 'probed',
      value: age === null ? '—' : `${iso(check.checked_at)} · ${agoLabel(age)}`,
    },
    {
      key: 'endpoint',
      label: 'endpoint',
      value: (
        <span className="inline-flex flex-wrap items-baseline gap-2">
          <span>{address}</span>
          {endpoint && !revealAll && (
            <button
              onClick={() => setRevealed((v) => !v)}
              aria-label={`${revealed ? 'hide' : 'show'} the address for ${check.name}`}
              className="rounded-pill border border-line-strong px-1 font-sans text-micro text-chrome-400 hover:text-chrome-200"
            >
              {revealed ? 'hide' : 'show'}
            </button>
          )}
        </span>
      ),
    },
    {
      key: 'powers',
      label: 'powers',
      value: check.powers.length > 0 ? check.powers.join(', ') : '— (no page depends on this)',
    },
  ];

  return (
    <Callout
      tone={tone}
      title={`${check.name} — ${statusLabel(check.status)}`}
      action={
        <ReprobeButton
          name={check.name}
          running={reprobing}
          disabled={origin === 'fixture'}
          onClick={() => onReprobe(check.id)}
        />
      }
    >
      <div className="space-y-3">
        <p>{masked ? maskAddresses(check.detail) : check.detail}</p>
        <FieldList fields={fields} labelWidth={64} />
        {check.remedy && (
          <div>
            <div className="text-xs font-semibold text-chrome-200">
              {check.status === 'skipped' ? 'How to enable it (optional)' : 'Remedy'}
            </div>
            <pre className="mt-1 max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded-control border border-line-strong bg-black/25 p-3 font-mono text-micro leading-relaxed text-chrome-100">
              {maskOptional(check.remedy, masked)}
            </pre>
            {masked && /[•]/.test(maskOptional(check.remedy, masked) ?? '') && (
              <p className="mt-1 text-micro text-chrome-600">
                Addresses in this remedy are hidden — reveal them to copy the commands.
              </p>
            )}
          </div>
        )}
      </div>
    </Callout>
  );
}
