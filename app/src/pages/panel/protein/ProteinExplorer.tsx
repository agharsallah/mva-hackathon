/**
 * The protein explorer — the first exhibit in this app where the third dimension *is* the
 * finding.
 *
 * The domain lollipop puts this gene's protein-altering alleles on a 1D amino-acid axis and
 * answers "which domain". It is blind to the question that decides a compound heterozygote
 * (two different broken copies of one gene, one from each parent): are the two alleles'
 * residues *close in space*? A protein folds, so sequence distance is a poor proxy — two
 * residues 300 amino acids apart on the chain can pack into one pocket, and two neighbours
 * on the chain can point at opposite faces. This exhibit measures that directly, as a Cα
 * distance in ångström, and draws it.
 *
 * Layering: everything case-specific is in `buildScene.ts` / `encodings.ts` / `distances.ts`
 * / `filters.ts` — pure and unit-tested. `viz3d` supplies the canvas, the text twin, the
 * camera and the pick, and knows nothing about genes. This file is the wiring plus the two
 * things only a page can own: which URL keys hold the selection, and which words the legend
 * says.
 */

import { useCallback, useMemo } from 'react';

import {
  useGeneStructure,
  useHetPairs,
  useProteinStructure,
  useStructureGenes,
} from '../../../api/hooks';
import type { GeneStructure, PanelHetPairs, ProteinStructure } from '../../../api/types';
import { Select } from '../../../components/Controls';
import { Exhibit } from '../../../components/Exhibit';
import { Callout } from '../../../components/Explainer';
import { Skeleton } from '../../../components/QueryState';
import { useUrlKnownOption } from '../../../lib/hooks/useUrlKnownOption';
import { useUrlState } from '../../../lib/urlstate';
import {
  describeScene,
  SceneControls,
  type Selection3D,
  useSceneExplorer,
  useSceneSelection,
  Viz3dCanvas,
} from '../../../viz3d';
import { DEFAULT_GENE } from '../LocusExplorer';
import {
  buildProteinScene,
  emphasise,
  isCandidate,
  type ProteinSceneBuild,
  sliceProteinScene,
} from './buildScene';
import { OffPanelNote } from './compare/FoldPanel';
import { isNonCodingError } from './compare/metrics';
import { useComparePair } from './compareBridge';
import { type CandidateDistance, candidateDistances, findPair, pairLink } from './distances';
import { DistanceTable } from './DistanceTable';
import { useProteinFilters } from './filters';
import { canonicalGene, COMPARE_A, geneEntry, geneGroups, geneSymbols } from './geneSet';
import { ProteinFilters } from './ProteinFilters';
import {
  EncodingLegend,
  EncodingReading,
  ProteinError,
  ProteinProvenance,
  UnplacedList,
} from './ProteinNotes';

/** How many residues either side of the picked pair "focus on selection" keeps. */
const FOCUS_PAD = 40;

/**
 * The gene selection is the Panel page's own `gene` key, deliberately shared with the locus
 * explorer and the pair matrix: "which gene are we looking at" is a property of the page, so
 * one link moves the whole page to a coherent view.
 */
export function ProteinExplorer() {
  const set = useStructureGenes();
  const genes = useMemo(() => set.data?.data ?? [], [set.data]);
  // `canonicalGene` runs before the vocabulary check, so `?gene=bub1b` and `?gene=CCDC84`
  // resolve to the set's own spelling instead of spending a second request pair under their
  // own cache key and titling the exhibit in the reader's casing.
  const [gene, setGene] = useUrlKnownOption(
    'gene',
    DEFAULT_GENE,
    geneSymbols(genes),
    canonicalGene,
  );
  const entry = geneEntry(genes, gene);
  // A non-coding gene has no translation, so the protein endpoint would answer 422. The set
  // already said so, and a request is not spent to be told again.
  const coding = entry?.coding ?? true;
  const model = useProteinStructure(coding ? gene : null);
  const anatomy = useGeneStructure(gene);
  const pairs = useHetPairs(gene);
  const nonCoding = !coding || isNonCodingError(model.error);
  const error = nonCoding ? null : (model.error ?? anatomy.error);
  const groups = useMemo(() => geneGroups(genes), [genes]);

  return (
    <Exhibit
      title={`The fold in 3D — where ${gene}'s alleles sit in space`}
      controls={
        <Select
          value={gene}
          options={groups.length === 0 ? [{ value: gene, label: gene }] : []}
          groups={groups}
          onChange={setGene}
          disabled={groups.length === 0}
          label="gene"
        />
      }
      legend={<StaticLegend />}
      reading="Two damaging alleles close together in space is a mechanism claim; the same two on opposite faces of the fold are two independent lesions. Read every distance against the model's confidence at both ends before believing either story."
      source={model.data?.source}
      cachedAt={model.data?.cachedAt}
      origin={model.data?.origin}
      data={model.data?.data ? { protein: model.data.data.protein, gene } : undefined}
    >
      {nonCoding ? (
        <Callout tone="broken" title={`${gene} is non-coding — there is no protein to fold`}>
          {model.error?.message ??
            `${gene} has no protein-coding canonical transcript (biotype ${
              entry?.biotype ?? 'unknown'
            }).`}{' '}
          Every residue axis in this exhibit — the amino-acid index, the Cα coordinates, the domain
          annotation — is defined on a translation, and this gene has none. It is in the structure
          set as a reference row; no canvas is drawn rather than drawing something that is not a
          protein.
        </Callout>
      ) : error ? (
        <ProteinError error={error} />
      ) : model.data && anatomy.data ? (
        <Fold
          structure={model.data.data}
          geneStructure={anatomy.data.data}
          pairs={pairs.data?.data}
          origin={model.data.origin}
          anatomyOrigin={anatomy.data.origin}
        />
      ) : (
        <Skeleton height={520} />
      )}
    </Exhibit>
  );
}

/**
 * `Exhibit.legend` is registered for the AI export while the exhibit is mounted, so it has to
 * be renderable before any data arrives. The full decode of the *active* encoding lives under
 * the canvas instead, where it can change with the colour-by control.
 */
function StaticLegend() {
  return (
    <>
      A tube through the protein&apos;s alpha carbons (Cα — the one backbone atom every amino acid
      has), one bead per residue, coloured by whichever encoding the <code>colour by</code> control
      selects; the decode of the active one sits directly under the canvas, because the colours
      change with it. Larger spheres are this proband&apos;s protein-altering alleles, in their VEP
      impact colour under every ramp. The yellow ring is the residue held in{' '}
      <code>?prot.pick=</code>; the yellow line joins the picked pair and is labelled with their Cα
      distance in ångström (Å, 10⁻¹⁰ m). The three axes are the model&apos;s own frame in Å and
      carry no genomic coordinate.
    </>
  );
}

function Fold({
  structure,
  geneStructure,
  pairs,
  origin,
  anatomyOrigin,
}: {
  structure: ProteinStructure;
  geneStructure: GeneStructure;
  pairs?: PanelHetPairs;
  origin?: 'api' | 'fixture';
  anatomyOrigin?: 'api' | 'fixture';
}) {
  const result = useMemo(
    () => buildProteinScene(structure, geneStructure, pairs),
    [structure, geneStructure, pairs],
  );

  if (!result.ok) {
    return (
      <Callout tone="broken" title="nothing painted — the two payloads disagree">
        {result.error.message}
        {/*
          The one mismatch that is a *deployment* fault rather than a data fault: the offline
          fixture rewrites the model's translation id from the gene-structure **fixture**, so
          the two ids can only agree when both payloads come from the same side. A running API
          that predates `/api/panel/protein-structure` answers 404 for it, the client falls back
          to the fixture for that one endpoint, and this is what the reader sees. Name the fix.
        */}
        {origin !== anatomyOrigin && (
          <p className="mt-2">
            The two payloads came from different places — the 3D model from the{' '}
            <strong>{origin === 'fixture' ? 'offline fixture' : 'live API'}</strong>, the gene
            structure from the{' '}
            <strong>{anatomyOrigin === 'fixture' ? 'offline fixture' : 'live API'}</strong> — and
            the fixture takes its translation id from the fixture gene structure, so the two can
            never agree across that split. If the API is running, it is older than the{' '}
            <code>/api/panel/protein-structure</code> route: restart it with{' '}
            <code>uv run mva-viz-api</code>.
          </p>
        )}
      </Callout>
    );
  }
  return (
    <Explorer
      build={result.build}
      structure={structure}
      pairs={pairs}
      origin={origin}
      inPanel={geneStructure.in_panel}
    />
  );
}

function Explorer({
  build,
  structure,
  pairs,
  origin,
  inPanel,
}: {
  build: ProteinSceneBuild;
  structure: ProteinStructure;
  pairs?: PanelHetPairs;
  origin?: 'api' | 'fixture';
  /** False = fold only: no allele was ever annotated here, so none can be painted. */
  inPanel: boolean;
}) {
  const { scene: full, placed, unplaced } = build;
  const filters = useProteinFilters(structure.protein_length);

  // The pair is two residue ids — an amino-acid index either side, never a coordinate.
  const [pairA, setPairA] = useUrlState('prot.a', '');
  const [pairB, setPairB] = useUrlState('prot.b', '');

  const rows = useMemo(() => candidateDistances(placed, pairs), [placed, pairs]);
  const selectedRow = pairA && pairB ? findPair(rows, pairA, pairB) : undefined;

  const scene = useMemo(() => {
    const painted = emphasise(sliceProteinScene(full, filters.from, filters.to), filters.accept);
    return selectedRow ? { ...painted, links: [pairLink(selectedRow)] } : painted;
  }, [full, filters.from, filters.to, filters.accept, selectedRow]);

  const ids = useMemo(() => full.residues.map((residue) => residue.id), [full.residues]);
  const explorer = useSceneExplorer(scene, 'prot');
  const selection = useSceneSelection('prot', ids);

  const highlighted = useMemo(
    () => [...new Set([selection.picked, pairA, pairB].filter(Boolean))],
    [selection.picked, pairA, pairB],
  );

  /**
   * A click reports the residue. A click on a *candidate* also builds the pair: the first
   * candidate fills slot A, the second fills slot B and the link is drawn, a third starts
   * over, and re-clicking the one in slot A clears the pair.
   */
  const onSelect = useCallback(
    (picked: Selection3D | null) => {
      selection.onSelect(picked);
      if (!picked || !isCandidate(picked.datum)) return;
      if (picked.id === pairA) {
        setPairA('');
        setPairB('');
      } else if (!pairA || pairB) {
        setPairA(picked.id);
        setPairB('');
      } else {
        setPairB(picked.id);
      }
    },
    [selection, pairA, pairB, setPairA, setPairB],
  );

  const pickRow = useCallback(
    (row: CandidateDistance) => {
      setPairA(row.a.id);
      setPairB(row.b.id);
      const datum = full.residues.find((residue) => residue.id === row.a.id);
      if (datum) selection.onSelect({ id: datum.id, label: datum.label, datum });
    },
    [full.residues, selection, setPairA, setPairB],
  );

  /**
   * Hand this gene to the side-by-side comparison as side A, leaving side B on whatever it
   * held. Two URL writes in one tick, which `useUrlState` composes by reading the live
   * address bar rather than React Router's captured snapshot — see its own note.
   */
  const [, setCompareA] = useUrlState('prot.cmpA', COMPARE_A);
  const stageCompare = useCallback(
    () => setCompareA(structure.gene),
    [setCompareA, structure.gene],
  );

  /** Fit the camera to the selection by trimming the chain to it — see `sliceProteinScene`. */
  const focus = useCallback(() => {
    const positions = highlighted
      .map((id) => full.residues.find((residue) => residue.id === id)?.meta?.n)
      .filter((n): n is number => typeof n === 'number');
    if (positions.length === 0) return;
    filters.setWindow(
      Math.max(1, Math.min(...positions) - FOCUS_PAD),
      Math.min(filters.length, Math.max(...positions) + FOCUS_PAD),
    );
  }, [highlighted, full.residues, filters]);

  const compare = useComparePair(structure.gene, placed);
  const drawn = describeScene(explorer.scene, highlighted).count;

  return (
    <div className="space-y-3">
      <SceneControls
        explorer={explorer}
        view={selection.view}
        onViewChange={selection.setView}
        filters={false}
      />
      <ProteinFilters
        filters={filters}
        onFocus={focus}
        focusable={highlighted.length > 0}
        comparePair={compare.pair !== null}
        compareWhy={compare.why}
        onUseCompare={() => {
          if (!compare.pair) return;
          setPairA(compare.pair[0].id);
          setPairB(compare.pair[1].id);
        }}
      />

      <Viz3dCanvas
        scene={explorer.scene}
        height={520}
        highlighted={highlighted}
        onSelect={onSelect}
        view={selection.view}
      />

      {!inPanel && <OffPanelNote gene={structure.gene} />}

      <p className="text-xs leading-relaxed text-chrome-400">
        <span className="font-semibold text-chrome-300">Colours now</span> —{' '}
        <EncodingLegend encodingId={explorer.encoding.id} domainTones={build.domainTones} />
      </p>
      <p className="text-xs leading-relaxed text-chrome-400">
        <span className="font-semibold text-chrome-300">Reading</span> —{' '}
        <EncodingReading encodingId={explorer.encoding.id} />
      </p>

      <ProteinProvenance build={build} model={structure} origin={origin} />
      <UnplacedList rows={unplaced} />

      <div className="space-y-2 pt-1">
        <p className="text-xs text-chrome-400">
          <span className="font-semibold text-chrome-300">Closest candidate pairs</span> — the Cα
          distance between every pair of placed alleles, closest first. Click a pair to draw it in
          the view above; sort any column.
        </p>
        <DistanceTable
          rows={rows}
          selected={selectedRow?.key ?? null}
          onPick={pickRow}
          compareWith={{ gene: structure.gene, onCompare: stageCompare }}
        />
      </div>

      <p className="text-[11px] text-chrome-600">
        {drawn} of {build.modelled} modelled residues drawn (window {filters.from}–{filters.to} of{' '}
        {filters.length} amino acids; {build.unmodelled} carry no coordinates). One URL cites this
        figure: <code>?gene={structure.gene}</code>, <code>prot.pick</code>, <code>prot.a</code>/
        <code>prot.b</code>, <code>prot.by</code>, <code>prot.view</code>. Filters stay out of the
        URL on purpose — they are exploratory, not part of a citation.
      </p>
    </div>
  );
}
