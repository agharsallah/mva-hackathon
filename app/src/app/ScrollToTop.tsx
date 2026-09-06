/**
 * Scrolls the window to the top on every route change, the behaviour a multi-page site
 * gets for free and a client-side router does not: without this, navigating from the
 * bottom of a long page (e.g. Panel) to another page lands the reader mid-scroll on
 * content they never asked for.
 *
 * Skipped when the new location carries a `hash`: that is a deep link to a specific
 * anchor (`/learn#allele`, `/provenance#reference`) and the target page (or the browser,
 * on a fresh load) is responsible for scrolling to it — see `Learn.tsx`'s own
 * hash-driven `scrollIntoView`. Forcing the top here would fight that.
 */

import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

export function ScrollToTop() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (hash) return;
    window.scrollTo(0, 0);
  }, [pathname, hash]);
  return null;
}
