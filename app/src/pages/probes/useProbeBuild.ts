/**
 * POST the draft payload to `/api/probe/build`.
 *
 * There is no fixture path for a POST (`client.post` has none by design — see
 * `api/client.ts`), and inventing one here would be worse than useless: a builder that
 * "validates" against a stub would tell you a file is safe to spend a submission on
 * without any rule having run. So a down API is reported as a down API, and the exhibit
 * shows nothing where a verdict would be.
 */

import { useCallback, useState } from 'react';

import { post } from '../../api/client';
import type { ProbeBuildRequest, ProbeBuildResult } from '../../api/types/probebuild';

export interface ProbeBuildState {
  result: ProbeBuildResult | null;
  error: Error | null;
  building: boolean;
  build: (request: ProbeBuildRequest) => void;
  clear: () => void;
}

export function useProbeBuild(): ProbeBuildState {
  const [result, setResult] = useState<ProbeBuildResult | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [building, setBuilding] = useState(false);

  const build = useCallback((request: ProbeBuildRequest) => {
    setError(null);
    setBuilding(true);
    post<ProbeBuildResult>('/api/probe/build', request)
      .then(setResult)
      .catch((err: Error) => {
        setResult(null);
        setError(err);
      })
      .finally(() => setBuilding(false));
  }, []);

  const clear = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return { result, error, building, build, clear };
}

/** Save the built CSV without a server round trip: a Blob URL the browser downloads. */
export function downloadCsv(csv: string, filename: string): void {
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
