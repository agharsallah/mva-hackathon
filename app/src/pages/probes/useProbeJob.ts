/**
 * Submit a k-mer count job and follow it to completion.
 *
 * The reads API is asynchronous: POST returns a job, and progress is read with a
 * long-poll (`/api/jobs/{id}/wait?timeout=60`) that blocks server-side until the state
 * changes or the timeout expires. That is cheaper and lower-latency than client polling,
 * so the loop below simply re-issues the wait until the job reaches a terminal state.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, getBare, post } from '../../api/client';
import type { CountJob, ProbeSpec } from '../../api/types';

const TERMINAL = new Set(['done', 'failed', 'cancelled', 'lost']);
const WAIT_TIMEOUT = 60;

export interface ProbeJobState {
  job: CountJob | null;
  error: Error | null;
  submitting: boolean;
  waiting: boolean;
  submit: (probes: ProbeSpec[]) => void;
  cancel: () => void;
  reset: () => void;
}

export function useProbeJob(): ProbeJobState {
  const [job, setJob] = useState<CountJob | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const abandoned = useRef(false);

  useEffect(() => () => void (abandoned.current = true), []);

  const follow = useCallback(async (id: string) => {
    setWaiting(true);
    try {
      for (;;) {
        if (abandoned.current) return;
        const next = await getBare<CountJob>(`/api/jobs/${id}/wait`, { timeout: WAIT_TIMEOUT });
        if (abandoned.current) return;
        setJob(next);
        if (TERMINAL.has(next.state)) return;
      }
    } catch (err) {
      if (!abandoned.current) setError(err as Error);
    } finally {
      if (!abandoned.current) setWaiting(false);
    }
  }, []);

  const submit = useCallback(
    (probes: ProbeSpec[]) => {
      setError(null);
      setJob(null);
      setSubmitting(true);
      post<CountJob>('/api/probe/count', { probes })
        .then((created) => {
          setJob(created);
          if (!TERMINAL.has(created.state)) void follow(created.id);
        })
        .catch((err: Error) => setError(err))
        .finally(() => setSubmitting(false));
    },
    [follow],
  );

  const cancel = useCallback(() => {
    if (!job) return;
    post<CountJob>(`/api/jobs/${job.id}/cancel`)
      .then(setJob)
      .catch((err: Error) => setError(err));
  }, [job]);

  const reset = useCallback(() => {
    setJob(null);
    setError(null);
  }, []);

  return { job, error, submitting, waiting, submit, cancel, reset };
}

/** True when the failure is "the reads API upstream is down", which needs its own banner. */
export function isUpstreamDown(err: Error | null): boolean {
  return err instanceof ApiError && err.isUpstreamDown;
}

// --- probe text parsing ----------------------------------------------------

export interface ParsedProbe extends ProbeSpec {
  line: number;
  valid: boolean;
  problem?: string;
}

/**
 * One probe per line: `name<whitespace>SEQUENCE`, or just `SEQUENCE`.
 * Blank lines and `#` comments are ignored.
 */
export function parseProbes(text: string): ParsedProbe[] {
  const out: ParsedProbe[] = [];
  text.split('\n').forEach((raw, i) => {
    const line = raw.trim();
    if (!line || line.startsWith('#')) return;
    const parts = line.split(/[\s,\t]+/).filter(Boolean);
    const sequence = (parts.length > 1 ? parts[parts.length - 1] : parts[0]).toUpperCase();
    const name = parts.length > 1 ? parts.slice(0, -1).join('_') : `probe_${out.length + 1}`;
    let problem: string | undefined;
    if (!/^[ACGT]+$/.test(sequence)) problem = 'sequence must be A, C, G, T only';
    else if (sequence.length < 12) problem = 'too short — under 12 bp matches by chance';
    else if (sequence.length > 200) problem = 'too long — over 200 bp';
    out.push({ line: i + 1, name, sequence, valid: !problem, problem });
  });
  return out;
}
