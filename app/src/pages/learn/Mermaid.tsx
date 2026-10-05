/**
 * The one module allowed to import `mermaid` (see the rule in `eslint.config.js`).
 *
 * It is `import()`ed, not imported: mermaid is a large bundle and a reader who never opens a
 * chapter containing a diagram must not download it. Rendering is deferred to an effect, so
 * a failure draws the diagram's source instead of blanking the page.
 */

import { useEffect, useRef, useState } from 'react';

import { useTheme } from '../../lib/theme';

let nextId = 0;

export function Mermaid({ source }: { source: string }) {
  const theme = useTheme();
  const host = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const el = host.current;
    if (!el) return;
    void (async () => {
      try {
        const { default: mermaid } = await import('mermaid');
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'strict',
          theme: theme === 'light' ? 'default' : 'dark',
        });
        const { svg } = await mermaid.render(`mermaid-${(nextId += 1)}`, source);
        if (!cancelled) el.innerHTML = svg;
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [source, theme]);

  if (failed) {
    return (
      <pre className="overflow-x-auto rounded-control border border-line-soft bg-well p-3 font-mono text-micro text-chrome-400">
        {source}
      </pre>
    );
  }
  return <div ref={host} className="overflow-x-auto" />;
}

export default Mermaid;
