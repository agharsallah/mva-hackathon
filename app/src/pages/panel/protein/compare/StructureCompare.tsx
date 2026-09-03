/**
 * Two folds, side by side, under one set of controls.
 *
 * Why this exhibit exists next to the single-gene explorer: a number off one predicted model
 * has no scale. "62 % of BUBR1 is above pLDDT 70" is unreadable until a second protein is
 * beside it — and the second protein is what tells a reader whether a long disordered stretch
 * is this gene's finding or AlphaFold's normal behaviour on a large multi-domain protein.
 * The comparison is therefore the *calibration* exhibit, not a second copy of the first one.
 *
 * Three properties, each of them a deliberate constraint:
 *
 * 1. **The controls are shared, not duplicated.** One colour-by, one confidence toggle, one
 *    camera preset. Two independent control rows would let a reader compare a domain-coloured
 *    fold against a pLDDT-coloured one and read the difference as biology.
 * 2. **"sync cameras" makes the two pictures literally the same view.** Both canvases are
 *    normalised into the same unit box by their adapters, so one `CameraPose3D` is meaningful
 *    on both — see `viz3d/spec/types.ts`. With it off, each canvas keeps its own orbit.
 *
 *    `onPose` stays attached even while sync is *off*, and only `pose` is withheld. That
 *    asymmetry is the fix for a real bug: with reporting also switched off, the shared `pose`
 *    went stale, both canvases' echo guards still matched it, and re-enabling sync resynced
 *    nothing until the reader orbited again. Reporting throughout means the shared pose is
 *    always the last camera a reader actually moved, so switching sync back on moves the
 *    *other* canvas onto it immediately (the reporting one's guard no-ops, by design).
 * 3. **Only a panel gene may show an allele.** Everything else in the set is fold-only, and
 *    each column says so under its canvas (`OffPanelNote`) rather than showing an empty
 *    allele count that would read as a statement about the proband.
 */

import { useMemo, useState } from 'react';

import { useStructureGenes } from '../../../../api/hooks';
import { Select, Toggle } from '../../../../components/Controls';
import { Exhibit } from '../../../../components/Exhibit';
import { Skeleton } from '../../../../components/QueryState';
import { useUrlKnownOption } from '../../../../lib/hooks/useUrlKnownOption';
import { useUrlEnum } from '../../../../lib/urlstate';
import {
  CAMERA_PRESETS,
  type CameraPose3D,
  type CameraPreset,
  type ColorEncoding,
} from '../../../../viz3d';
import {
  canonicalGene,
  COMPARE_A,
  COMPARE_B,
  geneEntry,
  geneGroups,
  geneSymbols,
} from '../geneSet';
import { FactSheet } from './FactSheet';
import { FoldPanel } from './FoldPanel';
import { type FoldState, useFold } from './useFold';

/** URL keys, so one link cites one comparison. */
const KEY_A = 'prot.cmpA';
const KEY_B = 'prot.cmpB';
const KEY_BY = 'prot.cmpBy';
const KEY_VIEW = 'prot.cmpView';

/** The encodings both scenes declare. Ids are stable across genes; the tone maps are not. */
function encodingsOf(...states: FoldState[]): readonly ColorEncoding[] {
  for (const state of states) {
    if (state.kind === 'ready') return state.build.scene.encodings ?? [state.build.scene.color];
  }
  return [];
}

export function StructureCompare() {
  const set = useStructureGenes();
  // Memoised because `?? []` is a fresh array on every render, and three derived memos
  // (symbols, groups, the per-gene folds) key off it.
  const genes = useMemo(() => set.data?.data ?? [], [set.data]);
  const symbols = useMemo(() => geneSymbols(genes), [genes]);

  // Canonicalised before the vocabulary check — see `canonicalGene`.
  const [a, setA] = useUrlKnownOption(KEY_A, COMPARE_A, symbols, canonicalGene);
  const [b, setB] = useUrlKnownOption(KEY_B, COMPARE_B, symbols, canonicalGene);
  const [view, setView] = useUrlEnum<CameraPreset>(KEY_VIEW, 'iso', CAMERA_PRESETS);
  const [dim, setDim] = useState(true);
  const [sync, setSync] = useState(true);
  const [pose, setPose] = useState<CameraPose3D | null>(null);
  // Bumped by "reset both cameras": re-applies the current preset on both canvases even
  // though `view` itself did not change. See `Viz3dCanvasProps.refitKey`.
  const [refitKey, setRefitKey] = useState(0);

  const foldA = useFold(a, geneEntry(genes, a));
  const foldB = useFold(b, geneEntry(genes, b));

  const encodings = encodingsOf(foldA, foldB);
  const encodingIds = useMemo(() => encodings.map((e) => e.id), [encodings]);
  const [by, setBy] = useUrlKnownOption(KEY_BY, 'domain', encodingIds);

  const groups = useMemo(() => geneGroups(genes), [genes]);
  // `onPose` always, `pose` only while sync is on — see property 2 in the module doc.
  const shared = { pose: sync ? pose : null, onPose: setPose, refitKey };

  /** Both cameras back to the shared preset, and the shared orbit dropped with them. */
  const resetCameras = () => {
    setPose(null);
    setRefitKey((n) => n + 1);
  };

  return (
    <Exhibit
      title={`Two folds side by side — ${a} against ${b}`}
      controls={
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          {/*
            While `/api/panel/structure-genes` is in flight `groups` is empty, and a `<select>`
            with a value and no options renders blank and cannot fire a resolvable change. The
            single-option fallback is the same one the explorer uses: show the gene the URL
            already names, disabled, until the vocabulary arrives.
          */}
          <Select
            value={a}
            options={groups.length === 0 ? [{ value: a, label: a }] : []}
            groups={groups}
            onChange={setA}
            disabled={groups.length === 0}
            label="A"
          />
          <Select
            value={b}
            options={groups.length === 0 ? [{ value: b, label: b }] : []}
            groups={groups}
            onChange={setB}
            disabled={groups.length === 0}
            label="B"
          />
        </div>
      }
      legend={<Legend />}
      reading="A percentage off one predicted model has no scale. Read every number in one column against the same number in the other: a long low-confidence stretch is only a finding if the comparison gene does not have one too."
      source={set.data?.source}
      cachedAt={set.data?.cachedAt}
      origin={set.data?.origin}
      data={{ compare: [a, b], colour_by: by, view }}
    >
      {set.isLoading ? (
        <Skeleton height={420} />
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <Select
              value={by}
              options={encodings.map((e) => ({ value: e.id, label: e.label }))}
              onChange={setBy}
              label="colour by (both)"
            />
            <Select
              value={view}
              options={CAMERA_PRESETS.map((preset) => ({ value: preset, label: preset }))}
              onChange={setView}
              label="camera (both)"
            />
            <Toggle on={dim} onChange={setDim}>
              dim low-confidence (pLDDT &lt; 70)
            </Toggle>
            <Toggle on={sync} onChange={setSync}>
              sync cameras
            </Toggle>
            <button
              type="button"
              onClick={resetCameras}
              title="drop the shared orbit and re-fit both canvases to the camera preset above"
              className="rounded-md border border-chrome-700 bg-chrome-900 px-2 py-1 text-[11px] text-chrome-400 transition hover:bg-chrome-800 hover:text-chrome-200"
            >
              reset both cameras
            </button>
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            {[foldA, foldB].map((state, index) => (
              <div key={index === 0 ? `A-${a}` : `B-${b}`} className="space-y-2">
                <p className="text-[11px] font-semibold text-chrome-300">
                  {index === 0 ? 'A' : 'B'} — {index === 0 ? a : b}
                </p>
                <FoldPanel
                  state={state}
                  encodingId={by}
                  dim={dim}
                  view={view}
                  {...shared}
                  height={380}
                />
              </div>
            ))}
          </div>

          <div className="grid gap-x-6 gap-y-3 border-t border-chrome-800 pt-3 md:grid-cols-2">
            {[foldA, foldB].map((state, index) => (
              <div key={index === 0 ? `fs-A-${a}` : `fs-B-${b}`} className="space-y-1.5">
                <p className="text-[11px] font-semibold text-chrome-300">{index === 0 ? a : b}</p>
                {state.kind === 'ready' ? (
                  <FactSheet metrics={state.metrics} />
                ) : (
                  <p className="text-[11px] text-chrome-600">
                    no fact sheet —{' '}
                    {state.kind === 'loading'
                      ? 'still loading'
                      : state.kind === 'non-coding'
                        ? 'non-coding, no protein'
                        : state.kind === 'mismatch'
                          ? 'the two payloads name different translations'
                          : 'the structure could not be fetched'}
                  </p>
                )}
              </div>
            ))}
          </div>

          <p className="text-[11px] text-chrome-600">
            One URL cites this comparison: <code>?{KEY_A}=</code>
            {a}, <code>{KEY_B}=</code>
            {b}, <code>{KEY_BY}=</code>
            {by}, <code>{KEY_VIEW}=</code>
            {view}. The confidence toggle, the camera sync and the camera reset stay out of the URL
            — they are gestures, not claims.
          </p>
        </div>
      )}
    </Exhibit>
  );
}

function Legend() {
  return (
    <>
      Two tubes through two proteins&apos; <strong>alpha carbons</strong> (Cα — the one backbone
      atom every amino acid has), one bead per residue, both coloured by the single{' '}
      <code>colour by</code> control so the two pictures are comparable by construction. Each canvas
      is normalised into the same unit box, which is what makes <strong>sync cameras</strong>{' '}
      meaningful: with it on, orbiting either canvas puts the other at the same camera pose, so a
      shape difference is a shape difference and not a viewpoint difference. A larger sphere is one
      of this proband&apos;s protein-altering alleles in its VEP impact colour — and it can only
      appear on a gene from the <strong>annotated panel</strong>. Every other gene in the set is{' '}
      <strong>fold only</strong>: the structure is public reference data, identical for every human,
      and nothing patient-derived is drawn on it. Residues drawn small and grey are below pLDDT 70,
      the floor below which a predicted position supports no spatial claim. The axes are each
      model&apos;s own frame in ångström and carry no genomic coordinate.
    </>
  );
}
