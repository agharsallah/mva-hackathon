/**
 * The one React component that owns a WebGL canvas.
 *
 * Three constraints shaped it, all of them things the repo's gates enforce:
 *
 *  1. **No `onClick` on the `<canvas>`.** `jsx-a11y/click-events-have-key-events` and
 *     `no-static-element-interactions` are warnings, and CI runs `lint:strict
 *     --max-warnings 0`, so a warning is a failed build. Pointer listeners are attached
 *     inside `core/viewer.ts` through the ref, which jsx-a11y does not inspect — and the
 *     keyboard path is `SceneFallback`'s button list, which is a better affordance anyway.
 *  2. **`role="img"` + a generated `aria-label`.** `src/test/a11y.test.tsx` axe-audits every
 *     module, and a canvas with no accessible name fails `role-img-alt`. The label is
 *     `describeScene(scene).text` — the same sentence the AI export and the fallback use.
 *  3. **three is never imported here.** `core/loadThree.ts` owns the dynamic import, so this
 *     component renders (and the whole page tests) with three absent.
 *
 * Everything that changes per *frame* — the render loop, the link labels, the highlight rings —
 * lives in `core/viewer.ts` and never touches React state. Hover is the one exception, and it is
 * bounded: the viewer reports a hit at pointer rate, but `onHover` below sets state **only when
 * the hovered datum id changes**, so a pointer sweep across one sphere is one re-render, not
 * sixty. The tooltip's *position* is written straight to the DOM node by a ref for the same
 * reason.
 */

import { useEffect, useMemo, useRef, useState } from 'react';

import { toGeometry } from '../adapters';
import { poseDistance } from '../core/camera';
import { hasWebGL } from '../core/capability';
import { loadThreeBundle } from '../core/loadThree';
import { datumById, idAtHit, selectionAt } from '../core/pick';
import { createViewer, type Viewer } from '../core/viewer';
import { describeDatumLine, describeScene } from '../spec/describe';
import type { CameraPose3D, Viz3dCanvasProps } from '../spec/types';
import { SceneFallback } from './SceneFallback';

interface HoverState {
  id: string;
}

export function Viz3dCanvas({
  scene,
  height = 420,
  highlighted = [],
  onSelect,
  view = 'iso',
  autoRotate = true,
  label,
  pose,
  onPose,
  refitKey,
}: Viz3dCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'failed'>('loading');
  const [hover, setHover] = useState<HoverState | null>(null);

  const webgl = useMemo(() => hasWebGL(), []);
  const buffers = useMemo(() => toGeometry(scene), [scene]);
  const description = useMemo(() => describeScene(scene, highlighted), [scene, highlighted]);
  const reduced = useReducedMotion();
  const spin = autoRotate && !reduced;

  // Live refs so the viewer's callbacks always see the current scene without the viewer
  // having to be torn down and rebuilt on every prop change.
  const live = useRef({ scene, buffers, onSelect, highlighted, view, spin, onPose, pose });
  live.current = { scene, buffers, onSelect, highlighted, view, spin, onPose, pose };

  /**
   * The last pose this canvas either reported or was told to adopt — the echo guard. Without
   * it, two canvases sharing one pose prop each re-apply what the other just sent, and the
   * pair jitters instead of moving together.
   */
  const mirrored = useRef<CameraPose3D | null>(null);

  useEffect(() => {
    if (!webgl) return;
    let cancelled = false;
    loadThreeBundle()
      .then((bundle) => {
        const canvas = canvasRef.current;
        if (cancelled || !canvas) return;
        const viewer = createViewer(bundle, {
          canvas,
          overlay: overlayRef.current,
          onPick: (hit) =>
            live.current.onSelect?.(
              hit
                ? selectionAt(live.current.scene, live.current.buffers, hit.source, hit.index)
                : null,
            ),
          onPoseChange: (next) => {
            mirrored.current = next;
            live.current.onPose?.(next);
          },
          onHover: (hit, at) => {
            const id = hit ? idAtHit(live.current.buffers, hit.source, hit.index) : null;
            // Position first, as a transform on the existing node: no React involved, so the
            // tooltip tracks the pointer at pointer rate for free.
            const tooltip = tooltipRef.current;
            if (tooltip && id) {
              const box = canvas.getBoundingClientRect();
              tooltip.style.transform = `translate(${at.x - box.left + 12}px, ${at.y - box.top + 12}px)`;
            }
            // State only on a *change of datum*. Re-rendering the tree on every pointermove
            // over the same sphere is what the module note above promises not to do.
            setHover((prev) => (prev?.id === id ? prev : id ? { id } : null));
          },
        });
        viewerRef.current = viewer;
        viewer.setGeometry(live.current.buffers);
        viewer.setHighlight(live.current.highlighted);
        viewer.setView(live.current.view);
        viewer.setAutoRotate(live.current.spin);
        setStatus('ready');
        // A controlled `pose` is deliberately NOT applied here: `setView` above has just
        // fitted the camera to the preset, and the `[pose, status]` effect below is declared
        // after the `view` effect, so it runs last and a shared pose wins over the fit. Doing
        // it here instead would be overwritten by that effect's first pass on `ready`.
      })
      .catch(() => {
        if (!cancelled) setStatus('failed');
      });
    return () => {
      cancelled = true;
      viewerRef.current?.dispose();
      viewerRef.current = null;
    };
  }, [webgl]);

  useEffect(() => void viewerRef.current?.setGeometry(buffers), [buffers, status]);
  useEffect(() => void viewerRef.current?.setHighlight(highlighted), [highlighted, status]);
  // `refitKey` is in the deps, not the body: bumping it re-applies the same preset, which is
  // what a "reset the camera" gesture means. See `Viz3dCanvasProps.refitKey`.
  useEffect(() => void viewerRef.current?.setView(view), [view, refitKey, status]);
  useEffect(() => void viewerRef.current?.setAutoRotate(spin), [spin, status]);

  // Controlled pose. Ignored when it is (within the reporting tolerance) the pose this canvas
  // itself last emitted — see `mirrored`.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !pose) return;
    if (mirrored.current && poseDistance(pose, mirrored.current) < 1e-4) return;
    mirrored.current = pose;
    viewer.setPose(pose);
  }, [pose, status]);

  // Auto-rotate is an invitation, not a behaviour: the first touch of the scene stops it.
  //
  // Armed on `ready`, not on mount. `{ once: true }` consumes the listener on the first event,
  // and until three resolves there is no viewer to tell — so a pointerdown during the loading
  // window used to eat the listener and leave the scene spinning under the reader's hand for
  // the rest of the session.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || status !== 'ready') return;
    const stop = () => viewerRef.current?.setAutoRotate(false);
    canvas.addEventListener('pointerdown', stop, { once: true });
    canvas.addEventListener('wheel', stop, { once: true, passive: true });
    return () => {
      canvas.removeEventListener('pointerdown', stop);
      canvas.removeEventListener('wheel', stop);
    };
  }, [status]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => viewerRef.current?.resize());
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [status]);

  /**
   * A canvas nobody can see does not render.
   *
   * One exhibit per page made this free; a page with three (the protein explorer plus the two
   * canvases of the side-by-side comparison) does not — each one holds a WebGL context and its
   * own frame loop, and on software rendering three of them starved the renderer. The loop is
   * paused whenever the canvas leaves the viewport and resumed when it comes back; the
   * threshold is deliberately 0, so a canvas one pixel into view is live.
   */
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver((entries) => {
      const seen = entries[entries.length - 1];
      if (seen) viewerRef.current?.setRunning(seen.isIntersecting);
    });
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [status]);

  if (!webgl || status === 'failed') {
    return (
      <SceneFallback
        scene={scene}
        description={description}
        highlighted={highlighted}
        onSelect={onSelect}
        note={
          webgl
            ? 'The 3D engine failed to load — this is the same figure as a list.'
            : 'This browser has no WebGL, so the figure is shown as a list. Every object is here.'
        }
      />
    );
  }

  const hovered = hover ? datumById(scene, hover.id) : null;

  return (
    <div className="space-y-2">
      <div className="relative w-full" style={{ height }}>
        <canvas
          ref={canvasRef}
          role="img"
          aria-label={label ?? description.text}
          className="h-full w-full cursor-crosshair"
        />
        <div ref={overlayRef} className="pointer-events-none absolute inset-0 overflow-hidden" />
        {status !== 'ready' && (
          <div className="absolute inset-0 grid place-items-center text-xs text-chrome-500">
            loading 3D engine…
          </div>
        )}
        <div
          ref={tooltipRef}
          hidden={!hovered}
          className="pointer-events-none absolute top-0 left-0 z-10 max-w-[18rem] rounded-pill border border-line-strong bg-chrome-950/95 px-2 py-1 font-mono text-micro text-chrome-200 shadow-lg"
        >
          {hovered && describeDatumLine(hovered, description.color.field)}
        </div>
      </div>
      <details className="text-xs">
        <summary className="cursor-pointer text-chrome-500 hover:text-chrome-300">
          {description.count} object(s), as a keyboard-reachable list
        </summary>
        <div className="mt-2">
          <SceneFallback
            scene={scene}
            description={description}
            highlighted={highlighted}
            onSelect={onSelect}
          />
        </div>
      </details>
    </div>
  );
}

/**
 * `prefers-reduced-motion` — the one media query this module honours. A visitor who asked the
 * OS for less motion gets a still scene they can still orbit by hand.
 */
function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(query.matches);
    const listen = (event: MediaQueryListEvent) => setReduced(event.matches);
    query.addEventListener('change', listen);
    return () => query.removeEventListener('change', listen);
  }, []);
  return reduced;
}
