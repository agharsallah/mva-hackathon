/**
 * `?refresh` in the URL means "probe now, do not serve me a cached answer".
 *
 * The API caches one probe round for ~10 s and the page polls every 10 minutes, which is
 * the right default — probing costs real round trips to Postgres, MinIO and Ensembl. But
 * right after restarting a service you want the truth immediately, not on the next tick.
 * Visiting `/status?refresh` passes `refresh=true` through to the endpoint, which skips its
 * own cache, and changes the react-query key so the page fetches on arrival.
 *
 * It is a URL flag rather than a button so the forced state is linkable and survives a
 * reload — the same reasoning as every other selection in this app living in the URL.
 */

import { useSearchParams } from 'react-router-dom';

export function useRefreshRequested(): boolean {
  return useSearchParams()[0].has('refresh');
}
