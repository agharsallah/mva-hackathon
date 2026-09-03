/**
 * "Has this element been scrolled into view yet?" — the gate an expensive exhibit hangs on.
 *
 * Why a hook and not an `enabled` flag threaded through props: the decision belongs to the
 * DOM, not to the page. An exhibit that fans out 44 HTTP requests to draw one table must not
 * spend them while it is 4,000 px below the fold, and the only honest signal for "the reader
 * is about to look at this" is the element's own intersection with the viewport.
 *
 * Three properties worth knowing before using it:
 *
 * - **It latches.** Once true it stays true: this gates a fetch, and a table that unloaded
 *   itself on scroll-away would re-fetch on the way back. (`Viz3dCanvas` wants the opposite —
 *   pausing a render loop *is* reversible — which is why it owns its own observer.)
 * - **`rootMargin` pre-warms.** The default fires 300 px before the element's top edge
 *   reaches the viewport, so the request is in flight by the time the reader arrives.
 * - **No observer means visible.** In jsdom (and any environment without
 *   `IntersectionObserver`) it reports `true` immediately. The alternative — reporting
 *   `false` forever — would silently blank the exhibit in every test rather than degrade.
 */

import { type MutableRefObject, useEffect, useRef, useState } from 'react';

export function useInView<T extends Element = HTMLDivElement>(
  rootMargin = '300px',
): { ref: MutableRefObject<T | null>; inView: boolean } {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(() => typeof IntersectionObserver === 'undefined');

  useEffect(() => {
    if (inView) return;
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) setInView(true);
      },
      { rootMargin },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [inView, rootMargin]);

  return { ref, inView };
}
