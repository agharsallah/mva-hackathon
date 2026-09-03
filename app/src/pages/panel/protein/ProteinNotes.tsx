/**
 * The prose half of the protein exhibit: the legend that changes with the active colour
 * encoding, the one-sentence reading, the provenance line, and the two honest failure
 * renderings (upstream down, candidates the model could not place).
 *
 * Split out of `ProteinExplorer.tsx` so that file stays the wiring and this one stays the
 * words. Every export is a component, so fast refresh keeps working.
 */

import { Link } from 'react-router-dom';

import { ApiError, type Origin } from '../../../api/client';
import { Chip } from '../../../components/Exhibit';
import { Callout } from '../../../components/Explainer';
import { ErrorCard } from '../../../components/QueryState';
import { dec, int } from '../../../lib/format';
import { C, impactColor, type Tone, TONE_MARK } from '../../../lib/palette';
import type { ProteinSceneBuild, UnplacedCandidate } from './buildScene';
import { BUCKET_EDGES } from './distances';

/** Wording shared by every encoding: what the marks mean regardless of the colour ramp. */
function Marks() {
  return (
    <>
      {' '}
      A <strong>larger sphere</strong> is a residue carrying one of this proband&apos;s
      protein-altering alleles, and it keeps its <em>impact</em> colour under every ramp so a
      verdict never disappears when the colour-by changes:{' '}
      <Chip color={impactColor('HIGH')}>HIGH</Chip> truncates the protein,{' '}
      <Chip color={impactColor('MODERATE')}>MODERATE</Chip> swaps one amino acid,{' '}
      <Chip color={impactColor('LOW')}>LOW/MODIFIER</Chip> is unlikely to matter. The yellow ring
      marks the residue picked in the URL; the yellow line joins the picked pair and carries their
      Cα distance in ångström. A residue drawn <Chip color={TONE_MARK.neutral}>small and grey</Chip>{' '}
      is one the filters do not emphasise — including every residue below pLDDT 70 while{' '}
      <em>dim low-confidence</em> is on, because a predicted position that uncertain supports no
      spatial claim.
    </>
  );
}

/** The colours the *active* encoding paints, decoded — the repo's Legend rule, per switch. */
export function EncodingLegend({
  encodingId,
  domainTones,
}: {
  encodingId: string;
  domainTones: Readonly<Record<string, Tone>>;
}) {
  const named = Object.entries(domainTones).filter(([name]) => name !== 'none');
  return (
    <>
      A smooth tube through the protein&apos;s <strong>alpha carbons</strong> (Cα — the one backbone
      atom every amino acid has), one bead per residue, in the model&apos;s own frame; the three
      axes are ångström (Å) and carry no genomic coordinate.
      {encodingId === 'domain' && (
        <>
          {' '}
          Colour = the annotated <strong>domain</strong> (a semi-independent working part of the
          fold):{' '}
          {named.map(([name, tone], i) => (
            <span key={name}>
              {i > 0 && ', '}
              <Chip color={TONE_MARK[tone]}>{name}</Chip>
            </span>
          ))}
          {named.length > 0 ? ', and ' : ' '}
          <Chip color={TONE_MARK.neutral}>grey = in no annotated domain</Chip>. Domains sharing a
          name across source databases share a colour; a fifth domain onward also falls to grey.
        </>
      )}
      {encodingId === 'plddt' && (
        <>
          {' '}
          Colour = <strong>pLDDT</strong>, AlphaFold&apos;s own per-residue confidence, 0–100:{' '}
          <Chip color={C.broken}>
            red ≈ 0–50, the model is guessing and the region is likely disordered
          </Chip>
          ,{' '}
          <Chip color={C.decision}>
            yellow ≈ 60–70, the fold is roughly right but the position is not
          </Chip>
          , <Chip color={C.good}>green ≈ 90–100, as trustworthy as an experimental structure</Chip>.
        </>
      )}
      {encodingId === 'impact' && (
        <>
          {' '}
          Colour = VEP&apos;s <strong>impact</strong> bucket for an allele on that residue:{' '}
          <Chip color={impactColor('HIGH')}>HIGH</Chip>,{' '}
          <Chip color={impactColor('MODERATE')}>MODERATE</Chip>,{' '}
          <Chip color={impactColor('LOW')}>LOW/MODIFIER</Chip>,{' '}
          <Chip color={TONE_MARK.neutral}>grey = no allele on this residue</Chip> — which is almost
          the whole chain.
        </>
      )}
      {encodingId === 'secondary' && (
        <>
          {' '}
          Colour = <strong>secondary structure</strong>, the local shape of the chain as the
          coordinate file annotates it: <Chip color={TONE_MARK.raw}>purple = helix</Chip>,{' '}
          <Chip color={TONE_MARK.machinery}>blue = strand</Chip>,{' '}
          <Chip color={TONE_MARK.neutral}>grey = coil or unannotated</Chip>. Absence of an
          annotation means &quot;not annotated&quot;, never &quot;all coil&quot;.
        </>
      )}
      {encodingId === 'rarity' && (
        <>
          {' '}
          Colour = the allele&apos;s <strong>rarity</strong> in gnomAD:{' '}
          <Chip color={TONE_MARK.good}>green = rare</Chip>, the only kind of allele a recessive
          candidate can be, <Chip color={TONE_MARK.broken}>red = common</Chip>, so a poor candidate,
          and <Chip color={TONE_MARK.neutral}>grey = no allele here</Chip>.
        </>
      )}
      <Marks />
    </>
  );
}

const READING: Record<string, string> = {
  domain:
    'Two damaging alleles landing in the same domain — or in two domains that pack against each ' +
    'other in this view — is a mechanism claim a 1D lollipop cannot make; two on opposite faces ' +
    'of the fold are two independent lesions.',
  plddt:
    'Check the confidence before believing any distance: a green stretch supports a spatial ' +
    'claim, a red one is a prediction of a region that may have no fixed shape at all, and the ' +
    'distance table marks a pair whose ends are not both green.',
  impact:
    'Look for two large, non-grey spheres close together: a compound heterozygote needs two ' +
    'damaged copies, and two hits packing into one pocket is the strongest structural story ' +
    'available without an experiment.',
  secondary:
    'A truncating allele early in a helix-rich region removes everything downstream of it; the ' +
    'shape here tells you how much of the fold a stop codon would take with it.',
  rarity:
    'A red (common) sphere is a poor recessive candidate however damaging it looks: the healthy ' +
    'population already carries it, so the pair to submit is green on both ends.',
};

export function EncodingReading({ encodingId }: { encodingId: string }) {
  return <>{READING[encodingId] ?? READING.domain}</>;
}

/**
 * Where the coordinates came from, how much of the chain they cover, and how much of it is
 * trustworthy. A prediction that does not say it is a prediction is the failure mode this
 * line exists to prevent.
 */
export function ProteinProvenance({
  build,
  model,
  origin,
}: {
  build: ProteinSceneBuild;
  model: {
    protein: string;
    uniprot: string | null;
    provenance: string;
    model_url: string;
    version: string | null;
  };
  origin?: Origin;
}) {
  const pct = build.confidentFraction === null ? null : build.confidentFraction * 100;
  return (
    <div className="mt-2 space-y-1 text-[11px] leading-relaxed text-chrome-500">
      <p>
        model:{' '}
        <span className="font-mono text-chrome-300">
          {model.provenance === 'alphafold' ? 'AlphaFold — a prediction' : 'PDB — an experiment'}
        </span>
        {model.version && <> · version {model.version}</>}
        {model.uniprot && (
          <>
            {' '}
            · UniProt <span className="font-mono text-chrome-300">{model.uniprot}</span>
          </>
        )}{' '}
        · translation <span className="font-mono text-chrome-300">{model.protein}</span> ·{' '}
        <a
          href={model.model_url}
          target="_blank"
          rel="noreferrer"
          className="text-machinery-400 underline decoration-dotted hover:text-machinery-300"
        >
          coordinate file
        </a>{' '}
        ·{' '}
        <Link
          to="/provenance#reference"
          className="text-machinery-400 underline decoration-dotted hover:text-machinery-300"
        >
          provenance manifest
        </Link>
      </p>
      <p>
        coverage: <span className="font-mono text-chrome-300">{int(build.modelled)}</span> residues
        modelled
        {build.unmodelled > 0 && (
          <>
            , <span className="font-mono text-decision-400">{int(build.unmodelled)}</span> not
            covered by the model and therefore unmeasured
          </>
        )}
        {pct !== null && (
          <>
            {' '}
            · <span className="font-mono text-chrome-300">{dec(pct, 1)} %</span> of them at pLDDT ≥
            70 ({int(build.confident)} residues), the floor below which a position supports no
            spatial claim
          </>
        )}
      </p>
      {origin === 'fixture' &&
        // The claim is gated on there being an allele to claim about. 15 of the 23 committed
        // fixture genes are fold-only (`candidates: []`), and announcing an invented allele
        // on a canvas that shows none both misleads and weakens the warning on the eight
        // genes where it is the point.
        (build.placed.length + build.unplaced.length > 0 ? (
          <p className="text-decision-400/90">
            fixture: <strong>real AlphaFold backbone</strong> (public reference data, identical for
            every human) + <strong>synthetic candidate alleles</strong> from the gene-structure
            fixture. The fold is true; the alleles painted on it are invented, so no distance below
            means anything clinically.
          </p>
        ) : (
          <p className="text-decision-400/90">
            fixture: <strong>real AlphaFold backbone</strong> (public reference data, identical for
            every human), and <strong>no allele is painted</strong> — this gene carries no candidate
            in the fixture, so nothing on the canvas is patient-derived or invented.
          </p>
        ))}
      <p>
        geometric bands:{' '}
        {BUCKET_EDGES.map((b, i) => (
          <span key={b.bucket}>
            {i > 0 && ' · '}
            <span className="text-chrome-400">{b.bucket}</span>{' '}
            {b.upTo === Infinity ? '(> 25 Å)' : `(< ${b.upTo} Å)`} — {b.means}
          </span>
        ))}
        . These are distance bands on one predicted model, not functional claims.
      </p>
    </div>
  );
}

/** A 502 names the upstream that was unreachable. Never a fixture-shaped stand-in. */
export function ProteinError({ error }: { error: Error }) {
  const status = error instanceof ApiError ? error.status : null;
  if (status !== 502) return <ErrorCard error={error} />;
  return (
    <Callout tone="broken" title="upstream structure source unreachable">
      The API could not reach <strong>AlphaFold DB</strong> (or Ensembl, which resolves the
      translation and the UniProt accession it is fetched by), so there are no coordinates to draw.
      Nothing is rendered on purpose: a guessed fold would be indistinguishable from a measured one
      on screen.
      <p className="mt-1.5 font-mono text-[11px] text-broken-400/80">{error.message}</p>
    </Callout>
  );
}

/** Candidates with no place on the fold, listed with the reason — never dropped. */
export function UnplacedList({ rows }: { rows: readonly UnplacedCandidate[] }) {
  if (rows.length === 0) return null;
  return (
    <ul className="mt-2 space-y-1 text-[11px] text-chrome-500">
      {rows.map((row) => (
        <li
          key={row.label}
          className="border-l-2 pl-2"
          style={{ borderColor: impactColor(row.impact) }}
        >
          <span className="font-mono text-chrome-300">{row.label}</span> not on the fold —{' '}
          {row.reason}
        </li>
      ))}
    </ul>
  );
}
