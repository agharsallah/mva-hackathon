/**
 * Failure classification — the data half of `ErrorCard`, kept out of the component file so
 * that file exports only components (react-refresh). One failure per thing a reader can
 * actually do about it, each with its own explanation and remedy; `unknown` is the honest
 * fallback. The order of the branches is the classification: the specific readings come
 * before the generic status-range ones.
 */

import { API_LABEL, ApiError, isRouteMissing } from '../api/client';

export type FailureKind =
  | 'unreachable'
  | 'route-missing'
  | 'not-found'
  | 'upstream-down'
  | 'unauthorized'
  | 'bad-request'
  | 'server-fault'
  | 'aborted'
  | 'unknown';

export interface Failure {
  kind: FailureKind;
  title: string;
  /** One or two plain sentences on what this means for the reader. */
  explain: string;
  /** What to do about it, if there is something to do. */
  remedy?: string;
  /** A command that fixes it, shown in a well. */
  command?: string;
}

/** Turn an error into the one of six failures the reader can actually act on. */
export function classifyError(error: Error): Failure {
  const api = error instanceof ApiError ? error : null;
  if (api?.isUpstreamDown) {
    return {
      kind: 'upstream-down',
      title: 'An upstream service is not answering',
      explain:
        'The API is up, but a service behind it did not respond. Everything that does not need that service keeps working.',
      remedy: 'Check the dependency status in the footer; its card names the remedy.',
    };
  }
  // Two different 404s, and telling a reader the wrong one costs them the whole debugging
  // session. `isRouteMissing` is the narrow one the fetch layer already uses: FastAPI's own
  // `{"detail": "Not Found"}` for a path nothing routes, which really does mean the process
  // predates this build. An endpoint that ran and found nothing answers with its own
  // sentence ("no such record"), and telling that reader to restart the API sends them to
  // fix a server that is working. Seen for real: an API started from the wrong directory
  // resolved every repo-relative reference path to nothing, and a page blamed a stale process.
  if (isRouteMissing(error)) {
    return {
      kind: 'route-missing',
      title: 'The running API does not have this endpoint',
      explain:
        'The API process is older than this app: this page asks for a route that was added after it started.',
      remedy: 'Restart the API so it picks up the new routes.',
    };
  }
  if (api?.status === 404) {
    return {
      kind: 'not-found',
      title: 'The API has no data for this selection',
      explain: `The endpoint answered, and nothing matched: ${api.message}`,
      remedy:
        'Pick another selection above. If this one should exist, the table behind it may not be built — the dependency status says which inputs the API actually loaded.',
    };
  }
  // Before the generic 4xx: a 401 is not a bad parameter, and reading it as one sent the
  // reader off to change a selection that was never the problem. It means this build is
  // talking to an API that requires an API key, and a browser has no way to hold that
  // token — only the server-side proxy does. Seen for real: a dev build pointed straight at
  // the deployed API answered 401 on every panel while the header still said "API up",
  // because `/health` is deliberately unauthenticated.
  if (api && (api.status === 401 || api.status === 403)) {
    return {
      kind: 'unauthorized',
      title: 'This API needs a token, and a browser cannot hold one',
      explain:
        'The API answered, but refused without a valid X-API-Key. Only the hosted deployment can send it — the token lives in the server-side proxy, never in the bundle, which is the whole point of it.',
      remedy:
        'Point this build at a local API instead (leave VITE_API_URL unset), or run the proxy locally with `vercel dev`. Never put the token in VITE_API_URL or any VITE_ variable — Vite inlines those into the bundle.',
    };
  }
  if (api && api.status >= 400 && api.status < 500) {
    return {
      kind: 'bad-request',
      title: 'The API rejected this query',
      explain:
        'The request reached the API but its parameters were refused. Usually a selection in the URL no longer matches what the data offers.',
      remedy: 'Change the selection above, or reset the page to its defaults.',
    };
  }
  if (api && api.status >= 500) {
    return {
      kind: 'server-fault',
      title: 'The API failed while answering',
      explain: 'The API accepted the request and then hit an error of its own.',
      remedy: 'The API log has the traceback. The dependency status shows whether one is down.',
    };
  }
  if (error.name === 'AbortError') {
    return {
      kind: 'aborted',
      title: 'The request was cancelled',
      explain: 'The page moved on before this answer arrived.',
      remedy: 'Retry to ask again.',
    };
  }
  if (error instanceof TypeError) {
    return {
      kind: 'unreachable',
      title: `No API answered at ${API_LABEL}`,
      explain:
        'Either the API is not running, or the browser blocked the request (a CORS refusal looks identical from here; the console has the reason).',
      remedy: 'Start the API, or point VITE_API_URL at one that is running.',
    };
  }
  return {
    kind: 'unknown',
    title: 'Request failed',
    explain: 'Something went wrong that this page did not anticipate.',
    remedy: 'Retry; if it persists, the details below are what to report.',
  };
}
