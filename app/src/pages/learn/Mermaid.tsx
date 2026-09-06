/**
 * A ```mermaid block, drawn in the browser.
 *
 * `mermaid` is a ~2.5 MB library and the dictionary has nineteen diagrams, so two rules keep
 * it cheap: it is `import()`ed (its own chunk, fetched only on this page) and a diagram is
 * only rendered once it scrolls into view. Until then — and wherever the browser cannot draw
 * it, jsdom included — the source is shown as a code block, which is what the markdown
 * shows in a plain text editor too. That fallback is why this component never throws.
 *
 * The diagrams carry their own light-paper colours (`style X fill:#ccebc5`), written for
 * GitHub's white page, so they render on a paper card in both themes rather than being
 * recoloured: the Legend under each one decodes exactly the colours the author chose.
 */

import { useEffect, useRef, useState } from 'react';

let counter = 0;

async function draw(source: string): Promise<string> {
  const mermaid = (await import('mermaid')).default;
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict',
    theme: 'base',
    fontFamily: 'Atkinson Hyperlegible Next Variable, system-ui, sans-serif',
  });
  const { svg } = await mermaid.render(`learn-mermaid-${counter++}`, source);
  return svg;
}

export function Mermaid({ source, label }: { source: string; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || svg || failed) return;
    if (typeof IntersectionObserver === 'undefined') {
      setFailed(true);
      return;
    }
    let live = true;
    const io = new IntersectionObserver((entries) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      io.disconnect();
      draw(source).then(
        (out) => live && setSvg(out),
        () => live && setFailed(true),
      );
    });
    io.observe(el);
    return () => {
      live = false;
      io.disconnect();
    };
  }, [source, svg, failed]);

  if (failed) {
    return (
      <pre className="learn-code" aria-label={`${label} (diagram source)`}>
        {source}
      </pre>
    );
  }
  return (
    <div
      ref={ref}
      role="img"
      aria-label={label}
      className="learn-paper flex min-h-[120px] items-center justify-center overflow-x-auto"
      // The SVG comes from mermaid's own renderer over source text committed in this
      // repository — no user input reaches it.
      dangerouslySetInnerHTML={svg ? { __html: svg } : undefined}
    >
      {svg ? undefined : <span className="text-micro text-chrome-400">drawing diagram…</span>}
    </div>
  );
}
