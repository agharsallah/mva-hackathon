import { useState } from 'react';

import { API_URL } from '../../api/client';
import type { StepFigure } from '../../api/types';
import { FigureLightbox } from '../../components/FigureLightbox';
import { bytes as fmtBytes } from '../../lib/format';
import { cx } from '../../lib/ui';

/**
 * Every figure a step drew, shown rather than named.
 *
 * `/api/steps` used to list figure *filenames*, so the ~75 rendered exhibits under
 * `figures/` existed only on the filesystem of whoever ran the renderer. The API now serves
 * the bytes, and this strip is where the page reads them: an image inline, an interactive
 * Plotly page as a link, because an `<iframe>` of a 3 MB self-contained chart is not a
 * thumbnail.
 *
 * The open figure is written to the address bar by the caller, so one link cites one figure.
 *
 * **Every figure carries its reading.** A chart with no caption is decoration, and this
 * repository had seventy of them; `reads` says what the image shows and `means` says what it
 * is evidence for, written beside the step and validated by `tools/check_step_narrative.py`,
 * which refuses a step that drew a figure nobody read.
 */

/** An image can be a thumbnail; an HTML or JSON artifact has to be opened. */
const INLINE = new Set(['png', 'svg']);

function src(url: string): string {
  return url.startsWith('/') ? `${API_URL}${url}` : url;
}

export function FigureStrip({ figures, origin }: { figures: StepFigure[]; origin?: string }) {
  const [open, setOpen] = useState<string | null>(null);
  const images = figures.filter((f) => INLINE.has(f.kind));
  const others = figures.filter((f) => !INLINE.has(f.kind));

  if (figures.length === 0) {
    return (
      <p className="text-micro text-chrome-500">
        No figure was drawn for this step — a true statement about it, not a missing file.
      </p>
    );
  }

  // Offline there is no API to serve the bytes, so the strip names the files instead of
  // rendering a grid of broken images and claiming the figures are missing.
  if (origin === 'fixture') {
    return (
      <div className="space-y-1">
        <p className="text-micro text-chrome-400">
          {figures.length} {figures.length === 1 ? 'figure was' : 'figures were'} rendered for this
          step. The API serves the bytes; this session is on fixture data, so they are named here
          rather than shown.
        </p>
        <ul className="flex flex-wrap gap-2">
          {figures.map((f) => (
            <li
              key={f.name}
              className="rounded-control border border-line bg-well px-2 py-1 font-mono text-micro text-chrome-400"
            >
              {f.path}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {images.length > 0 && (
        <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {images.map((f) => (
            <li key={f.name} className="space-y-2 rounded-card border border-line bg-well p-2">
              <button
                type="button"
                onClick={() => setOpen(f.name)}
                aria-label={`open figure ${f.title}`}
                className="block w-full cursor-zoom-in focus:outline-none focus-visible:ring-1 focus-visible:ring-focus"
              >
                <img
                  src={src(f.url)}
                  alt={f.caption?.reads ?? f.title}
                  loading="lazy"
                  className="w-full rounded-control border border-line-soft"
                />
              </button>
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-micro font-semibold text-chrome-200">{f.title}</span>
                <span className="font-mono text-micro text-chrome-500">{fmtBytes(f.bytes)}</span>
              </div>
              {f.caption ? (
                <dl className="space-y-1 text-micro leading-relaxed">
                  <div>
                    <dt className="inline text-chrome-500">What it shows. </dt>
                    <dd className="inline text-chrome-300">{f.caption.reads}</dd>
                  </div>
                  <div>
                    <dt className="inline text-chrome-500">What it means. </dt>
                    <dd className="inline text-chrome-300">{f.caption.means}</dd>
                  </div>
                  {f.caption.source && (
                    <div className="font-mono break-all text-chrome-600">{f.caption.source}</div>
                  )}
                </dl>
              ) : (
                <p className="text-micro text-chrome-500">
                  No reading is written for this figure yet.
                </p>
              )}
            </li>
          ))}
        </ul>
      )}

      {others.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {others.map((f) => (
            <li key={f.name} className="max-w-md">
              <a
                href={src(f.url)}
                target="_blank"
                rel="noreferrer"
                className={cx(
                  'flex items-baseline gap-2 rounded-control border border-line bg-well px-2 py-1',
                  'text-micro text-chrome-300 transition hover:border-line-strong hover:text-chrome-50',
                )}
              >
                <span className="font-mono text-chrome-500">{f.kind}</span>
                {f.title}
              </a>
              {f.caption && (
                <div className="space-y-0.5 px-2 pt-1 text-micro leading-relaxed text-chrome-400">
                  <p>{f.caption.reads}</p>
                  <p className="text-chrome-300">{f.caption.means}</p>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <FigureLightbox
        figures={images}
        slug={open}
        onSelect={setOpen}
        linkFor={(slug) => `${window.location.origin}${window.location.pathname}?figure=${slug}`}
      />
    </div>
  );
}
